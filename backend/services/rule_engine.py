import re

from core.rules import RULES


def _text_contains(text: str, keyword: str) -> bool:
    return re.search(re.escape(keyword), text, re.IGNORECASE) is not None


def evaluate(text: str) -> list[dict]:
    findings: list[dict] = []

    for rule in RULES:
        text_lower = text.lower()

        has_keyword = any(kw in text_lower for kw in rule["keywords"])

        if not has_keyword:
            continue

        has_negation = any(neg in text_lower for neg in rule["negations"])

        if has_negation:
            continue

        findings.append({
            "title": rule["name"],
            "severity": rule["severity"],
            "reference": rule["reference"],
        })

    return findings
