from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from services.ai_service import generate_report
from services.pdf_parser import parse_pdf
from services.rule_engine import evaluate
from services.knowledge_service import search as knowledge_search
from services.nvd_service import search_cves, extract_tech_keywords
from services.scoring_engine import compute_score

router = APIRouter()

STORAGE_DIR = Path("storage") / "uploads"


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


async def _enrich_with_cves(finding: dict, doc_text: str) -> list[dict]:
    combined = f"{finding['title']} {finding['reference']} {doc_text}"
    tech_kws = extract_tech_keywords(combined)
    if not tech_kws:
        return []

    seen: set[str] = set()
    all_cves: list[dict] = []
    for kw in tech_kws:
        results = await search_cves(kw, top_k=5)
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
    parsed = parse_pdf(file_path)
    raw_findings = evaluate(parsed["text"])

    scoring = compute_score(raw_findings)
    overall_score = scoring["overall_score"]
    risk_level = scoring["risk_level"]

    enriched = []
    for f in raw_findings:
        refs = _gather_finding_references(f)
        cves = await _enrich_with_cves(f, parsed["text"])
        enriched.append({
            "title": f["title"],
            "severity": f["severity"],
            "rule_reference": f["reference"],
            "references": refs,
            "cves": cves,
        })

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

    return {
        "summary": ai_result["summary"],
        "overall_score": overall_score,
        "risk_level": risk_level,
        "findings": findings_out,
    }
