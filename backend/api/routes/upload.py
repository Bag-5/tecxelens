import uuid
from pathlib import Path

from fastapi import APIRouter, File, UploadFile, HTTPException

router = APIRouter()

STORAGE_DIR = Path("storage") / "uploads"
ALLOWED_EXTENSIONS = {".pdf", ".txt", ".pptx", ".docx"}


@router.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    STORAGE_DIR.mkdir(parents=True, exist_ok=True)

    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail="Only PDF, TXT, DOCX, and PPTX files are supported.",
        )

    file_id = str(uuid.uuid4())
    safe_filename = file.filename or "unnamed"
    save_path = STORAGE_DIR / f"{file_id}_{safe_filename}"

    try:
        content = await file.read()
        save_path.write_bytes(content)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save file: {str(e)}")

    return {
        "file_id": file_id,
        "filename": safe_filename,
        "status": "uploaded",
    }
