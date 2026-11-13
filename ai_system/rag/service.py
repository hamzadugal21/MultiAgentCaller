"""Local, permission-filtered hybrid retrieval without schema changes.

The index is deliberately process-local. PostgreSQL remains the source of truth
for domain objects and authorization; callers must obtain approved documents from
narrow Django services before ingestion. This avoids treating RAG as permission
control and avoids an unapproved pgvector migration.
"""

from __future__ import annotations

import hashlib
import io
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

EMBEDDING_MODEL_ID = "Xenova/all-MiniLM-L6-v2"
EMBEDDING_MODEL_REVISION = "cb3d680149bf9a3209564e1b27ab3bb355b65707"
DEFAULT_EMBEDDING_MODEL_PATH = Path("var/models/embeddings/all-minilm-l6-v2")
MAX_DOCUMENT_CHARACTERS = 50_000
MAX_CHUNK_CHARACTERS = 1_000
MAX_RESULTS = 8
MAX_INGEST_BYTES = 5 * 1024 * 1024
_TOKEN_PATTERN = re.compile(r"[a-z0-9_]{2,}", re.IGNORECASE)
_INJECTION_PATTERNS = (
    "ignore previous instructions",
    "system message",
    "developer message",
    "reveal prompt",
    "execute command",
)


class RagError(Exception):
    """Safe base error for retrieval failures."""


class EmbeddingUnavailable(RagError):
    """Raised when the explicit local embedding assets are unavailable."""


class Embedder(Protocol):
    def embed(self, texts: list[str]) -> list[list[float]]: ...


@dataclass(frozen=True, slots=True)
class RetrievalPrincipal:
    user_id: str
    role: str
    company_id: str | None = None
    candidate_id: str | None = None
    ai_processing_consented: bool = False


@dataclass(frozen=True, slots=True)
class RagDocument:
    source_id: str
    domain: str
    version: str
    text: str
    company_id: str | None = None
    candidate_id: str | None = None
    requires_consent: bool = False
    active: bool = True


@dataclass(frozen=True, slots=True)
class RetrievalResult:
    source_id: str
    domain: str
    version: str
    chunk_index: int
    text: str
    score: float
    injection_warning: bool


@dataclass(frozen=True, slots=True)
class _Chunk:
    source_id: str
    domain: str
    version: str
    text: str
    embedding: tuple[float, ...]
    keyword_counts: Counter[str]
    company_id: str | None
    candidate_id: str | None
    requires_consent: bool
    chunk_index: int


class LocalMiniLMEmbedder:
    """CPU ONNX sentence embedder using explicit ignored local model assets."""

    def __init__(self, model_path: Path | str = DEFAULT_EMBEDDING_MODEL_PATH):
        self._model_path = Path(model_path)
        self._session = None
        self._tokenizer = None

    def _load(self) -> None:
        if self._session is not None:
            return
        model_file = self._model_path / "onnx" / "model_int8.onnx"
        if not model_file.is_file():
            raise EmbeddingUnavailable("embedding_model_unavailable")
        try:
            import onnxruntime
            from transformers import AutoTokenizer

            self._tokenizer = AutoTokenizer.from_pretrained(
                self._model_path,
                local_files_only=True,
                trust_remote_code=False,
            )
            self._session = onnxruntime.InferenceSession(
                str(model_file),
                providers=["CPUExecutionProvider"],
            )
        except (ImportError, OSError, RuntimeError, ValueError) as error:
            raise EmbeddingUnavailable("embedding_model_unavailable") from error

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts or any(not isinstance(text, str) or not text for text in texts):
            raise RagError("embedding_input_invalid")
        self._load()
        try:
            encoded = self._tokenizer(
                texts,
                max_length=256,
                padding=True,
                truncation=True,
                return_tensors="np",
            )
            inputs = {
                item.name: encoded[item.name]
                for item in self._session.get_inputs()
                if item.name in encoded
            }
            output = self._session.run(None, inputs)[0]
            mask = encoded["attention_mask"]
            vectors: list[list[float]] = []
            for row, row_mask in zip(output, mask, strict=True):
                count = max(int(row_mask.sum()), 1)
                vector = (row * row_mask[:, None]).sum(axis=0) / count
                norm = float((vector**2).sum() ** 0.5) or 1.0
                vectors.append([float(value / norm) for value in vector])
            return vectors
        except (KeyError, RuntimeError, ValueError) as error:
            raise RagError("embedding_failed") from error


