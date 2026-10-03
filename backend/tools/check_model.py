"""Check whether a specific model slug exists on OpenRouter and what it costs.

Prints pricing for the requested slug plus any close matches, so a model id
can be validated before it is hard-coded into config.
"""

import asyncio
import json
import sys

import httpx

QUERY = sys.argv[1] if len(sys.argv) > 1 else "qwen3.7"


async def main() -> None:
    async with httpx.AsyncClient(timeout=30.0) as c:
        r = await c.get("https://openrouter.ai/api/v1/models")
        r.raise_for_status()
        models = r.json().get("data", [])

    print(f"exact slug '{QUERY}':")
    exact = [m for m in models if m.get("id") == QUERY]
    if not exact:
        print("  NOT FOUND in catalogue\n")
    for m in exact:
        print(f"  {m['id']}  pricing={m.get('pricing')}  ctx={m.get('context_length')}")

    print(f"\nclose matches containing '{QUERY.lower()}':")
    hits = [m for m in models if QUERY.lower() in m.get("id", "").lower()]
    if not hits:
        print("  none")
    for m in sorted(hits, key=lambda x: x["id"]):
        p = m.get("pricing", {}) or {}
        zero = p.get("prompt") in ("0", 0, 0.0) and p.get("completion") in ("0", 0, 0.0)
        print(f"  {'FREE' if zero else 'paid'}  {m['id']:<52} "
              f"prompt={p.get('prompt')} completion={p.get('completion')}")

    print("\nall qwen slugs currently offered:")
    for m in sorted((x for x in models if "qwen" in x.get("id", "").lower()), key=lambda x: x["id"]):
        p = m.get("pricing", {}) or {}
        zero = p.get("prompt") in ("0", 0, 0.0) and p.get("completion") in ("0", 0, 0.0)
        print(f"  {'FREE' if zero else 'paid'}  {m['id']:<52} ctx={m.get('context_length')}")


asyncio.run(main())