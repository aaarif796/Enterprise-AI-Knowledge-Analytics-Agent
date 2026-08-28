"""FastAPI application entry point.

Wires together: routers, CORS, MCP server, static frontend serving,
DB init + demo seeding on startup, and graceful shutdown.
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .api.chat import router as chat_router
from .api.health import router as health_router
from .api.ingest import router as ingest_router
from .core.config import get_settings
from .core.logging import get_logger, setup_logging
from .mcp.server import get_mcp_server

logger = get_logger("app")


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    settings = get_settings()
    logger.info("starting", app=settings.app_name, env=settings.environment)

    # Initialize DB (pgvector) + seed demo analytics data
    try:
        from .services.database import init_db
        from .services.sql_engine import SQLEngine

        init_db()
        if settings.sql_seed_demo:
            SQLEngine().seed_demo()
        logger.info("database_ready")
    except Exception as exc:
        logger.error("db_startup_failed", error=str(exc))

    yield
    logger.info("shutdown")


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version="1.0.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health_router)
    app.include_router(chat_router)
    app.include_router(ingest_router)
    app.include_router(get_mcp_server().router)

    # Serve built frontend if present (production deploy)
    frontend_dist = Path(settings.frontend_dist).resolve()
    if frontend_dist.exists():
        app.mount("/", StaticFiles(directory=str(frontend_dist), html=True), name="frontend")

    return app


app = create_app()
