from pathlib import Path
from zipfile import BadZipFile, ZipFile

from django.core.exceptions import ValidationError

MAX_RESUME_SIZE = 5 * 1024 * 1024
ALLOWED_EXTENSIONS = {".pdf", ".docx"}


def validate_resume_file(uploaded_file):
    extension = Path(uploaded_file.name).suffix.lower()

    if extension not in ALLOWED_EXTENSIONS:
        raise ValidationError("Only PDF and DOCX resume files are allowed.")

    if uploaded_file.size <= 0:
        raise ValidationError("The uploaded resume is empty.")

    if uploaded_file.size > MAX_RESUME_SIZE:
        raise ValidationError("The resume must not be larger than 5 MB.")

    original_position = uploaded_file.tell()

    try:
        uploaded_file.seek(0)

        if extension == ".pdf":
            header = uploaded_file.read(1024)

            if b"%PDF-" not in header:
                raise ValidationError("The uploaded file is not a valid PDF.")

        elif extension == ".docx":
            uploaded_file.seek(0)

            try:
                with ZipFile(uploaded_file) as document:
                    entries = set(document.namelist())

                    required_entries = {
                        "[Content_Types].xml",
                        "word/document.xml",
                    }

                    if not required_entries.issubset(entries):
                        raise ValidationError(
                            "The uploaded file is not a valid DOCX document."
                        )
            except BadZipFile as error:
                raise ValidationError(
                    "The uploaded file is not a valid DOCX document."
                ) from error

    finally:
        uploaded_file.seek(original_position)
