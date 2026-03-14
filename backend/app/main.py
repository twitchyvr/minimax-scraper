"""FastAPI application entry point."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.ai import router as ai_router
from app.api.browse import router as browse_router
from app.api.jobs import router as jobs_router
from app.api.ws import router as ws_router
from app.config import settings
from app.models.schemas import HealthResponse
from app.storage.database import init_db


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Initialize database on startup."""
    settings.output_dir.mkdir(parents=True, exist_ok=True)
    await init_db()
    yield


app = FastAPI(
    title="minimax-scraper",
    description="Markdown documentation scraper with OS-like browser UI",
    version="0.2.1",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(jobs_router)
app.include_router(browse_router)
app.include_router(ai_router)
app.include_router(ws_router)


@app.get("/api/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Health check endpoint."""
    return HealthResponse()
