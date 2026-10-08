"""Secure file storage for uploaded documents."""

import uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile, status

from app.core.config import BASE_DIR, settings

_CHUNK = 1024 * 1024


def _upload_root() -> Path:
    root = Path(settings.UPLOAD_DIR)
    if not root.is_absolute():
        root = BASE_DIR / root
    root.mkdir(parents=True, exist_ok=True)
    return root


def validate_extension(filename: str) -> str:
    ext = (filename or "").rsplit(".", 1)[-1].lower()
    if ext not in settings.allowed_extension_set:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Unsupported file type '.{ext}'. Allowed: "
                f"{', '.join(sorted(settings.allowed_extension_set))}."
            ),
        )
    return ext


def save_upload(file: UploadFile, subdir: str = "documents") -> tuple[str, int]:
    """Persist an upload with a safe generated name. Returns (path, size_bytes)."""
    ext = validate_extension(file.filename)
    target_dir = _upload_root() / subdir
    target_dir.mkdir(parents=True, exist_ok=True)

    safe_name = f"{uuid.uuid4().hex}.{ext}"
    target = target_dir / safe_name

    max_bytes = settings.MAX_UPLOAD_MB * 1024 * 1024
    size = 0
    try:
        with open(target, "wb") as out:
            while True:
                chunk = file.file.read(_CHUNK)
                if not chunk:
                    break
                size += len(chunk)
                if size > max_bytes:
                    out.close()
                    target.unlink(missing_ok=True)
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail=f"File exceeds the {settings.MAX_UPLOAD_MB}MB limit.",
                    )
                out.write(chunk)
    except HTTPException:
        raise
    except OSError as exc:
        target.unlink(missing_ok=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Could not store uploaded file: {exc}",
        ) from exc

    if size == 0:
        target.unlink(missing_ok=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded file is empty."
        )

    return str(target), size
