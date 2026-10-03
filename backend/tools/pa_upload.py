"""Upload the TECXE Lens backend to PythonAnywhere via the Files REST API.

Uses the documented endpoint:

    POST https://www.pythonanywhere.com/api/v0/user/<user>/files/path<abs_dest>
    multipart form field: "content"

Directories are created automatically by the API, so no mkdir step is needed.

The knowledge/*.pdf corpus is deliberately NOT uploaded: the pre-built
knowledge_index.json replaces it at runtime, which saves 27 MB on a 512 MiB
account and avoids re-parsing. Regenerate the index locally and re-run this
script if the corpus ever changes.

Usage:
    python tools/pa_upload.py --token <api_token> [--user Bag5] [--dry-run]
"""

import argparse
import mimetypes
import sys
from pathlib import Path

import httpx

BACKEND_DIR = Path(__file__).resolve().parent.parent

# Never sync these: local artefacts, caches, or the PDF corpus.
EXCLUDE_DIRS = {
    ".venv", "__pycache__", ".git", "storage", "knowledge", "node_modules",
    ".pytest_cache", ".mypy_cache",
}
EXCLUDE_FILES = {
    ".env",              # uploaded separately, handled explicitly
    "knowledge_index.json",  # uploaded separately, it is large
    "backend.zip",
}

HOSTS = {"www": "https://www.pythonanywhere.com", "eu": "https://eu.pythonanywhere.com"}


def collect_files(root: Path) -> list[Path]:
    out: list[Path] = []
    for path in sorted(root.rglob("*")):
        if any(part in EXCLUDE_DIRS for part in path.parts):
            continue
        if path.name in EXCLUDE_FILES or path.suffix == ".pyc":
            continue
        if path.is_file():
            out.append(path)
    return out


def upload(host: str, user: str, token: str, local: Path, remote_dir: str,
           dry_run: bool = False) -> bool:
    rel = local.relative_to(BACKEND_DIR).as_posix()
    dest = f"{remote_dir}/{rel}"
    size_kb = local.stat().st_size / 1024

    if dry_run:
        print(f"  [dry] {rel:<42} {size_kb:9.1f} KB -> {dest}")
        return True

    url = f"{host}/api/v0/user/{user}/files/path{dest}"
    mime = mimetypes.guess_type(local.name)[0] or "application/octet-stream"

    try:
        with httpx.Client(timeout=300.0) as client:
            resp = client.post(
                url,
                headers={"Authorization": f"Token {token}"},
                files={"content": (local.name, local.read_bytes(), mime)},
            )
    except Exception as exc:
        print(f"  FAIL  {rel:<42} {type(exc).__name__}: {str(exc)[:80]}")
        return False

    if resp.status_code in (200, 201):
        verb = "updated" if resp.status_code == 200 else "created"
        print(f"  ok    {rel:<42} {size_kb:9.1f} KB ({verb})")
        return True

    print(f"  FAIL  {rel:<42} HTTP {resp.status_code}: {resp.text[:120]}")
    return False


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--token", required=True)
    ap.add_argument("--user", default="Bag5")
    ap.add_argument("--region", choices=["www", "eu"], default="www")
    ap.add_argument("--dest", default="/home/Bag5/tecxelens/backend")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--skip-env", action="store_true")
    args = ap.parse_args()

    host = HOSTS[args.region]
    token = args.token.strip()
    if not token:
        print("empty token", file=sys.stderr)
        return 2

    files = collect_files(BACKEND_DIR)
    extra = [BACKEND_DIR / "knowledge_index.json"]
    env_file = BACKEND_DIR / ".env"

    print(f"user={args.user} region={args.region} dest={args.dest}")
    print(f"code files: {len(files)}")

    ok = True
    for f in files:
        ok &= upload(host, args.user, token, f, args.dest, args.dry_run)

    if env_file.exists() and not args.skip_env:
        print("\n.env (contains secrets):")
        ok &= upload(host, args.user, token, env_file, args.dest, args.dry_run)

    if extra[0].exists():
        print("\nknowledge_index.json (large):")
        ok &= upload(host, args.user, token, extra[0], args.dest, args.dry_run)
    else:
        print("\nknowledge_index.json MISSING - run tools/build_knowledge_index.py first")

    print("\nRESULT:", "all uploads succeeded" if ok else "SOME UPLOADS FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())