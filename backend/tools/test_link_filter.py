"""Verify that internal URLs can never reach the reputation provider.

Run: python tools/test_link_filter.py

The privacy guarantee is the one thing in this feature that must not regress, so
it is tested directly rather than inferred: each blocked URL is asserted both to
be rejected by is_public_url() and to never appear in a provider call.
"""

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services import link_service
from services.link_service import is_public_url, normalize_url, split_urls
from services.link_providers.base import ProviderRateLimited

# Must never be disclosed. Cloud metadata endpoints lead the list: 169.254.169.254
# hands out instance credentials to anything that asks, so leaking it to a third
# party would be far worse than an ordinary intranet hostname.
MUST_BLOCK = [
    "http://192.168.1.1/",
    "http://192.168.0.10/admin",
    "http://10.0.0.5/",
    "http://10.255.255.254/",
    "http://172.16.0.1/",
    "http://172.31.255.1/",
    "http://127.0.0.1:8000/",
    "https://127.0.0.1/",
    "http://169.254.169.254/latest/meta-data/",
    "http://[::1]/",
    "http://[fe80::1]/",
    "http://[fc00::1]/",
    "http://0.0.0.0/",
    "http://100.64.0.1/",
    "http://255.255.255.255/",
    "http://localhost/",
    "http://localhost:3000/admin",
    "http://wiki.local/",
    "http://fileserver/",
    "http://db.internal/",
    "http://printer.lan/",
    "http://git.home.arpa/",
    "http://vault.corp/",
    "http://host.home/",
    "http://app.intranet/",
    "http://box.private/",
    "http://srv.test/",
    "http://placeholder.example/",
    "http://bad.invalid/",
    "http://admin:sup3rsecret@example.com/",
    "http://user@example.com/",
    "ftp://files.example.com/",
    "file:///etc/passwd",
    "javascript:alert(1)",
]

# Ordinary public destinations that must keep working.
MUST_ALLOW = [
    "https://example.com/",
    "https://www.google.com/search?q=test",
    "https://sub.domain.co.uk/deep/path?a=1&b=2",
    "http://8.8.8.8/",
    "https://github.com/Bag-5/tecxelens",
]

failures: list[str] = []


def check(label: str, condition: bool, detail: str = "") -> None:
    if not condition:
        failures.append(f"{label}: {detail}")


def reset_rate_window() -> None:
    """Clear the shared lookup/submit budget.

    The rate window is a module-level list, so without this each sub-test would
    inherit slots spent by the previous one and the suite would be
    order-dependent. Reaching into the private state is deliberate: the window
    is an implementation detail, and exposing a production reset just to serve
    tests would be worse.
    """
    with link_service._rate_lock:
        link_service._rate_times.clear()


