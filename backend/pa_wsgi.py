"""WSGI entrypoint for shared/free hosting (PythonAnywhere, uWSGI).

PythonAnywhere's free tier serves apps through uWSGI, which speaks WSGI.
FastAPI is an ASGI application, so it needs an ASGI -> WSGI adapter to be
mounted directly. ``a2wsgi.WSGIMiddleware`` goes the other way (WSGI app
exposed as ASGI), so it cannot be used here.

``ASGIWSGIAdapter`` below is a small, dependency-free bridge that drives the
ASGI app through a single asyncio event loop per request and returns the
response body to uWSGI.
"""

import asyncio
import os
import sys
import traceback
from datetime import datetime
from http import HTTPStatus
from pathlib import Path

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

os.chdir(BASE_DIR)

from main import app as fastapi_app  # noqa: E402


def _build_scope(environ):
    """Translate a uWSGI environ dict into an ASGI HTTP connection scope."""
    headers = []
    for key, value in environ.items():
        if key.startswith("HTTP_"):
            name = key[5:].replace("_", "-").lower()
            headers.append((name.encode("latin-1"), value.encode("latin-1")))
    if environ.get("CONTENT_TYPE"):
        headers.append((b"content-type", environ["CONTENT_TYPE"].encode("latin-1")))
    if environ.get("CONTENT_LENGTH"):
        headers.append((b"content-length", environ["CONTENT_LENGTH"].encode("latin-1")))

    script_name = environ.get("SCRIPT_NAME", "")
    path_info = environ.get("PATH_INFO", "")
    path = script_name + path_info
    query_string = environ.get("QUERY_STRING", "")
    server_port = int(environ.get("SERVER_PORT") or 80)
    remote_addr = environ.get("REMOTE_ADDR")

    return {
        "type": "http",
        "asgi": {"version": "3.0", "spec_version": "2.3"},
        "http_version": (environ.get("SERVER_PROTOCOL") or "HTTP/1.1").split("/")[-1],
        "method": (environ.get("REQUEST_METHOD") or "GET").upper(),
        "scheme": environ.get("wsgi.url_scheme") or "http",
        "path": path,
        "raw_path": path.encode("latin-1"),
        "query_string": query_string.encode("latin-1"),
        "root_path": script_name,
        "headers": headers,
        "client": (remote_addr, 0) if remote_addr else None,
        "server": (environ.get("SERVER_NAME") or "localhost", server_port),
        "state": {},
    }


def _build_receive(environ):
    """Read the request body up front and hand it out through the ASGI protocol."""
    try:
        length = int(environ.get("CONTENT_LENGTH") or 0)
    except (TypeError, ValueError):
        length = 0

    if length > 0:
        body = environ["wsgi.input"].read(length)
    else:
        body = b""

    state = {"delivered": False}
    never_disconnects = asyncio.Event()

    async def receive():
        if not state["delivered"]:
            state["delivered"] = True
            return {"type": "http.request", "body": body, "more_body": False}
        # Never report a client disconnect. Starlette races its disconnect
        # listener against the response stream and cancels streaming as soon as
        # receive() yields http.disconnect, which would truncate every
        # StreamingResponse (e.g. the PDF report) to zero bytes. Block instead;
        # the surrounding task group cancels this once the response completes.
        await never_disconnects.wait()
        return {"type": "http.disconnect"}

    return receive


class _ResponseCapture:
    """Collects the ASGI response messages emitted by the application."""

    def __init__(self):
        self.status = None
        self.headers = []
        self.chunks = []

    async def __call__(self, message):
        message_type = message.get("type")
        if message_type == "http.response.start":
            self.status = message.get("status", 500)
            self.headers = message.get("headers") or []
        elif message_type == "http.response.body":
            chunk = message.get("body") or b""
            if chunk:
                self.chunks.append(chunk)


_ERROR_LOG = Path(BASE_DIR) / "storage" / "wsgi_errors.log"
_ERROR_LOG_MAX_BYTES = 256 * 1024


def _log_exception(environ) -> None:
    """Append a traceback for an exception that escaped the ASGI app."""
    try:
        _ERROR_LOG.parent.mkdir(parents=True, exist_ok=True)
        if _ERROR_LOG.exists() and _ERROR_LOG.stat().st_size > _ERROR_LOG_MAX_BYTES:
            _ERROR_LOG.write_text("", encoding="utf-8")
        with _ERROR_LOG.open("a", encoding="utf-8") as handle:
            handle.write(
                f"\n--- {environ.get('REQUEST_METHOD', '?')} "
                f"{environ.get('PATH_INFO', '?')} "
                f"{datetime.now().isoformat(timespec='seconds')} ---\n"
            )
            traceback.print_exc(file=handle)
    except Exception:
        pass


class ASGIWSGIAdapter:
    """Expose an ASGI application as a WSGI callable."""

    def __init__(self, asgi_app):
        self.asgi_app = asgi_app

    def __call__(self, environ, start_response):
        capture = _ResponseCapture()

        async def run():
            await self.asgi_app(_build_scope(environ), _build_receive(environ), capture)

        try:
            asyncio.run(run())
        except Exception:
            # Shared hosts do not expose application logs over the API, so an
            # escaped exception here is otherwise invisible: the client sees a
            # bare 500 and the cause is lost. Persist it next to the app so it
            # can be read back over the Files API.
            _log_exception(environ)
            error = b'{"detail":"internal server error"}'
            start_response(
                "500 Internal Server Error",
                [("Content-Type", "application/json"), ("Content-Length", str(len(error)))],
            )
            return [error]

        if capture.status is None:
            error = b'{"detail":"no response produced"}'
            start_response(
                "500 Internal Server Error",
                [("Content-Type", "application/json"), ("Content-Length", str(len(error)))],
            )
            return [error]

        try:
            reason = HTTPStatus(capture.status).phrase
        except ValueError:
            reason = "Unknown"

        headers = [
            (key.decode("latin-1"), value.decode("latin-1"))
            for key, value in capture.headers
            if key.lower() != b"content-length"
        ]
        body = b"".join(capture.chunks)
        headers.append(("Content-Length", str(len(body))))

        start_response(f"{capture.status} {reason}", headers)
        return [body]


application = ASGIWSGIAdapter(fastapi_app)