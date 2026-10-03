"""WSGI entrypoint for shared hosting (PythonAnywhere).

PythonAnywhere serves WSGI only — there is no uvicorn process to bind a port
with — so the ASGI app is wrapped with a2wsgi.WSGIMiddleware.

Two things here are load-bearing:

1. `sys.path` must contain the backend directory. main.py uses flat absolute
   imports (`from core.config import ...`) with no package install, so the
   directory itself has to be importable.

2. `os.chdir(BASE_DIR)`. Historically every storage path was a bare relative
   `Path("storage")`, which resolves against the process CWD. On shared hosts
   the CWD is the home directory, not the project, so `mkdir(exist_ok=True)`
   would silently scatter uploads and cache outside the project tree.

Note there is deliberately no knowledge-base pre-warm here. PythonAnywhere
pings the app with a single request after each reload and allows only 20
seconds for that first response; eagerly parsing the corpus at import time
would fail every reload. The pre-built knowledge_index.json keeps import fast
instead.
"""

import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

os.chdir(BASE_DIR)

from a2wsgi import WSGIMiddleware  # noqa: E402

from main import app as fastapi_app  # noqa: E402

application = WSGIMiddleware(fastapi_app)