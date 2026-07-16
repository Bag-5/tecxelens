import hashlib
import json
import tempfile
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from services.report_generator import generate_report

router = APIRouter()

STORAGE_DIR = Path("storage") / "uploads"
CACHE_DIR = Path("storage") / "analysis_cache"


class ReportRequest(BaseModel):
    file_id: str


def _hash_file(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


@router.post("/report")
async def generate_pdf_report(body: ReportRequest):
    uploaded_files = list(STORAGE_DIR.glob(f"{body.file_id}_*"))
    if not uploaded_files:
        raise HTTPException(
            status_code=404,
            detail=f"File with id '{body.file_id}' not found",
        )

    file_path = uploaded_files[0]
    file_hash = _hash_file(file_path)
    cache_path = CACHE_DIR / f"{file_hash}.json"

    if not cache_path.exists():
        raise HTTPException(
            status_code=409,
            detail="No analysis found for this file. Run /analyze first.",
        )

    try:
        data = json.loads(cache_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=500,
            detail="Cached analysis data is corrupt. Re-analyze the file.",
        )

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp_path = Path(tmp.name)

    try:
        generate_report(data, file_path.name, tmp_path)
        pdf_bytes = tmp_path.read_bytes()
    finally:
        tmp_path.unlink(missing_ok=True)

    safe_name = file_path.stem.replace(" ", "_") + "_report.pdf"

    return StreamingResponse(
        iter([pdf_bytes]),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{safe_name}"',
            "Content-Length": str(len(pdf_bytes)),
        },
    )
