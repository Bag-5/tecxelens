import json
import logging
import re

import httpx

from core.config import (
    AI_ENABLE_FALLBACK,
    AI_MAX_TOKENS,
    AI_TIMEOUT,
    OPENROUTER_API_KEY,
    OPENROUTER_MODELS,
)

logger = logging.getLogger(__name__)

_FENCE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL)

# Several free/paid models on OpenRouter are reasoning models that spend the
# entire token budget thinking out loud and never emit the JSON body
# (observed: 9434 chars of reasoning, empty content, finish_reason="length").
# Asking OpenRouter to drop reasoning keeps `content` limited to the answer.
_NO_REASONING = {"exclude": True, "effort": "none"}


def _build_prompt(findings: list[dict], text_summary: str) -> str:
    findings_block = ""
    for i, f in enumerate(findings, 1):
        refs_block = ""
        if f.get("references"):
            refs_block = "\n".join(
                f"    - {r['document']} — {r['section']}" for r in f["references"]
            )
            refs_block = f"\n   Matched provisions:\n{refs_block}"

        cves_block = ""
        if f.get("cves"):
            cve_lines = "\n".join(
                f"    - {c['id']} (CVSS {c['cvss_score']}, {c['severity']}, {c['published']}): {c['description']}"
                for c in f["cves"]
            )
            cves_block = f"\n   Relevant CVEs:\n{cve_lines}"

        findings_block += f"""{i}. Title: {f['title']}
   Severity: {f['severity']}
   Reference standard: {f['rule_reference']}{refs_block}{cves_block}

"""

    return f"""You are a cybersecurity compliance report generator. Output valid JSON only, with no markdown fences, no preamble, and no explanation.

Document Context:
{text_summary[:2000]}

For each finding below, write a 2-3 sentence description explaining what it means and why it matters, and a 2-3 sentence recommendation for how to fix it. Then write a 1-2 paragraph executive summary.

Findings:
{findings_block}
Output JSON using this exact schema (do NOT change field names):
{{"summary": "executive summary","details": [{{"description": "what it means","recommendation": "how to fix"}}]}}

The details array must have exactly {len(findings)} entries, in the same order as the findings above."""


def _build_repair_prompt(findings: list[dict], text_summary: str) -> str:
    block = ""
    for i, f in enumerate(findings):
        block += f"""{i + 1}. Title: {f['title']}
   Severity: {f['severity']}
   Reference standard: {f['rule_reference']}

"""
    return f"""You are a cybersecurity compliance report generator. Output valid JSON only.

For every finding below, write a 2-3 sentence description explaining what it means and why it matters, and a 2-3 sentence recommendation for how to fix it. Every field must be a non-empty string.

Findings:
{block}
Document context:
{text_summary[:1000]}

Output exactly this JSON shape with a "details" array of exactly {len(findings)} entries in the same order:
{{"details": [{{"description": "what it means","recommendation": "how to fix"}}]}}"""


_SUMMARY_RE = re.compile(r'"summary"\s*:\s*"(.*?)"\s*,\s*"details"', re.DOTALL)
_DETAIL_RE = re.compile(
    r'"description"\s*:\s*"(.*?)"\s*,\s*"recommendation"\s*:\s*"(.*?)"',
    re.DOTALL,
)


def _salvage(content: str) -> dict | None:
    """Recover the fixed schema from a payload strict JSON parsing rejects.

    Models frequently emit an unescaped double quote inside a description or
    summary, which makes the whole document invalid JSON even though the
    structure and field names are correct. The schema is fixed and flat, so the
    fields can be lifted out directly instead of discarding the response.
    """
    summary_match = _SUMMARY_RE.search(content)
    summary = summary_match.group(1).strip() if summary_match else ""

    details = []
    for desc, rec in _DETAIL_RE.findall(content):
        desc = desc.replace('\\"', '"').replace('\\n', " ").strip()
        rec = rec.replace('\\"', '"').replace('\\n', " ").strip()
        details.append({"description": desc, "recommendation": rec})

    if not summary and not details:
        return None
    return {"summary": summary, "details": details}


