import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

API_VERSION = os.getenv("API_VERSION", "v1")

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "openai/gpt-oss-20b:free")
OPENROUTER_FALLBACK_MODEL = os.getenv("OPENROUTER_FALLBACK_MODEL", "google/gemma-4-26b-a4b-it:free")

KNOWLEDGE_DIR = Path(__file__).resolve().parent.parent / "knowledge"

NVD_API_KEY = os.getenv("NVD_API_KEY", "")
FRONTEND_ORIGIN = os.getenv("FRONTEND_ORIGIN", "*")
