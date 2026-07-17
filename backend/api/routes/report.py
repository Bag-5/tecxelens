import json
import tempfile
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from services.report_generator import generate_report

router = APIRouter()

CACHE_DIR = Path("storage") / "analysis_cache"


class ReportRequest(BaseModel):
    file_id: str


@router.post("/report")
async def generate_pdf_report(body: ReportRequest):
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    mapping_path = CACHE_DIR / "_by_id" / f"{body.file_id}.json"
    if not mapping_path.exists():
        raise HTTPException(
            status_code=404,
            detail="Analysis data not found. Upload and analyze a file first.",
        )

    try:
        mapping = json.loads(mapping_path.read_text(encoding="utf-8"))
        file_hash = mapping["file_hash"]
    except (json.JSONDecodeError, KeyError):
        raise HTTPException(
            status_code=500,
            detail="Analysis mapping is corrupt. Re-analyze the file.",
        )

    cache_path = CACHE_DIR / f"{file_hash}.json"
    if not cache_path.exists():
        raise HTTPException(
            status_code=409,
            detail="Cached analysis data is missing. Re-analyze the file.",
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
        generate_report(data, "analysis", tmp_path)
        pdf_bytes = tmp_path.read_bytes()
    finally:
        tmp_path.unlink(missing_ok=True)

    return StreamingResponse(
        iter([pdf_bytes]),
        media_type="application/pdf",
        headers={
            "Content-Disposition": 'attachment; filename="compliance_report.pdf"',
            "Content-Length": str(len(pdf_bytes)),
        },
    )
