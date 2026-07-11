import json

import httpx

from core.config import OPENROUTER_API_KEY, OPENROUTER_MODEL, OPENROUTER_FALLBACK_MODEL


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

    return f"""You are a cybersecurity compliance report generator. Output valid JSON only, with no markdown fences or extra text.

Document Context:
{text_summary[:2000]}

For each finding below, write a 2-3 sentence description explaining what it means and why it matters, and a 2-3 sentence recommendation for how to fix it. Then write a 1-2 paragraph executive summary.

Findings:
{findings_block}
Output JSON using this exact schema (do NOT change field names):
{{"summary": "executive summary","details": [{{"description": "what it means","recommendation": "how to fix"}}]}}

The details array must have exactly {len(findings)} entries, in the same order as the findings above."""


async def generate_report(findings: list[dict], text: str) -> dict:
    empty = {"summary": "", "details": []}

    if not OPENROUTER_API_KEY:
        return empty

    text_summary = text[:3000] if text else "(empty document)"
    prompt = _build_prompt(findings, text_summary)

    models = [OPENROUTER_MODEL, OPENROUTER_FALLBACK_MODEL]

    for model in models:
        try:
            async with httpx.AsyncClient(timeout=90.0) as client:
                body = {
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.3,
                    "max_tokens": 1200,
                }

                resp = await client.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                        "Content-Type": "application/json",
                    },
                    json=body,
                )

            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            parsed = json.loads(content)
            summary = parsed.get("summary", "")
            details = parsed.get("details", [])
            return {"summary": summary, "details": details}

        except (KeyError, IndexError, json.JSONDecodeError, Exception):
            continue

    return empty
