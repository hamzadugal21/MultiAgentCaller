import hashlib
from pathlib import Path
from zipfile import BadZipFile, ZipFile

from django.db import transaction
from docx import Document
from pypdf import PdfReader
from pypdf.errors import PdfReadError

from auditlog.models import AuditEvent
from auditlog.services import AuditCommand, record_domain_event
from candidates.models import CandidateProfile, Resume
from candidates.transition_services import (
    activate_processed_resume,
    transition_resume_processing,
)
from candidates.validators import validate_resume_file

MAX_PDF_PAGES = 50
MAX_DOCX_ARCHIVE_ENTRIES = 500
MAX_DOCX_UNCOMPRESSED_BYTES = 20 * 1024 * 1024
MAX_EXTRACTED_CHARACTERS = 100_000


class ResumeServiceError(Exception):
    """Raised for safe resume upload or processing failures."""


def _checksum(uploaded_file):
    digest = hashlib.sha256()
    uploaded_file.seek(0)
    for chunk in uploaded_file.chunks():
        digest.update(chunk)
    uploaded_file.seek(0)
    return digest.hexdigest()


def _file_type(filename):
    extension = Path(filename).suffix.lower()
    return {
        ".pdf": ("pdf", "application/pdf", "pypdf-v1"),
        ".docx": (
            "docx",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "python-docx-v1",
        ),
    }[extension]


def create_pending_resume(*, candidate, actor, uploaded_file, request_id=None):
    validate_resume_file(uploaded_file)
    try:
        candidate = CandidateProfile.objects.select_related("user").get(
            pk=candidate.pk,
            user_id=actor.pk,
            user__is_active=True,
            user__role="candidate",
        )
    except (AttributeError, CandidateProfile.DoesNotExist) as error:
        raise ResumeServiceError("The resume upload is not authorized.") from error

    checksum = _checksum(uploaded_file)
    safe_type, mime_type, _ = _file_type(uploaded_file.name)
    resume = Resume(
        candidate=candidate,
        original_filename=Path(uploaded_file.name).name[:255],
        file_size=uploaded_file.size,
        sha256_checksum=checksum,
        mime_type=mime_type,
        is_active=False,
    )
    stored_name = None
    previous = candidate.resumes.filter(is_active=True).first()
    try:
        resume.file.save(resume.original_filename, uploaded_file, save=False)
        stored_name = resume.file.name
        with transaction.atomic():
            resume.save()
            metadata = {
                "checksum": checksum,
                "file_type": safe_type,
                "size_bytes": uploaded_file.size,
            }
            if previous is not None:
                metadata["replaces_resume_id"] = previous.pk
            record_domain_event(
                AuditCommand(
                    category=AuditEvent.Category.DATA_CHANGE,
                    event_type="resume.uploaded",
                    outcome=AuditEvent.Outcome.SUCCESS,
                    severity=AuditEvent.Severity.INFO,
                    resource_type="candidates.Resume",
                    resource_id=resume.pk,
                    actor=actor,
                    request_id=request_id,
                    metadata=metadata,
                )
            )
    except Exception:
        if stored_name:
            resume.file.storage.delete(stored_name)
        raise
    return resume


def _extract_pdf(resume):
    with resume.file.open("rb") as stream:
        reader = PdfReader(stream)
        if reader.is_encrypted or len(reader.pages) > MAX_PDF_PAGES:
            raise ResumeServiceError("pdf_limits")
        return "\n".join(page.extract_text() or "" for page in reader.pages)


def _extract_docx(resume):
    with resume.file.open("rb") as stream:
        try:
            with ZipFile(stream) as archive:
                entries = archive.infolist()
                if (
                    len(entries) > MAX_DOCX_ARCHIVE_ENTRIES
                    or sum(entry.file_size for entry in entries)
                    > MAX_DOCX_UNCOMPRESSED_BYTES
                ):
                    raise ResumeServiceError("docx_limits")
            stream.seek(0)
            document = Document(stream)
        except BadZipFile as error:
            raise ResumeServiceError("invalid_docx") from error
    return "\n".join(paragraph.text for paragraph in document.paragraphs)


def process_and_activate_resume(*, resume, actor, request_id=None):
    _, _, parser = _file_type(resume.original_filename)
    transition_resume_processing(
        resume=resume,
        target_status=Resume.ProcessingStatus.PROCESSING,
        parser=parser,
        request_id=request_id,
    )
    try:
        text = _extract_pdf(resume) if parser == "pypdf-v1" else _extract_docx(resume)
        if len(text) > MAX_EXTRACTED_CHARACTERS:
            raise ResumeServiceError("extracted_text_limit")
    except (PdfReadError, OSError, ValueError, ResumeServiceError) as error:
        failure_code = (
            str(error)
            if isinstance(error, ResumeServiceError)
            else "document_processing_failed"
        )
        return transition_resume_processing(
            resume=resume,
            target_status=Resume.ProcessingStatus.FAILED,
            parser=parser,
            failure_code=failure_code,
            request_id=request_id,
        )

    completed = transition_resume_processing(
        resume=resume,
        target_status=Resume.ProcessingStatus.COMPLETED,
        parser=parser,
        extracted_text=text,
        request_id=request_id,
    )
    return activate_processed_resume(
        resume=completed,
        actor=actor,
        request_id=request_id,
    )