def _parse_content(content: str) -> dict | None:
    """Best-effort JSON extraction from a chat completion.

    Models routinely wrap JSON in ``` fences, prepend a sentence, or emit an
    unescaped quote that invalidates the document. Try strict parses first,
    then fall back to the salvage parser.
    """
    candidates = [content.strip()]

    fenced = _FENCE.search(content)
    if fenced:
        candidates.append(fenced.group(1).strip())

    start, end = content.find("{"), content.rfind("}")
    if start != -1 and end > start:
        candidates.append(content[start : end + 1])

    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict) and "details" in parsed:
            return parsed

    salvaged = _salvage(content)
    if salvaged is not None:
        logger.info("salvaged structured output from unparseable response")
    return salvaged


def _normalise_detail(entry: object) -> dict:
    """Coerce a detail entry into {description, recommendation} strings."""
    if not isinstance(entry, dict):
        if isinstance(entry, str):
            return {"description": entry, "recommendation": ""}
        return {"description": "", "recommendation": ""}
    return {
        "description": str(entry.get("description", "") or ""),
        "recommendation": str(entry.get("recommendation", "") or ""),
    }


async def _call(model: str, prompt: str) -> dict | None:
    try:
        async with httpx.AsyncClient(timeout=AI_TIMEOUT) as client:
            resp = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.3,
                    "max_tokens": AI_MAX_TOKENS,
                    "reasoning": _NO_REASONING,
                },
            )

        if resp.status_code != 200:
            logger.warning("openrouter %s -> HTTP %s: %s",
                           model, resp.status_code, resp.text[:200])
            return None

        payload = resp.json()
        choice = (payload.get("choices") or [{}])[0]
        finish = choice.get("finish_reason")
        content = (choice.get("message") or {}).get("content") or ""
        parsed = _parse_content(content)
        if parsed is None:
            logger.warning("openrouter %s -> unparseable (finish=%s, %d chars)",
                           model, finish, len(content))
            return None
        return parsed
    except Exception as exc:
        logger.warning("openrouter %s -> %s: %s", model, type(exc).__name__, exc)
        return None


async def generate_report(findings: list[dict], text: str) -> dict:
    empty = {"summary": "", "details": []}

    if not OPENROUTER_API_KEY or not findings:
        return empty

    text_summary = text[:3000] if text else "(empty document)"

    models = list(OPENROUTER_MODELS)
    if not AI_ENABLE_FALLBACK:
        models = models[:1]

    parsed: dict | None = None
    for model in models:
        parsed = await _call(model, _build_prompt(findings, text_summary))
        if parsed is not None:
            break

    if parsed is None:
        logger.error("all openrouter models failed; empty prose (tried: %s)",
                     ", ".join(models))
        return empty

    details = [_normalise_detail(d) for d in (parsed.get("details") or [])]

    # Models frequently return the right number of entries but leave a field
    # blank, or return too few entirely. One focused follow-up recovers the
    # gaps rather than shipping empty descriptions to the user.
    if len(details) < len(findings) or any(
        not d["description"] or not d["recommendation"] for d in details
    ):
        if models:
            repaired = await _call(models[0], _build_repair_prompt(findings, text_summary))
            if repaired and repaired.get("details"):
                extra = [_normalise_detail(d) for d in repaired["details"]]
                for idx in range(len(findings)):
                    if idx >= len(details):
                        details.append({"description": "", "recommendation": ""})
                    if idx < len(extra):
                        if not details[idx]["description"]:
                            details[idx]["description"] = extra[idx]["description"]
                        if not details[idx]["recommendation"]:
                            details[idx]["recommendation"] = extra[idx]["recommendation"]

    details = details[: len(findings)]

    return {
        "summary": parsed.get("summary", "") or "",
        "details": details,
    }