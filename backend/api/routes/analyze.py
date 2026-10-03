import asyncio
import hashlib
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from services.ai_service import generate_report
from services.document_parser import parse_document
from services.rule_engine import evaluate
from services.knowledge_service import search as knowledge_search
from services.nvd_service import search_cves, extract_tech_keywords
from services.scoring_engine import compute_score
from services import storage_service as storage
from core.config import STORAGE_DIR

router = APIRouter()


class AnalyzeRequest(BaseModel):
    file_id: str


def _gather_finding_references(finding: dict) -> list[dict]:
    query = f"{finding['title']} {finding['reference']}"
    results = knowledge_search(query, top_k=3)
    seen: set[str] = set()
    refs: list[dict] = []
    for r in results:
        key = f"{r['document']}|{r['section']}"
        if key in seen:
            continue
        seen.add(key)
        refs.append({"document": r["document"], "section": r["section"]})
    return refs[:3]


def _hash_file(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def cache_path(file_hash: str) -> Path:
    return storage.cache_payload_path(file_hash)


async def _enrich_with_cves(finding: dict, doc_text: str) -> list[dict]:
    combined = f"{finding['title']} {finding['reference']} {doc_text}"
    tech_kws = extract_tech_keywords(combined)
    if not tech_kws:
        return []

    per_keyword = await asyncio.gather(
        *(search_cves(kw, top_k=5) for kw in tech_kws)
    )

    seen: set[str] = set()
    all_cves: list[dict] = []
    for results in per_keyword:
        for cve in results:
            if cve["id"] not in seen:
                seen.add(cve["id"])
                all_cves.append(cve)

    all_cves.sort(
        key=lambda c: (-(c["cvss_score"] or 0))
    )
    return all_cves[:3]


@router.post("/analyze")
async def analyze_file(body: AnalyzeRequest):
    uploaded_files = list(STORAGE_DIR.glob(f"{body.file_id}_*"))
    if not uploaded_files:
        raise HTTPException(
            status_code=404,
            detail=f"File with id '{body.file_id}' not found",
        )

    file_path = uploaded_files[0]
    try:
        file_hash = _hash_file(file_path)
    except OSError as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Could not read the uploaded file: {exc}",
        )
    cached = storage.load_cached_analysis(file_hash)
    if cached:
        storage.save_file_id_mapping(body.file_id, file_hash)
        return cached

    # A corrupt, encrypted, or image-only PDF makes pypdf raise. Left
    # unhandled it escapes the app entirely: the 500 is generated outside the
    # CORS middleware, so the browser reports "Failed to fetch" and the UI
    # claims the backend is down instead of saying the file is unreadable.
    # Raising HTTPException keeps it inside the middleware stack, which means
    # the error reaches the client with proper CORS headers and a real message.
    try:
        parsed = parse_document(file_path)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=422,
            detail=(
                "Could not read this document. It may be corrupt, encrypted, "
                "or a scanned image with no extractable text."
            ),
        ) from exc

    if not (parsed.get("text") or "").strip():
        raise HTTPException(
            status_code=422,
            detail=(
                "No extractable text found. Scanned or image-only PDFs need OCR "
                "before they can be analyzed."
            ),
        )

    raw_findings = evaluate(parsed["text"])

    scoring = compute_score(raw_findings)
    overall_score = scoring["overall_score"]
    risk_level = scoring["risk_level"]

    enriched = []
    async def _build_enriched_finding(finding: dict) -> dict:
        refs = _gather_finding_references(finding)
        cves = await _enrich_with_cves(finding, parsed["text"])
        return {
            "title": finding["title"],
            "severity": finding["severity"],
            "rule_reference": finding["reference"],
            "references": refs,
            "cves": cves,
        }

    if raw_findings:
        enriched = await asyncio.gather(*(_build_enriched_finding(f) for f in raw_findings))

    ai_result = await generate_report(enriched, parsed["text"])

    findings_out = []
    for i, f in enumerate(enriched):
        ai_detail = ai_result["details"][i] if i < len(ai_result["details"]) else {}
        findings_out.append({
            "title": f["title"],
            "severity": f["severity"],
            "description": ai_detail.get("description", ""),
            "recommendation": ai_detail.get("recommendation", ""),
            "references": f["references"],
            "cves": f["cves"],
        })

    response = {
        "summary": ai_result["summary"],
        "overall_score": overall_score,
        "risk_level": risk_level,
        "findings": findings_out,
    }
    storage.save_cached_analysis(file_hash, response)
    storage.save_file_id_mapping(body.file_id, file_hash)
    storage.prune_all()
    return response
