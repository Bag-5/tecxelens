from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes.health import router as health_router
from api.routes.upload import router as upload_router
from api.routes.analyze import router as analyze_router
from api.routes.knowledge import router as knowledge_router
from api.routes.report import router as report_router
from core.config import API_VERSION, FRONTEND_ORIGINS

app = FastAPI(title="TECXE Lens", version=API_VERSION)

app.add_middleware(
    CORSMiddleware,
    allow_origins=FRONTEND_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router, tags=["health"])
app.include_router(upload_router, tags=["upload"])
app.include_router(analyze_router, tags=["analyze"])
app.include_router(knowledge_router, tags=["knowledge"])
app.include_router(report_router, tags=["report"])