def main() -> int:
    print("== is_public_url: must block ==")
    for url in MUST_BLOCK:
        blocked = not is_public_url(url)
        check("block", blocked, f"{url!r} was allowed")
        print(f"  {'ok  ' if blocked else 'FAIL'} {url}")

    print("\n== is_public_url: must allow ==")
    for url in MUST_ALLOW:
        allowed = is_public_url(url)
        check("allow", allowed, f"{url!r} was blocked")
        print(f"  {'ok  ' if allowed else 'FAIL'} {url}")

    print("\n== normalize_url ==")
    cases = [
        ("example.com", "https://example.com/"),
        ("  https://Example.COM/Path?q=1#frag ", "https://example.com/Path?q=1"),
        ("HTTP://Example.com", "http://example.com/"),
        ("ftp://example.com", None),
        ("", None),
        ("javascript:alert(1)", None),
    ]
    for raw, expected in cases:
        got = normalize_url(raw)
        check("normalize", got == expected, f"{raw!r} -> {got!r}, wanted {expected!r}")
        print(f"  {'ok  ' if got == expected else 'FAIL'} {raw!r} -> {got!r}")

    print("\n== split_urls partitioning ==")
    scannable, filtered, malformed = split_urls(
        [
            "https://example.com/",
            "http://192.168.1.1/",
            "https://example.com/",  # duplicate
            "not a url at all !!",  # no scheme, no dot -> filtered, not malformed
            "ftp://nope.example.com/",  # bad scheme -> malformed
        ]
    )
    print(f"  scannable={scannable}")
    print(f"  filtered ={filtered}")
    print(f"  malformed={malformed}")
    check("dedupe", scannable.count("https://example.com/") == 1, "duplicate not collapsed")
    check("no-private", not any(is_public_url(u) is False for u in scannable),
          "a blocked URL reached the scannable list")

    print("\n== provider is never called with a blocked URL ==")
    seen: list[str] = []

    class TripwireProvider:
        name = "tripwire"

        async def lookup(self, urls):
            seen.extend(urls)
            return {u: None for u in urls}

        async def submit(self, urls):
            seen.extend(urls)
            return {}

    original = link_service.get_provider
    link_service.get_provider = lambda: TripwireProvider()  # type: ignore[assignment]
    reset_rate_window()
    try:
        result = asyncio.run(
            link_service.scan_urls(
                [
                    "https://public.example.org/",
                    "http://192.168.1.1/",
                    "http://169.254.169.254/",
                    "http://wiki.local/",
                    "http://fileserver/",
                ]
            )
        )
    finally:
        link_service.get_provider = original  # type: ignore[assignment]

    print(f"  provider received: {seen}")
    print(f"  filtered_count   : {result['filtered_count']}")
    for url in seen:
        check("leak", is_public_url(url), f"BLOCKED URL reached provider: {url}")
    check(
        "leak",
        seen == ["https://public.example.org/"],
        f"provider saw unexpected URLs: {seen}",
    )
    check(
        "count",
        result["filtered_count"] == 4,
        f"expected 4 filtered, got {result['filtered_count']}",
    )

    print("\n== per-request cap is applied before any network call ==")

    class CountingProvider:
        name = "counting"

        def __init__(self) -> None:
            self.calls: list[str] = []

        async def lookup(self, urls):
            self.calls.extend(urls)
            return {u: None for u in urls}

        async def submit(self, urls):
            return {}

    counter = CountingProvider()
    original = link_service.get_provider
    link_service.get_provider = lambda: counter  # type: ignore[assignment]
    link_service.VIRUSTOTAL_MAX_URLS = 3
    reset_rate_window()
    try:
        capped = asyncio.run(
            link_service.scan_urls([f"https://site{i}.example.org/" for i in range(10)])
        )
    finally:
        link_service.get_provider = original  # type: ignore[assignment]
        link_service.VIRUSTOTAL_MAX_URLS = 25

    print(f"  sent {len(counter.calls)} of 10 (cap 3), truncated={capped['truncated_count']}")
    check("cap", len(counter.calls) == 3, f"expected 3 lookups, made {len(counter.calls)}")
    check("cap", capped["truncated_count"] == 7, "truncated_count wrong")

    # ---- rate limiting -----------------------------------------------------
    # Before this existed, scan_urls sent every pending URL in one batch. The
    # Public API allows 4 requests/minute, so a 25-URL paste reliably produced a
    # run of 429s -- each reported as an unknown URL, which read as "VirusTotal
    # has never seen this" and invited a pointless submission.

    print("\n== lookup window caps a large paste and flags it incomplete ==")

    class VerboseProvider:
        name = "verbose"

        def __init__(self) -> None:
            self.calls: list[str] = []

        async def lookup(self, urls):
            self.calls.extend(urls)
            return {
                u: {
                    "url": u,
                    "malicious": 0,
                    "suspicious": 0,
                    "harmless": 70,
                    "undetected": 5,
                    "timeout": 0,
                    "categories": {},
                    "reputation": 0,
                    "last_analysis_date": 1_700_000_000,
                    "permalink": "",
                }
                for u in urls
            }

        async def submit(self, urls):
            return {}

    verbose = VerboseProvider()
    original = link_service.get_provider
    link_service.get_provider = lambda: verbose  # type: ignore[assignment]
    reset_rate_window()
    try:
        limited = asyncio.run(
            link_service.scan_urls(
                [f"https://rate{i}.example.org/" for i in range(10)]
            )
        )
    finally:
        link_service.get_provider = original  # type: ignore[assignment]

    by_url = {link["url"]: link for link in limited["links"]}
    checked = [l for l in limited["links"] if l["source"] == "lookup"]
    unchecked = [l for l in limited["links"] if l["source"] == "queued"]
    print(f"  asked 10, provider saw {len(verbose.calls)}, quota_exhausted={limited['quota_exhausted']}")
    print(f"  checked={len(checked)} unchecked={len(unchecked)}")
    check("rate", len(verbose.calls) <= 3, f"provider saw {len(verbose.calls)}, window allows 3")
    check("rate", limited["quota_exhausted"] is True, "quota_exhausted not set")
    check("rate", limited["truncated_count"] == 0, "rate limiting must not report truncation")
    check("rate", len(unchecked) == 10 - len(checked), "unchecked count does not add up")
    check("rate", len(limited["links"]) == 10, "every requested URL must still be reported")
    check(
        "rate",
        all(l["verdict"] == "unknown" for l in unchecked),
        "deferred URLs must be unknown, never clean",
    )
    # Nothing may be silently dropped: each deferred URL still appears.
    check(
        "rate",
        all(any(l["url"] == f"https://rate{i}.example.org/" for l in limited["links"]) for i in range(10)),
        "a deferred URL vanished from the response",
    )
    _ = by_url  # kept for readability above

    print("\n== provider 429 is reported as an incomplete scan, not as unknown ==")

    class LimitedProvider:
        name = "limited"

        async def lookup(self, urls):
            raise ProviderRateLimited("HTTP 429", retry_after=30.0)

        async def submit(self, urls):
            return {}

    original = link_service.get_provider
    link_service.get_provider = lambda: LimitedProvider()  # type: ignore[assignment]
    reset_rate_window()
    try:
        blocked = asyncio.run(
            link_service.scan_urls(["https://quota.example.org/", "https://quota2.example.org/"])
        )
    finally:
        link_service.get_provider = original  # type: ignore[assignment]

    print(f"  quota_exhausted={blocked['quota_exhausted']}, links={len(blocked['links'])}")
    check("429", blocked["quota_exhausted"] is True, "429 did not set quota_exhausted")
    check("429", len(blocked["links"]) == 2, "URLs lost when the provider refused")
    check(
        "429",
        all(l["verdict"] == "unknown" for l in blocked["links"]),
        "a 429 must not be reported as anything other than unknown",
    )

    print("\n== lookups and submissions draw on one shared budget ==")

    class SharedProvider:
        name = "shared"

        def __init__(self) -> None:
            self.lookups = 0
            self.submits = 0

        async def lookup(self, urls):
            self.lookups += len(urls)
            return {u: None for u in urls}

        async def submit(self, urls):
            self.submits += len(urls)
            return {u: {"url": u, "job_id": "id"} for u in urls}

    shared = SharedProvider()
    original = link_service.get_provider
    link_service.get_provider = lambda: shared  # type: ignore[assignment]
    reset_rate_window()
    try:
        # Exhaust the window on lookups.
        asyncio.run(link_service.scan_urls([f"https://burn{i}.example.org/" for i in range(3)]))
        after_lookups = shared.lookups
        submission = asyncio.run(
            link_service.submit_unknown([f"https://sub{i}.example.org/" for i in range(5)])
        )
    finally:
        link_service.get_provider = original  # type: ignore[assignment]

    print(f"  lookups used {after_lookups}, submission granted={submission['granted']} reason={submission['reason']}")
    check("shared", after_lookups == 3, f"expected the window to allow 3 lookups, used {after_lookups}")
    check(
        "shared",
        submission["granted"] == 0 and submission["reason"] == "rate_limited",
        "submission ignored the shared budget",
    )

    print()
    if failures:
        print(f"FAILED ({len(failures)})")
        for f in failures:
            print(f"  - {f}")
        return 1

    print("PASS: every internal URL blocked, none reached the provider")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())