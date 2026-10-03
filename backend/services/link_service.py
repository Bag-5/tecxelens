"""Link reputation orchestration.

Provider-agnostic: this module owns URL hygiene, the privacy filter, caching
and severity mapping, and delegates the actual lookups to whichever
``LinkProvider`` is configured.

The privacy filter is the important part. VirusTotal states that any URL
submitted or queried becomes part of a publicly accessible dataset, so nothing
leaves this process without passing ``is_public_url`` first. We never fetch the
URLs ourselves -- the provider does that -- so the only risk handled here is
disclosure, not SSRF.
"""

import ipaddress
import logging
import re
import threading
import time
from urllib.parse import urlsplit, urlunsplit

from core.config import (
    INTERNAL_DOMAINS,
    VIRUSTOTAL_MAX_URLS,
    VIRUSTOTAL_SUBMIT,
)
from services.link_providers import get_provider
from services.link_providers.base import ProviderRateLimited, RawVerdict

logger = logging.getLogger(__name__)

# Hostnames that never resolve on the public internet. A URL using one of
# these is either an intranet reference or a typo, and in neither case should it
# be disclosed to a third party.
_INTERNAL_TLDS = frozenset(
    {
        "local",
        "localhost",
        "internal",
        "intranet",
        "lan",
        "home",
        "corp",
        "private",
        "test",
        "example",
        "invalid",
        "home.arpa",
    }
)

# A bare hostname with no dot ("wiki", "fileserver") is an intranet name.
_BARE_HOSTNAME = re.compile(r"^[a-z0-9-]+$")

# Address space that is not globally routable. ipaddress.is_private does not
# cover all of it -- 100.64.0.0/10 (RFC 6598 shared address space) is neither
# private nor reserved by that API -- so the ranges that matter are listed
# explicitly rather than inferred.
_NON_ROUTABLE_NETWORKS = tuple(
    ipaddress.ip_network(cidr)
    for cidr in (
        "0.0.0.0/8",          # "this network"
        "10.0.0.0/8",         # RFC 1918
        "100.64.0.0/10",      # RFC 6598 carrier-grade NAT
        "127.0.0.0/8",        # loopback
        "169.254.0.0/16",     # link-local, incl. cloud metadata at .169.254
        "172.16.0.0/12",      # RFC 1918
        "192.0.0.0/24",       # IETF protocol assignments
        "192.0.2.0/24",       # TEST-NET-1
        "192.168.0.0/16",     # RFC 1918
        "198.18.0.0/15",      # benchmarking
        "198.51.100.0/24",    # TEST-NET-2
        "203.0.113.0/24",     # TEST-NET-3
        "224.0.0.0/4",        # multicast
        "240.0.0.0/4",        # reserved, incl. 255.255.255.255
        "::/128",             # unspecified
        "::1/128",            # loopback
        "fc00::/7",           # unique local
        "fe80::/10",          # link-local
    )
)

# Distinguishes "host:port" (no scheme) from "scheme:rest". A scheme may
# legally contain dots, so the tell is whether what follows the colon is all
# digits.
_SCHEME_PREFIX = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.\-]*:")
_PORT = re.compile(r"^[0-9]+$")

_CACHE_TTL_SECONDS = 24 * 60 * 60
_cache: dict[str, tuple[float, dict]] = {}
_cache_lock = threading.Lock()


# --------------------------------------------------------------------------
# URL hygiene
# --------------------------------------------------------------------------


def normalize_url(raw: str) -> str | None:
    """Return a canonical URL, or ``None`` if it is not usable.

    Canonicalisation here is deliberately minimal -- only enough to make cache
    keys stable and to look sane in a report. The provider performs its own
    canonicalisation, and duplicating its rules would risk producing an
    identifier that misses an existing verdict.
    """
    if not raw:
        return None

    candidate = raw.strip().strip("<>\"'")
    if not candidate:
        return None

    # Users paste bare hosts constantly; assume https rather than rejecting.
    # Only prepend when there is genuinely no scheme, otherwise "javascript:..."
    # would be mangled into a bogus https URL instead of being rejected.
    if "://" not in candidate:
        scheme_match = _SCHEME_PREFIX.match(candidate)
        if not scheme_match or _PORT.match(
            candidate[scheme_match.end() :].split("/", 1)[0]
        ):
            candidate = f"https://{candidate}"

    try:
        parts = urlsplit(candidate)
    except ValueError:
        return None

    if parts.scheme.lower() not in {"http", "https"}:
        return None
    if not parts.hostname:
        return None
    if len(candidate) > 2048:
        return None

    # A fragment never reaches the server, so dropping it keeps two links to the
    # same page sharing one cache entry.
    return urlunsplit(
        (
            parts.scheme.lower(),
            parts.netloc.lower(),
            parts.path or "/",
            parts.query,
            "",
        )
    )


