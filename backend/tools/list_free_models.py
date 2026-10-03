"""List OpenRouter models currently available on the free tier.

The configured default (openai/gpt-oss-20b:free) has been retired; OpenRouter
returns 404 with a suggested replacement slug. This queries the live catalogue
so the default can be set to something that actually answers.
"""

import asyncio
import json

import httpx

from core.config import OPENROUTER_API_KEY

MODELS_URL = "https://openrouter.ai/api/v1/models"


async def main() -> None:
    async with httpx.AsyncClient(timeout=30.0) as c:
        r = await c.get(MODELS_URL)
        print("status:", r.status_code)
        if r.status_code != 200:
            print(r.text[:400])
            return

        data = r.json().get("data", [])

    free = []
    for m in data:
        mid = m.get("id", "")
        pricing = m.get("pricing", {}) or {}
        prompt = pricing.get("prompt")
        completion = pricing.get("completion")
        # Free tier: zero-cost prompt AND completion.
        if prompt in ("0", 0, 0.0) and completion in ("0", 0, 0.0):
            free.append(m)

    print(f"\n{len(free)} zero-cost models available:\n")
    for m in sorted(free, key=lambda x: x["id"]):
        ctx = m.get("context_length") or "?"
        print(f"  {m['id']:<62} ctx={ctx}")


asyncio.run(main())