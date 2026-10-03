"""Provider-agnostic contract for link reputation sources.

A provider answers two questions about a URL:

* what do the engines already know about it (``lookup``)
* can it be queued for fresh analysis (``submit``)

Keeping this narrow means adding a second reputation feed later is a new module
that satisfies ``LinkProvider`` -- not a change to every caller.
"""

from typing import Protocol, TypedDict, runtime_checkable


class RawVerdict(TypedDict):
    """A provider's verdict, before severity mapping.

    Every provider normalises to these keys so link_service and the report
    generator never have to know which source produced them.
    """

    url: str
    malicious: int
    suspicious: int
    harmless: int
    undetected: int
    timeout: int
    categories: dict[str, str]
    reputation: int
    last_analysis_date: int
    permalink: str


class SubmitAck(TypedDict):
    """Acknowledgement that a URL was queued for analysis."""

    url: str
    job_id: str


class ProviderRateLimited(Exception):
    """The provider refused work because its rate limit or quota is exhausted.

    This is deliberately distinct from a URL simply having no record. Returning
    ``None`` for a rate-limited URL would tell the user "VirusTotal has never
    seen this" and offer to submit it, when the truth is "we were not allowed to
    ask". The caller catches this and reports ``quota_exhausted`` so the UI can
    say the scan was incomplete instead of implying the link is merely unknown.
    """

    retry_after: float | None = None

    def __init__(self, message: str = "provider rate limit reached", retry_after: float | None = None):
        super().__init__(message)
        self.retry_after = retry_after


@runtime_checkable
class LinkProvider(Protocol):
    """A source of link reputation data."""

    name: str

    async def lookup(self, urls: list[str]) -> dict[str, RawVerdict | None]:
        """Return a verdict per URL, or ``None`` where the source has no record.

        Implementations must not raise for an unknown URL -- absence is a
        normal outcome and is reported as ``None``. Raise
        :class:`ProviderRateLimited` instead when the refusal is about capacity
        rather than about the URL.
        """
        ...

    async def submit(self, urls: list[str]) -> dict[str, SubmitAck]:
        """Queue URLs for fresh analysis.

        Only URLs with no existing verdict are worth submitting. Results are
        not immediate, so the caller must poll ``lookup`` again later.
        """
        ...