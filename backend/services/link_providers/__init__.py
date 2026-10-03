"""Link reputation provider registry.

Callers depend on ``get_provider()`` rather than on a concrete source, so the
provider can be swapped through configuration.
"""

import logging

from core.config import LINK_PROVIDER, VIRUSTOTAL_API_KEY, VIRUSTOTAL_TIMEOUT
from services.link_providers.base import LinkProvider

logger = logging.getLogger(__name__)

_PROVIDERS = {
    "virustotal",
}


def build_provider() -> LinkProvider:
    """Instantiate the provider named by ``LINK_PROVIDER``.

    Falls back to VirusTotal rather than raising: a misconfigured provider
    name should not take down document analysis, which does not use links.
    """
    name = (LINK_PROVIDER or "").strip().lower()

    if name not in _PROVIDERS:
        logger.warning(
            "unknown LINK_PROVIDER %r; falling back to virustotal (known: %s)",
            name,
            ", ".join(sorted(_PROVIDERS)),
        )
        name = "virustotal"

    if name == "virustotal":
        from services.link_providers.virustotal import VirusTotalProvider

        return VirusTotalProvider(VIRUSTOTAL_API_KEY, VIRUSTOTAL_TIMEOUT)

    raise RuntimeError(f"LINK_PROVIDER {name!r} has no implementation")


def get_provider() -> LinkProvider:
    return build_provider()