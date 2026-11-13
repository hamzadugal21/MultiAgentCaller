"""Explicitly download pinned local assets for the detached shared AI foundation."""

from __future__ import annotations

import sys
from pathlib import Path

from huggingface_hub import hf_hub_download

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def main() -> None:
    from ai_system.rag.service import (
        DEFAULT_EMBEDDING_MODEL_PATH,
        EMBEDDING_MODEL_ID,
        EMBEDDING_MODEL_REVISION,
    )
    from ai_system.runtime.llama_cpp import (
        DEFAULT_QWEN3B_MODEL_PATH,
        QWEN3B_MODEL_ID,
        QWEN3B_MODEL_REVISION,
    )

    hf_hub_download(
        repo_id=QWEN3B_MODEL_ID,
        filename=DEFAULT_QWEN3B_MODEL_PATH.name,
        revision=QWEN3B_MODEL_REVISION,
        local_dir=DEFAULT_QWEN3B_MODEL_PATH.parent,
    )
    for filename in (
        "config.json",
        "tokenizer.json",
        "tokenizer_config.json",
        "special_tokens_map.json",
        "vocab.txt",
        "onnx/model_int8.onnx",
    ):
        hf_hub_download(
            repo_id=EMBEDDING_MODEL_ID,
            filename=filename,
            revision=EMBEDDING_MODEL_REVISION,
            local_dir=DEFAULT_EMBEDDING_MODEL_PATH,
        )
    print("Pinned shared AI model assets are available locally.")


if __name__ == "__main__":
    main()
