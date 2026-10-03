"""Verify the pre-built JSON index produces identical search results to parsing
the PDFs directly, and report the load-time difference.

Run: python tools/verify_knowledge_index.py
"""

import shutil
import sys
import time
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

import core.config as config  # noqa: E402
from services import knowledge_service as ks  # noqa: E402

QUERIES = [
    "Weak Password Management ISO 27001 A.9.4.2",
    "multi-factor authentication ISO 27001 A.9.4.2",
    "log retention period",
    "shared user accounts",
    "weak authentication mechanism",
    "access control policy",
]


def _search_all() -> dict[str, list[tuple[str, str, float]]]:
    out: dict[str, list[tuple[str, str, float]]] = {}
    for q in QUERIES:
        out[q] = [
            (r["document"], r["section"], r["score"]) for r in ks.search(q, top_k=5)
        ]
    return out


def main() -> None:
    index_path = config.KNOWLEDGE_INDEX_PATH
    if not index_path.exists():
        raise SystemExit(f"Index not built: {index_path}")

    # --- JSON path (what will run in production) ---
    ks.reload()
    t0 = time.perf_counter()
    json_docs = ks._load_all()
    json_load = time.perf_counter() - t0
    json_sections = sum(len(d["sections"]) for d in json_docs.values())
    print(f"JSON   load: {json_load:.3f}s  docs={len(json_docs)} sections={json_sections}")
    json_results = _search_all()

    # --- PDF path (previous behaviour) ---
    # Move the index aside so _load_all() falls back to parsing the corpus.
    backup = index_path.with_suffix(".json.bak")
    shutil.move(str(index_path), str(backup))
    config.KNOWLEDGE_INDEX_PATH = backup  # keep it out of the way
    ks.reload()

    t0 = time.perf_counter()
    pdf_docs = ks._load_all()
    pdf_load = time.perf_counter() - t0
    print(f"PDF    load: {pdf_load:.3f}s  docs={len(pdf_docs)}")

    # Search timing on the PDF path (index is already warm at this point).
    t0 = time.perf_counter()
    _search_all()
    print(f"PDF    search: {time.perf_counter() - t0:.3f}s (warm)")

    pdf_results = _search_all()

    # Restore.
    shutil.move(str(backup), str(index_path))
    config.KNOWLEDGE_INDEX_PATH = index_path
    ks.reload()

    print()
    ok = True
    if set(json_docs) != set(pdf_docs):
        print(f"MISMATCH doc keys: json-only={set(json_docs) - set(pdf_docs)} "
              f"pdf-only={set(pdf_docs) - set(json_docs)}")
        ok = False

    for doc in json_docs:
        if len(json_docs[doc]["sections"]) != len(pdf_docs[doc]["sections"]):
            print(f"MISMATCH sections in {doc}: "
                  f"json={len(json_docs[doc]['sections'])} pdf={len(pdf_docs[doc]['sections'])}")
            ok = False
            break

    for q in QUERIES:
        if json_results[q] != pdf_results[q]:
            ok = False
            print(f"MISMATCH results for {q!r}")
            print(f"  json: {json_results[q]}")
            print(f"  pdf : {pdf_results[q]}")

    if ok:
        print("PARITY OK - JSON index matches PDF parsing exactly")
        print(f"\nSpeedup: {pdf_load / json_load:.0f}x faster load "
              f"({pdf_load:.1f}s -> {json_load:.2f}s)")
    else:
        print("PARITY FAILED")
        sys.exit(1)


if __name__ == "__main__":
    main()