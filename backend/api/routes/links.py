"""Link reputation endpoints.

Three endpoints rather than one, because VirusTotal analysis is asynchronous:

* ``POST /scan-links``          look up what is already known (fast, cached)
* ``POST /scan-links/submit``  ask for fresh analysis of unknown URLs
* ``POST /scan-links/status``   re-poll after submitting

There is no background worker. Shared hosting allows no threads and caps
requests at five minutes, so the client drives the polling loop and every
request stays short.
"""

import hashlib
import logging
import uuid
from urllib.parse import urlsplit

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from core.config import VIRUSTOTAL_MAX_URLS, VIRUSTOTAL_SUBMIT
from services import link_service, storage_service as storage
from services.ai_service import generate_report
from services.link_providers import get_provider
from services.scoring_engine import compute_link_risk

logger = logging.getLogger(__name__)

router = APIRouter()

# Hard ceiling on a single request regardless of configured max. VIRUSTOTAL_MAX_URLS
# governs how many are actually scanned; this stops an oversized paste from being
# accepted and silently truncated with no explanation.
_REQUEST_URL_LIMIT = 100

_ACTIONABLE = {"critical", "high", "medium", "low"}


class LinkScanRequest(BaseModel):
    urls: list[str] = Field(default_factory=list)
    # Set false to skip the AI prose pass when only the verdicts are wanted.
    enrich: bool = True


def _host(url: str) -> str:
    try:
        return urlsplit(url).hostname or url
    except ValueError:
        return url


def _verdict_sentence(link: dict) -> str:
    counts = (
        f"{link['malicious']} security vendors flagged this URL as malicious, "
        f"{link['suspicious']} as suspicious, and {link['harmless']} found it "
        f"harmless"
    )
    categories = ", ".join(sorted(set(link.get("categories", {}).values())))
    if categories:
        counts += f". Categorised as: {categories}"
    return counts + "."


def _link_to_finding(link: dict) -> dict:
    """Build a finding from a verdict.

    The text is derived from VirusTotal's own numbers rather than generated, so
    it stays factual even when the AI pass is unavailable or disabled.
    """
    host = _host(link["url"])
    return {
        "title": f"{link['verdict'].title()} link: {host}",
        "severity": link["severity"],
        "description": (
            f"{link['url']} was checked against VirusTotal's URL reputation "
            f"data. {_verdict_sentence(link)}"
        ),
        "recommendation": (
            "Do not visit or distribute this URL until it has been reviewed. "
            "Confirm the expected owner out of band, and if the link came from "
            "a document, verify it against the issuing party's official "
            "records before acting on it."
        ),
        "references": [],
        "cves": [],
    }


def _fallback_summary(links: list[dict], score: int, level: str) -> str:
    actionable = [link for link in links if link["severity"] in _ACTIONABLE]
    if not actionable:
        return (
            f"No suspicious links were found. The link risk score is {score} "
            f"({level}). Links that could not be checked are reported as "
            f"unknown and have not been verified either way."
        )
    hosts = sorted({_host(link["url"]) for link in actionable})
    return (
        f"{len(actionable)} of {len(links)} links carry a security flag, giving "
        f"a link risk score of {score} ({level}). Affected hosts: "
        f"{', '.join(hosts[:10])}. These links should be treated as unsafe "
        f"until verified by other means."
    )


def _build_payload(result: dict, ai_summary: str) -> dict:
    links = result["links"]
    findings = [
        _link_to_finding(link)
        for link in links
        if link.get("severity") in _ACTIONABLE
    ]
    scoring = compute_link_risk(links)
    return {
        "report_type": "links",
        "summary": ai_summary
        or _fallback_summary(links, scoring["overall_score"], scoring["risk_level"]),
        "overall_score": scoring["overall_score"],
        "risk_level": scoring["risk_level"],
        "findings": findings,
        "links": links,
        "filtered_count": result["filtered_count"],
        "truncated_count": result["truncated_count"],
        "quota_exhausted": result["quota_exhausted"],
    }