def is_public_url(url: str) -> bool:
    """Whether a URL may be disclosed to the reputation provider.

    Blocks private and reserved IP literals, internal TLDs, bare intranet
    hostnames, URLs carrying embedded credentials, and anything matching
    ``INTERNAL_DOMAINS``.
    """
    try:
        parts = urlsplit(url)
    except ValueError:
        return False

    if parts.scheme.lower() not in {"http", "https"}:
        return False

    # Embedded credentials are a phishing pattern in their own right, and they
    # would leak a secret to the provider along with the URL.
    if parts.username or parts.password:
        return False

    try:
        host = parts.hostname
    except ValueError:
        return False
    if not host:
        return False

    host = host.rstrip(".").lower()

    # IP literal: reject anything not globally routable.
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_reserved
            or ip.is_multicast
            or ip.is_unspecified
        ):
            return False
        return not any(ip in net for net in _NON_ROUTABLE_NETWORKS)

    if _BARE_HOSTNAME.match(host):
        return False

    labels = host.split(".")
    if len(labels) < 2:
        return False

    if labels[-1] in _INTERNAL_TLDS:
        return False
    if len(labels) >= 2 and ".".join(labels[-2:]) in _INTERNAL_TLDS:
        return False

    for internal in INTERNAL_DOMAINS:
        if host == internal or host.endswith(f".{internal}"):
            return False

    return True


# --------------------------------------------------------------------------
# Cache
# --------------------------------------------------------------------------


def _cache_get(url: str) -> dict | None:
    with _cache_lock:
        entry = _cache.get(url)
        if entry is None:
            return None
        stored_at, verdict = entry
        if time.time() - stored_at > _CACHE_TTL_SECONDS:
            _cache.pop(url, None)
            return None
        return verdict


def _cache_put(url: str, verdict: dict) -> None:
    with _cache_lock:
        _cache[url] = (time.time(), verdict)


# --------------------------------------------------------------------------
# Severity
# --------------------------------------------------------------------------


def severity_for(verdict: dict) -> str:
    """Map engine counts onto the existing finding vocabulary.

    Returns ``"none"`` for clean or unchecked links so they can be displayed
    without affecting the score.
    """
    malicious = verdict.get("malicious", 0) or 0
    suspicious = verdict.get("suspicious", 0) or 0
    harmless = verdict.get("harmless", 0) or 0

    if malicious >= 3:
        return "critical"
    if malicious >= 1:
        return "high"
    if suspicious >= 1:
        return "medium"
    if harmless == 0:
        return "low"
    return "none"


def verdict_label(verdict: dict) -> str:
    if verdict.get("malicious", 0) >= 1:
        return "malicious"
    if verdict.get("suspicious", 0) >= 1:
        return "suspicious"
    return "harmless"


# --------------------------------------------------------------------------
# Rate limiting
# --------------------------------------------------------------------------

# The Public API allows 4 requests/minute and counts lookups and submissions
# against the same budget, so both draw from one window. Staying at 3 leaves
# headroom for the polling path, which re-checks URLs while a submitted
# analysis settles.
#
# The window is per-process and in-memory. That is correct for the single-worker
# PythonAnywhere deployment this runs on, and it is deliberately not presented
# as a distributed limiter: if this ever runs multi-worker or multi-instance,
# the budget becomes per-process and the provider's own 429 becomes the real
# backstop. That is why ProviderRateLimited is handled rather than ignored.
_RATE_WINDOW_SECONDS = 60.0
_RATE_MAX_PER_WINDOW = 3
_rate_times: list[float] = []
_rate_lock = threading.Lock()


def _reserve_slots(count: int) -> int:
    """Claim up to ``count`` request slots, returning how many were granted."""
    now = time.time()
    with _rate_lock:
        while _rate_times and now - _rate_times[0] > _RATE_WINDOW_SECONDS:
            _rate_times.pop(0)
        granted = max(0, min(count, _RATE_MAX_PER_WINDOW - len(_rate_times)))
        for _ in range(granted):
            _rate_times.append(now)
    return granted


def _reserve_submit_slots(count: int) -> int:
    """Backwards-compatible alias; submissions share the lookup budget."""
    return _reserve_slots(count)


# --------------------------------------------------------------------------
# Orchestration
# --------------------------------------------------------------------------


def split_urls(raw_urls: list[str]) -> tuple[list[str], list[str], list[str]]:
    """Partition input into (scannable, filtered_out, malformed).

    Order is preserved and duplicates collapse, so a user who pastes the same
    link twice is charged for it once.
    """
    scannable: list[str] = []
    filtered: list[str] = []
    malformed: list[str] = []
    seen: set[str] = set()

    for raw in raw_urls or []:
        url = normalize_url(raw)
        if url is None:
            malformed.append(raw)
            continue
        if url in seen:
            continue
        seen.add(url)
        if is_public_url(url):
            scannable.append(url)
        else:
            filtered.append(url)

    return scannable, filtered, malformed


