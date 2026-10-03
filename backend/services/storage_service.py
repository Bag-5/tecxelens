"""Disk-quota housekeeping for shared hosting.

PythonAnywhere's free tier caps the *entire* account at 512 MiB, including the
virtualenv, the source tree and the knowledge index. Without bound, every
upload and every cached analysis stays on disk forever and eventually exhausts
the quota, which surfaces as unrelated-looking failures.

Files are pruned oldest-first (by mtime) against a byte budget and a file-count
budget. Uploads are only needed until an analysis completes -- /report replays
from the analysis cache -- so uploads can be pruned far more aggressively than
cache entries.

Pruning runs after uploads and after analyses. It is a cheap scandir on a
directory holding tens of files, so there is no need to throttle it.
"""

import json
import time
from pathlib import Path

from core.config import (
    CACHE_KEEP_BYTES,
    CACHE_KEEP_FILES,
    STORAGE_DIR,
    CACHE_DIR,
    UPLOAD_KEEP_BYTES,
    UPLOAD_KEEP_FILES,
)


def _prune_dir(
    directory: Path,
    keep_bytes: int,
    keep_files: int,
    grace_seconds: float = 60.0,
) -> int:
    """Delete oldest entries in `directory` until both budgets are satisfied.

    Entries modified within `grace_seconds` are never removed, so a file that
    was just written cannot be deleted out from under a request in flight.
    """
    if not directory.exists():
        return 0

    try:
        entries = [p for p in directory.iterdir() if p.is_file()]
    except OSError:
        return 0

    if not entries:
        return 0

    now = time.time()
    entries.sort(key=lambda p: p.stat().st_mtime)

    total = sum(p.stat().st_size for p in entries)
    removed = 0

    # Walk oldest-first, stopping once we are inside both budgets or run out of
    # files that are old enough to touch.
    for idx, path in enumerate(entries):
        if total <= keep_bytes and (len(entries) - removed) <= keep_files:
            break
        if now - path.stat().st_mtime < grace_seconds:
            continue
        try:
            total -= path.stat().st_size
            path.unlink()
            removed += 1
        except OSError:
            pass

    # A single file larger than the whole budget can never be satisfied by
    # pruning alone; drop the oldest entries regardless once we exceed it.
    if total > keep_bytes and entries:
        for path in entries:
            if total <= keep_bytes:
                break
            try:
                total -= path.stat().st_size
                path.unlink()
                removed += 1
            except OSError:
                pass

    return removed


def prune_uploads() -> int:
    return _prune_dir(STORAGE_DIR, UPLOAD_KEEP_BYTES, UPLOAD_KEEP_FILES)


# --- analysis cache payloads -------------------------------------------------
# These live here rather than in the route because /report resolves a file_id
# through them and both /analyze and /scan-links write them. Keeping the layout
# in one module means a change to the on-disk shape cannot drift between the
# route that writes and the route that reads.


def cache_payload_path(file_hash: str) -> Path:
    return CACHE_DIR / f"{file_hash}.json"


def file_id_mapping_path(file_id: str) -> Path:
    return CACHE_DIR / "_by_id" / f"{file_id}.json"


def load_cached_analysis(file_hash: str) -> dict | None:
    path = cache_payload_path(file_hash)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def save_cached_analysis(file_hash: str, payload: dict) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_payload_path(file_hash).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def save_file_id_mapping(file_id: str, file_hash: str) -> None:
    """Point an opaque file_id at a cached payload.

    /report resolves reports exclusively through this mapping, so any scan that
    should yield a downloadable PDF must write one.
    """
    path = file_id_mapping_path(file_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"file_hash": file_hash}, ensure_ascii=False),
        encoding="utf-8",
    )


def prune_cache() -> int:
    """Evict cached analyses oldest-first against the cache budget.

    Both the payload files and the file_id mappings are budgeted rather than
    aged out. Ageing payloads out on a timer looks tidy but breaks /report:
    the mapping and its payload are the only record of an analysis, so a user
    who comes back to download the PDF more than a minute later gets a 409
    "Cached analysis data is missing" for an analysis that succeeded.
    Retention is therefore driven by CACHE_KEEP_BYTES/CACHE_KEEP_FILES, with
    the grace window only protecting entries from in-flight requests.
    """
    removed = _prune_dir(CACHE_DIR, CACHE_KEEP_BYTES, CACHE_KEEP_FILES)
    removed += _prune_dir(
        CACHE_DIR / "_by_id", CACHE_KEEP_BYTES, CACHE_KEEP_FILES * 4
    )
    return removed


def prune_all() -> None:
    prune_uploads()
    prune_cache()