class SharedRagService:
    """A bounded local hybrid index with permission filtering before ranking."""

    def __init__(self, embedder: Embedder, *, chunk_characters: int = MAX_CHUNK_CHARACTERS):
        if not 100 <= chunk_characters <= MAX_CHUNK_CHARACTERS:
            raise ValueError("invalid chunk size")
        self._embedder = embedder
        self._chunk_characters = chunk_characters
        self._chunks: list[_Chunk] = []
        self._source_versions: dict[str, str] = {}

    def reindex(self, documents: list[RagDocument]) -> int:
        """Replace only supplied sources; inactive versions are removed safely."""
        source_ids = {document.source_id for document in documents}
        self._chunks = [chunk for chunk in self._chunks if chunk.source_id not in source_ids]
        for document in documents:
            self._validate_document(document)
            self._source_versions[document.source_id] = document.version
            if not document.active:
                continue
            chunks = self._chunk_text(document.text)
            vectors = self._embedder.embed(chunks)
            for index, (text, vector) in enumerate(zip(chunks, vectors, strict=True)):
                self._chunks.append(
                    _Chunk(
                        source_id=document.source_id,
                        domain=document.domain,
                        version=document.version,
                        text=text,
                        embedding=tuple(vector),
                        keyword_counts=Counter(self._tokens(text)),
                        company_id=document.company_id,
                        candidate_id=document.candidate_id,
                        requires_consent=document.requires_consent,
                        chunk_index=index,
                    )
                )
        return len(self._chunks)

    @staticmethod
    def extract_approved_text(*, filename: str, content: bytes) -> str:
        """Extract bounded text from an explicitly approved in-memory document.

        The caller must already have authorized document access. No source path,
        file object, or raw bytes are retained by this method.
        """
        if not isinstance(filename, str) or not isinstance(content, bytes) or not content:
            raise RagError("document_input_invalid")
        if len(content) > MAX_INGEST_BYTES:
            raise RagError("document_too_large")
        suffix = Path(filename).suffix.lower()
        try:
            if suffix == ".txt":
                text = content.decode("utf-8")
            elif suffix == ".pdf":
                from pypdf import PdfReader

                text = "\n".join(page.extract_text() or "" for page in PdfReader(io.BytesIO(content)).pages)
            elif suffix == ".docx":
                from docx import Document

                text = "\n".join(paragraph.text for paragraph in Document(io.BytesIO(content)).paragraphs)
            else:
                raise RagError("document_type_unsupported")
        except RagError:
            raise
        except (OSError, RuntimeError, UnicodeDecodeError, ValueError) as error:
            raise RagError("document_text_extraction_failed") from error
        text = " ".join(text.split())
        if not text:
            raise RagError("document_text_empty")
        return text[:MAX_DOCUMENT_CHARACTERS]

    def retrieve(
        self,
        *,
        query: str,
        principal: RetrievalPrincipal,
        limit: int = 4,
    ) -> list[RetrievalResult]:
        if not query or not isinstance(query, str) or not 1 <= limit <= MAX_RESULTS:
            raise RagError("retrieval_request_invalid")
        query_vector = self._embedder.embed([query])[0]
        query_terms = Counter(self._tokens(query))
        permitted = [chunk for chunk in self._chunks if self._permitted(chunk, principal)]
        scored = [
            (self._score(query_vector, query_terms, chunk), chunk)
            for chunk in permitted
        ]
        scored.sort(key=lambda item: (-item[0], item[1].source_id, item[1].chunk_index))
        return [
            RetrievalResult(
                source_id=chunk.source_id,
                domain=chunk.domain,
                version=chunk.version,
                chunk_index=chunk.chunk_index,
                text=chunk.text,
                score=round(score, 6),
                injection_warning=self._contains_injection(chunk.text),
            )
            for score, chunk in scored[:limit]
        ]

    @staticmethod
    def _validate_document(document: RagDocument) -> None:
        if (
            not document.source_id
            or not document.domain
            or not document.version
            or not isinstance(document.text, str)
            or len(document.text) > MAX_DOCUMENT_CHARACTERS
        ):
            raise RagError("document_invalid")
        if document.candidate_id and not document.requires_consent:
            raise RagError("candidate_document_requires_consent")

    def _chunk_text(self, text: str) -> list[str]:
        text = " ".join(text.split())
        if not text:
            raise RagError("document_empty")
        return [text[offset : offset + self._chunk_characters] for offset in range(0, len(text), self._chunk_characters)]

    @staticmethod
    def _tokens(text: str) -> list[str]:
        return _TOKEN_PATTERN.findall(text.lower())

    @staticmethod
    def _contains_injection(text: str) -> bool:
        lowered = text.lower()
        return any(pattern in lowered for pattern in _INJECTION_PATTERNS)

    @staticmethod
    def _permitted(chunk: _Chunk, principal: RetrievalPrincipal) -> bool:
        if chunk.company_id and chunk.company_id != principal.company_id:
            return False
        if chunk.candidate_id and chunk.candidate_id != principal.candidate_id:
            return False
        if chunk.requires_consent and not principal.ai_processing_consented:
            return False
        return True

    @staticmethod
    def _score(query_vector: list[float], query_terms: Counter[str], chunk: _Chunk) -> float:
        semantic = sum(left * right for left, right in zip(query_vector, chunk.embedding, strict=True))
        shared = sum((query_terms & chunk.keyword_counts).values())
        keyword = shared / max(sum(query_terms.values()), 1)
        return (0.8 * semantic) + (0.2 * keyword)


def source_fingerprint(document: RagDocument) -> str:
    """Version-aware identifier for callers that track source freshness."""
    payload = f"{document.source_id}\0{document.version}\0{document.text}".encode()
    return hashlib.sha256(payload).hexdigest()
