"""Health + config endpoints."""
from __future__ import annotations

import asyncio

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from ..core.config import get_settings
from ..core.model_router import ModelRouter
from ..core.schemas import ConfigResponse, HealthResponse, ModelInfo
from ..services.database import init_db
from ..services.sql_engine import SQLEngine

router = APIRouter(tags=["meta"])


@router.get("/", response_model=HealthResponse)
async def health() -> HealthResponse:
    settings = get_settings()
    services: dict[str, str] = {}

    async def check_postgres() -> None:
        try:
            await asyncio.wait_for(asyncio.to_thread(init_db), timeout=8)
            await asyncio.wait_for(asyncio.to_thread(SQLEngine().schema_description), timeout=8)
            services["postgres"] = "ok"
        except Exception as exc:
            services["postgres"] = f"unavailable: {type(exc).__name__}"

    async def check_redis() -> None:
        try:
            from ..core.cache import get_cache
            cache = get_cache()
            services["redis"] = "ok" if cache._client else "memory-fallback"
        except Exception as exc:
            services["redis"] = f"error: {exc}"

    await asyncio.gather(check_postgres(), check_redis())
    services["model_gateway"] = "configured"
    return HealthResponse(
        status="ok",
        environment=settings.environment,
        version="1.0.0",
        services=services,
    )


@router.get("/api/config", response_model=ConfigResponse)
async def config() -> ConfigResponse:
    settings = get_settings()
    router = ModelRouter()
    models = [
        ModelInfo(model=m, provider=p, free=f)
        for m, p, f in router.available_models()
    ]
    return ConfigResponse(
        default_model=router.default(),
        active_providers=sorted({p for _, p, _ in router.available_models()}),
        routes=router.routed_models(),
        available_models=models,
    )
