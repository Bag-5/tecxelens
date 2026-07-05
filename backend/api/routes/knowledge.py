from fastapi import APIRouter, Query

from services.knowledge_service import search

router = APIRouter()


@router.get("/knowledge/search")
async def knowledge_search(q: str = Query(..., min_length=1, description="Search keyword")):
    matches = search(q)
    return {"matches": matches}
