"""Pre-build the knowledge base into a single JSON index.

Parsing the 16 compliance PDFs with pypdf costs 20-90 CPU-seconds, which is
prohibitive on hosts with small CPU budgets (PythonAnywhere free tier allows
100 CPU-seconds per day). Running this script once locally and uploading the
result turns that cold start into a ~0.5s JSON read.

The emitted structure matches knowledge_service._cache exactly, so the runtime
loader can consume it without any behavioural change:

    {
      "<relative/path.pdf>": {
        "path": "<relative/path.pdf>",
        "category": "ghana" | "international" | "general",
        "sections": [{"section": "<label>", "text": "<line>"}, ...]
      }
    }

Usage:
    python tools/build_knowledge_index.py
"""

import json
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from core.config import KNOWLEDGE_DIR, KNOWLEDGE_INDEX_PATH  # noqa: E402
from services.knowledge_service import _extract_text, _split_sections  # noqa: E402


def build() -> dict:
    if not KNOWLEDGE_DIR.exists():
        raise SystemExit(f"Knowledge directory not found: {KNOWLEDGE_DIR}")

    index: dict[str, dict] = {}
    pdfs = sorted(KNOWLEDGE_DIR.rglob("*.pdf"))
    if not pdfs:
        raise SystemExit(f"No PDFs found under {KNOWLEDGE_DIR}")

    for n, pdf_path in enumerate(pdfs, 1):
        rel = pdf_path.relative_to(KNOWLEDGE_DIR)
        print(f"[{n}/{len(pdfs)}] {rel}", flush=True)
        index[str(rel)] = {
            "path": str(rel),
            "category": rel.parts[0] if len(rel.parts) > 1 else "general",
            "sections": _split_sections(_extract_text(pdf_path)),
        }

    return index


def main() -> None:
    index = build()
    total_sections = sum(len(d["sections"]) for d in index.values())

    print(f"\nDocuments:   {len(index)}")
    print(f"Sections:    {total_sections}")
    print(f"Writing:     {KNOWLEDGE_INDEX_PATH}")

    KNOWLEDGE_INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
    with KNOWLEDGE_INDEX_PATH.open("w", encoding="utf-8") as fh:
        json.dump(index, fh, ensure_ascii=False)

    size_mb = KNOWLEDGE_INDEX_PATH.stat().st_size / 1024 / 1024
    print(f"Done:        {size_mb:.1f} MB")


if __name__ == "__main__":
    main()