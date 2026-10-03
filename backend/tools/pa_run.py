"""Run shell commands on PythonAnywhere over the REST API.

The consoles API exposes create/send but console output is only available over
a websocket. To read results without a websocket, each command is run with its
output redirected to a file, which is then fetched through the Files API.

Usage:
    python tools/pa_run.py --token <token> -- "ls -la"
    python tools/pa_run.py --token <token> --cmd-file commands.sh
"""

import argparse
import shlex
import sys
import time
import uuid
from pathlib import Path

import httpx

BASE = "https://www.pythonanywhere.com/api/v0/user"
SCRATCH = "/home/Bag5/.pa_out"


def _headers(token: str) -> dict:
    return {"Authorization": f"Token {token}"}


def ensure_console(token: str, executable: str = "bash") -> str:
    with httpx.Client(timeout=60.0) as c:
        r = c.get(f"{BASE}/Bag5/consoles/", headers=_headers(token))
        if r.status_code == 200:
            for con in r.json():
                if con.get("executable") == executable:
                    return str(con["id"])
        r = c.post(
            f"{BASE}/Bag5/consoles/",
            headers=_headers(token),
            json={"executable": executable, "working_directory": "/home/Bag5"},
        )
        r.raise_for_status()
        return str(r.json()["id"])


def run_command(token: str, console_id: str, command: str, timeout: int = 900) -> tuple[int, str]:
    """Run `command`, return (exit_code, combined_output)."""
    out_file = f"{SCRATCH}/{uuid.uuid4().hex}.txt"

    # `command; echo $? > <rc>` captures the real exit status.
    wrapped = f"{command} > {out_file} 2>&1; echo $? > {out_file}.rc"

    with httpx.Client(timeout=60.0) as c:
        c.post(
            f"{BASE}/Bag5/consoles/{console_id}/send/",
            headers=_headers(token),
            data={"input": wrapped, "interact": "false"},
        )

    deadline = time.time() + timeout
    rc_val = None
    while time.time() < deadline:
        time.sleep(2.0)
        rc = fetch_file(token, out_file + ".rc")
        if rc is not None:
            rc_val = rc.strip()
            break

    output = fetch_file(token, out_file) or ""
    if rc_val is None:
        return 124, output + "\n[timed out waiting for command to finish]"

    # Clean up the scratch files so the account disk does not accumulate.
    for suffix in ("", ".rc"):
        try:
            with httpx.Client(timeout=30.0) as c:
                c.delete(f"{BASE}/Bag5/files/path{out_file}{suffix}",
                         headers=_headers(token))
        except Exception:
            pass

    return (int(rc_val) if rc_val.isdigit() else 1), output


def fetch_file(token: str, path: str) -> str | None:
    with httpx.Client(timeout=120.0) as c:
        r = c.get(f"{BASE}/Bag5/files/path{path}", headers=_headers(token))
    if r.status_code != 200:
        return None
    return r.text


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--token", required=True)
    ap.add_argument("--keep-console", action="store_true")
    ap.add_argument("--timeout", type=int, default=900)
    ap.add_argument("cmd", nargs="?", help="command to run")
    ap.add_argument("--cmd-file", help="file containing one command per line")
    args = ap.parse_args()

    commands: list[str] = []
    if args.cmd:
        commands.append(args.cmd)
    if args.cmd_file:
        commands.extend(
            ln.strip() for ln in Path(args.cmd_file).read_text().splitlines()
            if ln.strip() and not ln.strip().startswith("#")
        )
    if not commands:
        print("no command given", file=sys.stderr)
        return 2

    token = args.token.strip()
    console_id = ensure_console(token)
    print(f"# console {console_id}\n", flush=True)

    worst = 0
    for cmd in commands:
        print(f"$ {cmd}", flush=True)
        rc, out = run_command(token, console_id, cmd, args.timeout)
        if out.strip():
            print(out.rstrip())
        print(f"[exit {rc}]\n", flush=True)
        worst = worst or rc

    if not args.keep_console:
        with httpx.Client(timeout=60.0) as c:
            c.delete(f"{BASE}/Bag5/consoles/{console_id}/", headers=_headers(token))
        print(f"# console {console_id} closed")

    return worst


if __name__ == "__main__":
    sys.exit(main())