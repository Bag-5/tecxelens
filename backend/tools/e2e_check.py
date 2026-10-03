"""End-to-end smoke test: upload -> analyze -> report, plus storage behaviour.

Uses FastAPI's TestClient so it exercises the real routing, parsing, scoring,
NVD enrichment, AI enrichment and ReportLab rendering without binding a port.

Run: python tools/e2e_check.py
"""

import sys
import time
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from fastapi.testclient import TestClient  # noqa: E402

import core.config as config  # noqa: E402
from main import app  # noqa: E402

SAMPLE = """Corporate Access Control Standard

This standard governs how staff accounts are provisioned and how access to
internal systems is granted.

Passwords issued to staff are set by the administrator at creation time and
are not rotated on any schedule.

Administrative access to the management console requires authentication at
the login prompt before the console is displayed.

The helpdesk team operates from a shared account so that tickets can be
assigned to a single operator identifier.

System event logging is switched on for all production hosts by default and
writes entries to the local console.
"""


def main() -> None:
    failures: list[str] = []

    def check(label: str, ok: bool, detail: str = "") -> None:
        print(f"  {'PASS' if ok else 'FAIL'}  {label}{(' - ' + detail) if detail else ''}")
        if not ok:
            failures.append(label)

    client = TestClient(app)

    print("\n[1] health")
    r = client.get("/health")
    check("GET /health -> 200", r.status_code == 200, str(r.json()))

    print("\n[2] path resolution (must not be CWD-relative)")
    check("STORAGE_DIR is absolute", config.STORAGE_DIR.is_absolute(), str(config.STORAGE_DIR))
    check("CACHE_DIR is absolute", config.CACHE_DIR.is_absolute(), str(config.CACHE_DIR))
    check("STORAGE_DIR under BACKEND_DIR", config.STORAGE_DIR.is_relative_to(config.BASE_DIR))

    print("\n[3] filename sanitisation")
    from api.routes.upload import _safe_filename
    for raw, expect in [
        ("../../etc/passwd.pdf", "passwd.pdf"),
        ("C:\\Windows\\System32\\evil.pdf", "evil.pdf"),
        ("....//....//x.pdf", "x.pdf"),
        ("my report (final).pdf", "my_report__final_.pdf"),
        (None, "unnamed"),
    ]:
        got = _safe_filename(raw)
        check(f"_safe_filename({raw!r})", got == expect, f"-> {got!r}")

    print("\n[4] NVD keyword cap")
    from services.nvd_service import extract_tech_keywords
    dense = " ".join(["windows", "linux", "openssl", "tls", "ssh", "python", "java", "ldap", "mysql"])
    kws = extract_tech_keywords(dense)
    check(f"cap at {config.NVD_MAX_KEYWORDS} (got {len(kws)})",
          len(kws) <= config.NVD_MAX_KEYWORDS, str(kws))

    print("\n[5] upload")
    r = client.post("/upload", files={"file": ("policy.txt", SAMPLE.encode(), "text/plain")})
    check("POST /upload -> 200", r.status_code == 200, str(r.status_code))
    file_id = r.json().get("file_id")
    check("file_id present", bool(file_id), str(file_id))
    saved = list(config.STORAGE_DIR.glob(f"{file_id}_*"))
    check("file written under BACKEND_DIR/storage", len(saved) == 1, str(saved))

    print("\n[5b] rejects bad extension + traversal-y name")
    r = client.post("/upload", files={"file": ("evil.exe", b"MZ", "application/octet-stream")})
    check("rejects .exe -> 400", r.status_code == 400, str(r.status_code))

    print("\n[6] analyze (timed)")
    t0 = time.perf_counter()
    r = client.post("/analyze", json={"file_id": file_id})
    elapsed = time.perf_counter() - t0
    check("POST /analyze -> 200", r.status_code == 200, str(r.status_code))
    data = r.json()
    check(f"completed in {elapsed:.1f}s", r.status_code == 200)

    score = data.get("overall_score")
    check("overall_score is int 0-100", isinstance(score, int) and 0 <= score <= 100, str(score))
    check("risk_level present", bool(data.get("risk_level")), str(data.get("risk_level")))
    findings = data.get("findings", [])
    check("findings detected", len(findings) > 0, f"{len(findings)} findings")
    check("scores deterministically (not 0 without cause)",
          not (score == 0 and findings), f"score={score} findings={len(findings)}")

    if findings:
        f0 = findings[0]
        check("finding has title/severity", bool(f0.get("title")) and bool(f0.get("severity")))
        refs = f0.get("references", [])
        check("knowledge references resolved", len(refs) > 0,
              f"{len(refs)} refs e.g. {refs[0]['document'] if refs else 'NONE'}")

        # AI prose must be populated, not silently blank.
        summary_len = len(data.get("summary") or "")
        check("executive summary non-empty", summary_len > 0, f"{summary_len} chars")

        desc_ok = [bool(f.get("description")) for f in findings]
        rec_ok = [bool(f.get("recommendation")) for f in findings]
        check("every finding has a description", all(desc_ok),
              f"{sum(desc_ok)}/{len(findings)}")
        check("every finding has a recommendation", all(rec_ok),
              f"{sum(rec_ok)}/{len(findings)}")

        print(f"        findings        : {len(findings)}")
        print(f"        summary chars   : {summary_len}")
        print(f"        severities      : {[f['severity'] for f in findings]}")
        print(f"        cves (first)    : {len(f0.get('cves') or [])}")

    print("\n[7] cached re-analyze is fast")
    t0 = time.perf_counter()
    r2 = client.post("/analyze", json={"file_id": file_id})
    cached_elapsed = time.perf_counter() - t0
    check("cache hit -> 200", r2.status_code == 200)
    check(f"cache hit faster than cold ({cached_elapsed:.2f}s < {elapsed:.1f}s)",
          cached_elapsed < elapsed, f"{cached_elapsed:.2f}s vs {elapsed:.1f}s")
    check("cached payload identical", r2.json() == data)

    print("\n[8] report")
    r = client.post("/report", json={"file_id": file_id})
    check("POST /report -> 200", r.status_code == 200, str(r.status_code))
    check("content-type is pdf", r.headers.get("content-type") == "application/pdf",
          str(r.headers.get("content-type")))
    body = r.content
    check("PDF magic header", body[:5] == b"%PDF-", str(body[:8]))
    check("PDF non-trivial size", len(body) > 2000, f"{len(body)} bytes")

    print("\n[9] report for unknown id -> 404")
    r = client.post("/report", json={"file_id": "00000000-0000-0000-0000-000000000000"})
    check("unknown file_id -> 404", r.status_code == 404, str(r.status_code))

    print("\n[10] analyze for unknown id -> 404")
    r = client.post("/analyze", json={"file_id": "00000000-0000-0000-0000-000000000000"})
    check("unknown file_id -> 404", r.status_code == 404, str(r.status_code))

    print("\n" + "=" * 60)
    if failures:
        print(f"FAILURES ({len(failures)}):")
        for f in failures:
            print(f"  - {f}")
        sys.exit(1)
    print("ALL CHECKS PASSED")


if __name__ == "__main__":
    main()