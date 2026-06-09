import os
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException, UploadFile, status


ALLOWED_UPLOAD_EXTENSIONS = {
    ".pdf",
    ".jpg",
    ".jpeg",
    ".png",
    ".doc",
    ".docx",
    ".ppt",
    ".pptx",
    ".xls",
    ".xlsx",
    ".txt",
    ".rtf",
}

BLOCKED_UPLOAD_EXTENSIONS = {
    ".exe",
    ".bat",
    ".cmd",
    ".com",
    ".js",
    ".msi",
    ".ps1",
    ".scr",
    ".sh",
}


def validate_upload_file(file: UploadFile) -> str:
    original_filename = os.path.basename(file.filename or "file")
    extension = Path(original_filename).suffix.lower()

    if extension in BLOCKED_UPLOAD_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Этот тип файла нельзя загружать",
        )

    if extension not in ALLOWED_UPLOAD_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Поддерживаются PDF, изображения, документы Word/Office и TXT",
        )

    return original_filename


def build_upload_path(user_id: int, filename: str) -> str:
    safe_filename = os.path.basename(filename or "file")
    saved_filename = f"{user_id}_{uuid4().hex}_{safe_filename}"
    return os.path.join("uploads", saved_filename)
