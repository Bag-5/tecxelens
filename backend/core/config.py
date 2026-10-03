import os
import re
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / ".env")

API_VERSION = os.getenv("API_VERSION", "v1")

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")

# Tried in order; the first model that returns usable prose wins.
#
# Primary is a paid slug (the account has credits) because zero-cost ":free"
# slugs are unreliable: they return HTTP 429 under load and get retired without
# notice, which previously caused generate_report() to silently return empty
# prose. The free slugs behind it are a safety net so the feature still works
# if credits run out.
#
# Verified working: tools/check_model.py <slug> for existence/pricing,
# tools/_diag_one.py <slug> for an end-to-end prose check.
# Dead or unusable slugs: openai/gpt-oss-20b:free (retired, HTTP 404),
# google/gemma-4-*-it:free, thinkingmachines/inkling*:free,
# apodex/apodex-1.1-mini:free, inclusionai/ling-3.0-flash-sante:free.
OPENROUTER_MODELS = [
    m.strip()
    for m in os.getenv(
        "OPENROUTER_MODELS",
        "nvidia/nemotron-3.5-lightning,"
        "nvidia/nemotron-3-super-120b-a12b:free,"
        "liquid/lfm-2.5-2.6b:free",
    ).split(",")
    if m.strip()
]

# Legacy single-model overrides still apply when explicitly set.
_model_override = os.getenv("OPENROUTER_MODEL", "").strip()
_fallback_override = os.getenv("OPENROUTER_FALLBACK_MODEL", "").strip()
if _model_override:
    OPENROUTER_MODELS = [_model_override] + [
        m for m in OPENROUTER_MODELS if m != _model_override
    ]
if _fallback_override:
    OPENROUTER_MODELS.append(_fallback_override)

AI_TIMEOUT = float(os.getenv("AI_TIMEOUT", "25"))
AI_MAX_TOKENS = int(os.getenv("AI_MAX_TOKENS", "2000"))
AI_ENABLE_FALLBACK = os.getenv("AI_ENABLE_FALLBACK", "true").strip().lower() in {"1", "true", "yes"}

KNOWLEDGE_DIR = BASE_DIR / "knowledge"
KNOWLEDGE_INDEX_PATH = Path(
    os.getenv("KNOWLEDGE_INDEX_PATH", str(BASE_DIR / "knowledge_index.json"))
)

STORAGE_DIR = BASE_DIR / "storage" / "uploads"
CACHE_DIR = BASE_DIR / "storage" / "analysis_cache"

# Shared-host disk budget. PythonAnywhere free caps the whole account at
# 512 MiB including the virtualenv, so uploads and cached analyses are pruned
# oldest-first against these limits by services/storage_service.py.
UPLOAD_MAX_BYTES = int(os.getenv("UPLOAD_MAX_BYTES", str(25 * 1024 * 1024)))
UPLOAD_KEEP_BYTES = int(os.getenv("UPLOAD_KEEP_BYTES", str(120 * 1024 * 1024)))
UPLOAD_KEEP_FILES = int(os.getenv("UPLOAD_KEEP_FILES", "40"))
CACHE_KEEP_BYTES = int(os.getenv("CACHE_KEEP_BYTES", str(30 * 1024 * 1024)))
CACHE_KEEP_FILES = int(os.getenv("CACHE_KEEP_FILES", "200"))

NVD_API_KEY = os.getenv("NVD_API_KEY", "")
NVD_TIMEOUT = float(os.getenv("NVD_TIMEOUT", "8"))
NVD_MAX_KEYWORDS = int(os.getenv("NVD_MAX_KEYWORDS", "3"))

# Link reputation. The provider is pluggable: services/link_providers resolves
# LINK_PROVIDER to an implementation, so adding a second reputation source is a
# new module rather than a rewrite of the callers.
LINK_PROVIDER = os.getenv("LINK_PROVIDER", "virustotal").strip().lower()

VIRUSTOTAL_API_KEY = os.getenv("VIRUSTOTAL_API_KEY", "")
VIRUSTOTAL_TIMEOUT = float(os.getenv("VIRUSTOTAL_TIMEOUT", "10"))

# The Public (free) VirusTotal API allows 4 requests/minute and 500/day, and a
# single scan costs one request per URL. Capping before any network call keeps
# a large paste from silently exhausting the minute budget and returning a wall
# of unexplained failures.
VIRUSTOTAL_MAX_URLS = int(os.getenv("VIRUSTOTAL_MAX_URLS", "25"))

# Submitting an unknown URL asks VirusTotal to analyse it, which takes minutes
# and burns quota. Lookups are free of that cost, so this stays opt-in.
VIRUSTOTAL_SUBMIT = os.getenv("VIRUSTOTAL_SUBMIT", "true").strip().lower() in {
    "1",
    "true",
    "yes",
}

# Anything matching these domains is never sent to a third party, even when a
# user pastes it explicitly.
INTERNAL_DOMAINS = [
    d.strip().lower().lstrip(".")
    for d in os.getenv("INTERNAL_DOMAINS", "").split(",")
    if d.strip()
]

_frontend_origin = os.getenv("FRONTEND_ORIGIN", "*").strip()
FRONTEND_ORIGINS = [origin.strip() for origin in _frontend_origin.split(",") if origin.strip()]
if not FRONTEND_ORIGINS:
    FRONTEND_ORIGINS = ["*"]


def origin_regex(patterns: list[str]) -> str | None:
    """Compile configured origins into a regex, supporting a ``*`` subdomain wildcard.

    Starlette's CORSMiddleware only does exact string matching, so a plain
    allowlist silently breaks every Vercel preview deployment (each gets a unique
    random subdomain) and local development. A browser blocked by CORS reports a
    generic network failure, which makes the cause very hard to spot.

    Supported forms per entry:

    * ``*`` alone means allow everything, handled by the caller.
    * ``https://*.vercel.app`` matches any subdomain depth of vercel.app.
    * anything else is escaped and matched literally.

    A ``*`` expands only to whole DNS labels ("one or more label."), never to
    arbitrary characters. That keeps ``https://evil.com/?x=.vercel.app`` from
    matching, which a naive ``.*`` would happily allow. A bare ``https://vercel.app``
    also does not match, since the wildcard requires at least the dot.

    Returns ``None`` when there is nothing extra to match, i.e. when the caller
    should rely on the plain allowlist alone.
    """
    if not any("*" in pattern for pattern in patterns):
        return None
    if patterns == ["*"]:
        # Allow-all is handled by allow_origins=["*"]; a regex is redundant.
        return None

    compiled: list[str] = []
    for pattern in patterns:
        if "*" not in pattern:
            compiled.append(re.escape(pattern))
            continue
        pieces = pattern.split("*")
        regex = ""
        for index, piece in enumerate(pieces):
            if index > 0:
                # A "*" stands in for one or more whole DNS labels, each ending
                # in a dot, so the "." that follows it in "https://*.vercel.app"
                # is already accounted for and must not be required twice.
                # Requiring at least one label is also what stops a bare
                # "https://vercel.app" from matching.
                regex += r"[a-zA-Z0-9-]+(?:\.[a-zA-Z0-9-]+)*\."
                if piece.startswith("."):
                    piece = piece[1:]
            regex += re.escape(piece)
        compiled.append(regex)

    return "|".join(f"(?:{alt})" for alt in compiled)