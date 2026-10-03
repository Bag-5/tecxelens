import re
import uuid
from pathlib import Path

from fastapi import APIRouter, File, UploadFile, HTTPException

from core.config import STORAGE_DIR, UPLOAD_MAX_BYTES
from services.storage_service import prune_uploads

router = APIRouter()

ALLOWED_EXTENSIONS = {".pdf", ".txt", ".pptx", ".docx"}
MAX_UPLOAD_BYTES = UPLOAD_MAX_BYTES


def _safe_filename(raw: str | None) -> str:
    """Reduce a client-supplied filename to a harmless basename.

    UploadFile.filename is attacker-controlled, so it must never reach the
    filesystem verbatim: values like "../../etc/passwd" or "C:\\win\\x.pdf"
    would otherwise escape STORAGE_DIR.
    """
    name = Path(raw or "unnamed").name
    name = re.sub(r"[^A-Za-z0-9._-]", "_", name).lstrip(".")
    return name or "unnamed"


@router.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    STORAGE_DIR.mkdir(parents=True, exist_ok=True)

    safe_filename = _safe_filename(file.filename)
    suffix = Path(safe_filename).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail="Only PDF, TXT, DOCX, and PPTX files are supported.",
        )

    file_id = str(uuid.uuid4())
    save_path = STORAGE_DIR / f"{file_id}_{safe_filename}"

    try:
        content = await file.read()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read file: {str(e)}")

    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File exceeds the {MAX_UPLOAD_BYTES // (1024 * 1024)}MB limit.",
        )

    try:
        save_path.write_bytes(content)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save file: {str(e)}")

    prune_uploads()

    return {
        "file_id": file_id,
        "filename": safe_filename,
        "status": "uploaded",
    }