def _scan_hash(result: dict) -> str:
    """Stable id for a set of links, so re-scanning the same list is a cache hit."""
    scannable = sorted(
        link["url"] for link in result["links"] if link["source"] != "filtered"
    )
    return hashlib.sha256("\n".join(scannable).encode("utf-8")).hexdigest()


def _validate(urls: list[str]) -> None:
    if not urls:
        raise HTTPException(status_code=400, detail="Provide at least one URL.")
    if len(urls) > _REQUEST_URL_LIMIT:
        raise HTTPException(
            status_code=400,
            detail=f"Too many URLs in one request (max {_REQUEST_URL_LIMIT}).",
        )


@router.get("/capabilities")
async def link_capabilities():
    """Report whether link scanning can actually run on this deployment.

    The frontend calls this on load so it can explain an unconfigured provider
    instead of letting someone paste twenty URLs and receive twenty "unknown"
    verdicts, which reads as a working scan that found nothing rather than a
    feature that is switched off.
    """
    provider = get_provider()
    configured = bool(getattr(provider, "configured", False))
    return {
        "enabled": configured,
        "provider": getattr(provider, "name", "unknown"),
        "max_urls": VIRUSTOTAL_MAX_URLS,
        "submission_enabled": bool(configured and VIRUSTOTAL_SUBMIT),
        "reason": None if configured else "provider_not_configured",
    }


@router.post("/scan-links")
async def scan_links(body: LinkScanRequest):
    """Look up reputation for the supplied URLs.

    Unknown URLs come back as ``queued`` rather than as clean. They are not
    submitted here: analysis takes minutes, so that is a separate explicit step.
    """
    _validate(body.urls)

    # Not fatal: an unconfigured provider yields no verdicts, and the response
    # reports every URL as unchecked rather than claiming it is clean.
    if not getattr(get_provider(), "configured", True):
        logger.warning("link scan requested with no provider credentials")

    result = await link_service.scan_urls(body.urls)

    ai_summary = ""
    if body.enrich:
        actionable = [
            link for link in result["links"] if link["severity"] in _ACTIONABLE
        ]
        if actionable:
            findings = [_link_to_finding(link) for link in actionable]
            context = "\n".join(link["url"] for link in result["links"][:40])
            try:
                ai = await generate_report(findings, context)
                ai_summary = ai.get("summary", "")
            except Exception:
                # Prose is a nice-to-have; the deterministic summary still covers it.
                logger.warning("link scan: AI summary failed; using fallback")

    payload = _build_payload(result, ai_summary)

    # Persist so /report can serve a PDF. Reuses the document cache layout, which
    # is why scan_links returns a file_id the existing download button understands.
    file_hash = _scan_hash(result)
    file_id = str(uuid.uuid4())
    storage.save_cached_analysis(file_hash, payload)
    storage.save_file_id_mapping(file_id, file_hash)
    storage.prune_all()

    return {**payload, "file_id": file_id}


@router.post("/scan-links/submit")
async def submit_links(body: LinkScanRequest):
    """Queue unknown URLs for fresh analysis.

    Returns immediately with job ids. Results are collected by re-running
    ``/scan-links`` or ``/scan-links/status`` after a delay.
    """
    _validate(body.urls)
    outcome = await link_service.submit_unknown(body.urls)
    return {
        "submitted": outcome.get("submitted", {}),
        "granted": outcome.get("granted", 0),
        "deferred": outcome.get("deferred", 0),
        "reason": outcome.get("reason"),
    }


@router.post("/scan-links/status")
async def link_status(body: LinkScanRequest):
    """Re-check previously queued URLs.

    Separate from ``/scan-links`` so polling does not consume AI prose calls or
    rewrite the cached report while a scan is still settling.
    """
    _validate(body.urls)
    result = await link_service.scan_urls(body.urls)
    scoring = compute_link_risk(result["links"])
    return {
        "links": result["links"],
        "link_risk_score": scoring["overall_score"],
        "link_risk_level": scoring["risk_level"],
        "checked_count": result["checked_count"],
        "filtered_count": result["filtered_count"],
        "truncated_count": result["truncated_count"],
        "quota_exhausted": result["quota_exhausted"],
        "max_urls": VIRUSTOTAL_MAX_URLS,
    }