async def scan_urls(urls: list[str]) -> dict:
    """Look up verdicts, honouring the cache and the per-request URL cap.

    Returns ``links`` (every URL the user asked about, including filtered and
    unchecked ones), ``checked_count`` and ``truncated_count``.
    """
    scannable, filtered, malformed = split_urls(urls)

    truncated = 0
    if len(scannable) > VIRUSTOTAL_MAX_URLS:
        truncated = len(scannable) - VIRUSTOTAL_MAX_URLS
        scannable = scannable[:VIRUSTOTAL_MAX_URLS]
        logger.warning(
            "capping %d URLs to VIRUSTOTAL_MAX_URLS=%d",
            len(scannable) + truncated,
            VIRUSTOTAL_MAX_URLS,
        )

    results: dict[str, dict] = {}
    pending: list[str] = []

    for url in scannable:
        cached = _cache_get(url)
        if cached is not None:
            results[url] = dict(cached, source="lookup")
        else:
            pending.append(url)

    quota_exhausted = False
    if pending:
        # Ask the provider only for as many URLs as the current window allows.
        # The remainder fall through to the "unknown" branch below, so a large
        # paste is reported as partially unchecked instead of being silently
        # dropped or, worse, hammering the API into a 429.
        granted = _reserve_slots(len(pending))
        if granted < len(pending):
            quota_exhausted = True
            logger.info(
                "lookup window allows %d of %d pending URLs; %d deferred",
                granted,
                len(pending),
                len(pending) - granted,
            )

        batch = pending[:granted]
        raw: dict[str, RawVerdict | None] = {}
        if batch:
            provider = get_provider()
            try:
                raw = await provider.lookup(batch)
            except ProviderRateLimited as exc:
                # Capacity refusal mid-batch. Everything unchecked stays
                # unchecked and the response is flagged so the UI can say the
                # scan was incomplete rather than implying the links are unknown
                # to VirusTotal.
                quota_exhausted = True
                logger.warning("link scan rate limited: %s", exc)

        for url in pending:
            verdict = raw.get(url)
            if verdict is None:
                results[url] = {
                    "url": url,
                    "verdict": "unknown",
                    "severity": "none",
                    "malicious": 0,
                    "suspicious": 0,
                    "harmless": 0,
                    "undetected": 0,
                    "timeout": 0,
                    "categories": {},
                    "reputation": 0,
                    "last_analysis_date": 0,
                    "permalink": "",
                    "source": "queued",
                }
                continue

            verdict = dict(verdict)
            verdict["severity"] = severity_for(verdict)
            verdict["verdict"] = verdict_label(verdict)
            verdict["source"] = "lookup"
            results[url] = verdict
            _cache_put(url, verdict)

    for url in filtered:
        results[url] = {
            "url": url,
            "verdict": "not_scanned",
            "severity": "none",
            "malicious": 0,
            "suspicious": 0,
            "harmless": 0,
            "undetected": 0,
            "timeout": 0,
            "categories": {},
            "reputation": 0,
            "last_analysis_date": 0,
            "permalink": "",
            "source": "filtered",
        }

    links = [results[url] for url in scannable] + [
        results[url] for url in filtered
    ]

    return {
        "links": links,
        "filtered_count": len(filtered),
        "malformed": malformed,
        "truncated_count": truncated,
        "checked_count": sum(1 for link in links if link["source"] == "lookup"),
        "quota_exhausted": quota_exhausted,
    }


async def submit_unknown(urls: list[str]) -> dict:
    """Queue unchecked public URLs for fresh analysis.

    Analysis takes minutes, so this only requests the work and returns job ids;
    the caller re-runs ``scan_urls`` later to collect verdicts.
    """
    if not VIRUSTOTAL_SUBMIT:
        return {"submitted": {}, "granted": 0, "reason": "submission_disabled"}

    scannable, filtered, _ = split_urls(urls)
    if len(scannable) > VIRUSTOTAL_MAX_URLS:
        scannable = scannable[:VIRUSTOTAL_MAX_URLS]

    unknown = [url for url in scannable if _cache_get(url) is None]
    if not unknown:
        return {"submitted": {}, "granted": 0, "reason": "nothing_to_submit"}

    granted = _reserve_submit_slots(len(unknown))
    if granted == 0:
        logger.info("submission window full; %d URLs deferred", len(unknown))
        return {"submitted": {}, "granted": 0, "reason": "rate_limited"}

    provider = get_provider()
    acks = await provider.submit(unknown[:granted])
    logger.info("submitted %d URL(s) for analysis", len(acks))
    return {
        "submitted": acks,
        "granted": len(acks),
        "deferred": max(0, len(unknown) - granted),
        "reason": None,
    }