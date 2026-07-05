import re
from pathlib import Path
from collections import Counter

from pypdf import PdfReader

from core.config import KNOWLEDGE_DIR

_cache: dict[str, dict] | None = None


def _extract_text(file_path: Path) -> str:
    reader = PdfReader(file_path)
    parts: list[str] = []
    for page in reader.pages:
        txt = page.extract_text()
        if txt:
            parts.append(txt)
    return "\n".join(parts)


def _split_sections(text: str) -> list[dict]:
    lines = text.split("\n")
    sections: list[dict] = []
    current_label = "General"

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if re.match(r"^(PART|ANNEX|CHAPTER|SECTION)\s", stripped, re.IGNORECASE):
            current_label = stripped[:80]
        sections.append({
            "section": current_label,
            "text": stripped,
        })

    return sections


def _load_all() -> dict[str, dict]:
    global _cache
    if _cache is not None:
        return _cache

    _cache = {}

    if not KNOWLEDGE_DIR.exists():
        return _cache

    for pdf_path in sorted(KNOWLEDGE_DIR.rglob("*.pdf")):
        rel = pdf_path.relative_to(KNOWLEDGE_DIR)
        raw_text = _extract_text(pdf_path)
        sections = _split_sections(raw_text)
        _cache[str(rel)] = {
            "path": str(rel),
            "category": rel.parts[0] if len(rel.parts) > 1 else "general",
            "sections": sections,
        }

    return _cache


def _compute_score(text: str, query_terms: list[str]) -> float:
    text_lower = text.lower()
    word_counts = Counter(text_lower.split())
    hits = sum(1 for t in query_terms if t in text_lower)
    if hits == 0:
        return 0.0
    density = sum(word_counts[t] for t in query_terms if t in word_counts) / max(len(text_lower.split()), 1)
    return round(min(1.0, (hits / len(query_terms)) * 0.7 + density * 0.3), 4)


def search(query: str, top_k: int = 5) -> list[dict]:
    docs = _load_all()
    query_terms = query.lower().split()
    if not query_terms:
        return []

    scored: list[tuple[float, dict]] = []

    for doc_key, doc in docs.items():
        for sec in doc["sections"]:
            score = _compute_score(sec["text"], query_terms)
            if score > 0:
                scored.append((
                    score,
                    {
                        "document": doc_key,
                        "section": sec["section"],
                        "text": sec["text"],
                        "score": score,
                    },
                ))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [s[1] for s in scored[:top_k]]


def init() -> None:
    _load_all()


def reload() -> None:
    global _cache
    _cache = None
