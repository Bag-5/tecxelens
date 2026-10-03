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
        for path in reversed(entries):
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


def prune_cache() -> int:
    cache_root = CACHE_DIR / "_by_id"
    removed = _prune_dir(cache_root, CACHE_KEEP_BYTES, CACHE_KEEP_FILES * 4)

    # Cache payloads live directly in CACHE_DIR alongside the _by_id folder.
    for path in sorted(CACHE_DIR.glob("*.json")):
        try:
            if time.time() - path.stat().st_mtime < 60.0:
                continue
            path.unlink()
            removed += 1
        except OSError:
            pass

    return removed


def prune_all() -> None:
    prune_uploads()
    prune_cache()