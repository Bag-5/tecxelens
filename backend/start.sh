#!/bin/sh
set -e

exec python3 -m uvicorn main:app --host 0.0.0.0 --port "${PORT:-7860}"
