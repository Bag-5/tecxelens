import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

API_VERSION = os.getenv("API_VERSION", "v1")

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "meta-llama/llama-3.1-8b-instruct")
OPENROUTER_FALLBACK_MODEL = os.getenv("OPENROUTER_FALLBACK_MODEL", "google/gemma-4-26b-a4b-it:free")

KNOWLEDGE_DIR = Path(__file__).resolve().parent.parent / "knowledge"

NVD_API_KEY = os.getenv("NVD_API_KEY", "")

_frontend_origin = os.getenv("FRONTEND_ORIGIN", "*").strip()
FRONTEND_ORIGINS = [origin.strip() for origin in _frontend_origin.split(",") if origin.strip()]
if not FRONTEND_ORIGINS:
    FRONTEND_ORIGINS = ["*"]
