"""Assert the link score never claims safety when nothing was actually checked.

A scan that could not look up any URL has no evidence either way. Reporting
100/"Excellent" there asserts the opposite of what is known, which in a security
tool is worse than reporting nothing at all.
"""

import sys

sys.path.insert(0, r"C:\Users\Bag-5\Desktop\tecxelens\backend")

from api.routes.links import _fallback_summary
from services.scoring_engine import compute_link_risk


def L(source: str, severity: str = "none", url: str = "https://x.com/") -> dict:
    return {"url": url, "source": source, "severity": severity, "verdict": "unknown"}


def main() -> int:
    failures: list[str] = []

    cases = [
        ("nothing checked (no key)", [L("queued"), L("filtered")], 0, "Not Assessed"),
        ("all filtered", [L("filtered"), L("filtered")], 0, "Not Assessed"),
        ("checked and all clean", [L("lookup"), L("lookup")], 100, "Excellent"),
        ("one malicious", [L("lookup", "critical"), L("lookup")], 60, "Medium"),
        ("two malicious", [L("lookup", "critical"), L("lookup", "critical"), L("lookup")], 20, "Critical"),
        ("checked clean + unchecked", [L("lookup"), L("queued")], 100, "Excellent"),
        ("empty list", [], 0, "Not Assessed"),
    ]

    print("=== score semantics ===")
    for name, links, want_score, want_level in cases:
        got = compute_link_risk(links)
        ok = got["overall_score"] == want_score and got["risk_level"] == want_level
        print(f"  {'ok  ' if ok else 'FAIL'} {name:<28} -> {got['overall_score']}/{got['risk_level']}")
        if not ok:
            failures.append(f"{name}: wanted {want_score}/{want_level}")

        summary = _fallback_summary(links, got["overall_score"], got["risk_level"])
        checked_any = any(link["source"] == "lookup" for link in links)
        if not checked_any and "No suspicious links were found" in summary:
            failures.append(f"{name}: summary claims a clean scan with nothing checked")
            print("       FAIL summary still says 'No suspicious links were found'")

    print("\n=== summary text when nothing was checked ===")
    links = [L("queued"), L("filtered"), L("filtered")]
    got = compute_link_risk(links)
    summary = _fallback_summary(links, got["overall_score"], got["risk_level"])
    print(f"  {summary}")
    for phrase in ("no links could be checked", "Nothing here has been verified"):
        if phrase.lower() not in summary.lower():
            failures.append(f"summary missing {phrase!r}")
            print(f"  FAIL missing {phrase!r}")

    print("\n=== summary when genuinely checked and clean ===")
    links = [L("lookup"), L("queued")]
    got = compute_link_risk(links)
    summary = _fallback_summary(links, got["overall_score"], got["risk_level"])
    print(f"  {summary}")
    if "No suspicious links were found" not in summary:
        failures.append("clean scan should still say so")
        print("  FAIL clean scan no longer reports its result")

    print("\n=== summary when something is flagged ===")
    links = [L("lookup", "critical", "https://bad.example.org/a"),
             L("lookup", "none", "https://ok.example.org/b")]
    got = compute_link_risk(links)
    summary = _fallback_summary(links, got["overall_score"], got["risk_level"])
    print(f"  {summary}")
    if "1 of 2 checked links" not in summary:
        failures.append("flagged summary should count checked links, not total links")
        print("  FAIL expected '1 of 2 checked links'")

    print()
    if failures:
        print(f"FAILED ({len(failures)})")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("PASS: no score or summary ever claims safety without evidence")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
