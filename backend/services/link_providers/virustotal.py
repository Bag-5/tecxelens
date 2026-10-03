"""VirusTotal implementation of the link reputation provider.

API facts this depends on (v3 reference):

* ``GET /api/v3/urls/{id}`` requires the ``x-apikey`` header. ``id`` is the URL
  as unpadded base64url; VirusTotal canonicalises server-side, so the caller
  does not have to reproduce its canonicalisation rules.
* ``POST /api/v3/urls`` takes form-encoded ``url=...`` and returns an analysis
  id. Analysis is asynchronous and can take minutes.
* The Public API allows 4 requests/minute and 500 requests/day, and its terms
  forbid commercial use.
* Anything queried or submitted becomes part of the public VirusTotal dataset,
  so callers must filter internal URLs before reaching this module.
"""

import base64
import logging

import httpx

from core.config import VIRUSTOTAL_API_KEY, VIRUSTOTAL_TIMEOUT
from services.link_providers.base import ProviderRateLimited, RawVerdict, SubmitAck

logger = logging.getLogger(__name__)

_API = "https://www.virustotal.com/api/v3"
_GUI = "https://www.virustotal.com/gui/url"


def url_id(url: str) -> str:
    """Encode a URL as the identifier VirusTotal expects.

    Unpadded base64url per RFC 4648 section 3.2. Padding is stripped because
    VirusTotal rejects it.
    """
    return base64.urlsafe_b64encode(url.encode("utf-8")).decode("ascii").strip("=")


class VirusTotalProvider:
    name = "virustotal"

    def __init__(self, api_key: str, timeout: float = VIRUSTOTAL_TIMEOUT) -> None:
        self._api_key = api_key
        self._timeout = timeout

    @property
    def configured(self) -> bool:
        return bool(self._api_key)

    def _headers(self) -> dict[str, str]:
        return {"x-apikey": self._api_key}

    async def lookup(self, urls: list[str]) -> dict[str, RawVerdict | None]:
        if not self._api_key:
            logger.warning("virustotal: no API key configured; skipping lookups")
            return {url: None for url in urls}

        results: dict[str, RawVerdict | None] = {}
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            for url in urls:
                results[url] = await self._lookup_one(client, url)
        return results

    async def _lookup_one(
        self, client: httpx.AsyncClient, url: str
    ) -> RawVerdict | None:
        try:
            resp = await client.get(
                f"{_API}/urls/{url_id(url)}", headers=self._headers()
            )
        except Exception as exc:
            # A transport failure is not the same as "no record"; report it as
            # unknown so the caller can offer a submission rather than silently
            # presenting an unchecked URL as clean.
            logger.warning("virustotal lookup %s -> %s", url, exc)
            return None

        if resp.status_code == 404:
            return None  # genuinely not seen before

        if resp.status_code == 429:
            # Capacity refusal, not an unknown URL. Raising lets the caller
            # report an incomplete scan; returning None here would claim
            # VirusTotal has no record of a link we were never allowed to ask
            # about, and would invite the user to submit it for no reason.
            retry_after = None
            ra = resp.headers.get("Retry-After")
            if ra:
                try:
                    retry_after = float(ra)
                except ValueError:
                    retry_after = None
            logger.warning("virustotal lookup %s -> HTTP 429 (quota)", url)
            raise ProviderRateLimited(
                f"VirusTotal rate limit reached while checking {url}",
                retry_after=retry_after,
            )

        if resp.status_code != 200:
            logger.warning(
                "virustotal lookup %s -> HTTP %s: %s",
                url,
                resp.status_code,
                resp.text[:160],
            )
            return None

        try:
            attributes = resp.json()["data"]["attributes"]
        except (KeyError, TypeError, ValueError):
            logger.warning("virustotal lookup %s -> unexpected payload shape", url)
            return None

        stats = attributes.get("last_analysis_stats") or {}
        return {
            "url": url,
            "malicious": int(stats.get("malicious", 0) or 0),
            "suspicious": int(stats.get("suspicious", 0) or 0),
            "harmless": int(stats.get("harmless", 0) or 0),
            "undetected": int(stats.get("undetected", 0) or 0),
            "timeout": int(stats.get("timeout", 0) or 0),
            "categories": attributes.get("categories") or {},
            "reputation": int(attributes.get("reputation", 0) or 0),
            "last_analysis_date": int(attributes.get("last_analysis_date", 0) or 0),
            "permalink": f"{_GUI}/{url_id(url)}",
        }

    async def submit(self, urls: list[str]) -> dict[str, SubmitAck]:
        if not self._api_key:
            return {}

        acks: dict[str, SubmitAck] = {}
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            for url in urls:
                try:
                    resp = await client.post(
                        f"{_API}/urls",
                        headers=self._headers(),
                        data={"url": url},
                    )
                except Exception as exc:
                    logger.warning("virustotal submit %s -> %s", url, exc)
                    continue

                if resp.status_code not in (200, 201):
                    logger.warning(
                        "virustotal submit %s -> HTTP %s: %s",
                        url,
                        resp.status_code,
                        resp.text[:160],
                    )
                    continue

                try:
                    analysis_id = resp.json()["data"]["id"]
                except (KeyError, TypeError, ValueError):
                    continue

                acks[url] = {"url": url, "job_id": analysis_id}
        return acks