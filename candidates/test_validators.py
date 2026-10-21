from io import BytesIO
from zipfile import ZipFile

import pytest
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile

from candidates.validators import (
    MAX_RESUME_SIZE,
    validate_resume_file,
)


def create_valid_docx_bytes():
    buffer = BytesIO()

    with ZipFile(buffer, "w") as document:
        document.writestr(
            "[Content_Types].xml",
            '<?xml version="1.0" encoding="UTF-8"?>',
        )
        document.writestr(
            "word/document.xml",
            (
                '<?xml version="1.0" encoding="UTF-8"?>'
                "<document><body><p>Test résumé</p></body></document>"
            ),
        )

    return buffer.getvalue()


def test_valid_pdf_is_accepted():
    uploaded_file = SimpleUploadedFile(
        "candidate-resume.pdf",
        b"%PDF-1.7\nTest resume content\n%%EOF",
        content_type="application/pdf",
    )

    validate_resume_file(uploaded_file)

    assert uploaded_file.tell() == 0


def test_executable_disguised_as_pdf_is_rejected():
    uploaded_file = SimpleUploadedFile(
        "malicious-resume.pdf",
        b"MZ\x90\x00This is an executable",
        content_type="application/pdf",
    )

    with pytest.raises(
        ValidationError,
        match="not a valid PDF",
    ):
        validate_resume_file(uploaded_file)


def test_valid_docx_is_accepted():
    uploaded_file = SimpleUploadedFile(
        "candidate-resume.docx",
        create_valid_docx_bytes(),
        content_type=(
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        ),
    )

    validate_resume_file(uploaded_file)

    assert uploaded_file.tell() == 0


def test_invalid_docx_is_rejected():
    uploaded_file = SimpleUploadedFile(
        "fake-resume.docx",
        b"This is not a ZIP-based DOCX file.",
        content_type=(
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        ),
    )

    with pytest.raises(
        ValidationError,
        match="not a valid DOCX",
    ):
        validate_resume_file(uploaded_file)


def test_unsupported_extension_is_rejected():
    uploaded_file = SimpleUploadedFile(
        "candidate-resume.exe",
        b"MZ\x90\x00Executable data",
        content_type="application/octet-stream",
    )

    with pytest.raises(
        ValidationError,
        match="Only PDF and DOCX",
    ):
        validate_resume_file(uploaded_file)


def test_oversized_resume_is_rejected():
    uploaded_file = SimpleUploadedFile(
        "large-resume.pdf",
        b"%PDF-" + (b"0" * MAX_RESUME_SIZE),
        content_type="application/pdf",
    )

    with pytest.raises(
        ValidationError,
        match="larger than 5 MB",
    ):
        validate_resume_file(uploaded_file)
