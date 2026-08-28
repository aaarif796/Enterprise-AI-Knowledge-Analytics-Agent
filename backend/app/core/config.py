"""Application configuration loader.

Loads environment variables (via pydantic-settings) and the model
configuration YAML (providers + task route table). This is the central
configuration for the whole application.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

import yaml
from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Load .env from project root
BACKEND_DIR = Path(__file__).resolve().parent.parent  # backend/
PROJECT_ROOT = BACKEND_DIR.parent
load_dotenv(PROJECT_ROOT / ".env")


class Settings(BaseSettings):
    """Environment-driven application settings."""

    model_config = SettingsConfigDict(env_file=str(PROJECT_ROOT / ".env"), extra="ignore")

    # App
    app_name: str = "Enterprise AI Knowledge & Analytics Agent"
    environment: str = "development"
    debug: bool = True
    backend_host: str = "0.0.0.0"
    backend_port: int = 8000
    log_level: str = "INFO"
    cors_origins: str = "http://localhost:5173,http://localhost:8080"

    # PostgreSQL (relational SQL + pgvector embeddings)
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_user: str = "agent"
    postgres_password: str = "agent_password"
    postgres_db: str = "agentdb"

    # Redis
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0
    redis_password: str = ""

    # Model gateway
    model_default: str = "ollama/llama3.1"
    model_config_path: str = "config/models.yaml"
    openai_api_key: Optional[str] = None
    openai_api_base: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    groq_api_key: Optional[str] = None
    openrouter_api_key: Optional[str] = None
    gemini_api_key: Optional[str] = None
    deepseek_api_key: Optional[str] = None
    custom_llm_api_key: Optional[str] = None
    custom_llm_base_url: Optional[str] = None
    ollama_base_url: str = "http://localhost:11434"

    # RAG / ingestion
    embedding_dim: int = 768
    chunk_size: int = 1000
    chunk_overlap: int = 200
    top_k_retrieval: int = 5

    # SQL agent demo data
    sql_seed_demo: bool = True

    # Web search
    web_search_engine: str = "duckduckgo"
    serpapi_key: Optional[str] = None

    # Frontend static path
    frontend_dist: str = "../frontend/dist"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def postgres_url(self) -> str:
        return (
            f"postgresql+psycopg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def postgres_dsn(self) -> str:
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def redis_url(self) -> str:
        auth = f":{self.redis_password}@" if self.redis_password else ""
        return f"redis://{auth}{self.redis_host}:{self.redis_port}/{self.redis_db}"

    @property
    def model_config_file(self) -> Path:
        # Resolve relative to backend dir or project root
        p = Path(self.model_config_path)
        if not p.is_absolute():
            for base in (BACKEND_DIR, PROJECT_ROOT):
                cand = base / p
                if cand.exists():
                    return cand
        return p


class ModelConfig:
    """Parsed models.yaml - providers, routes, generation params."""

    def __init__(self, raw: dict[str, Any]) -> None:
        self.raw = raw
        self.default_model: str = raw.get("default_model", "ollama/llama3.1")
        self.providers: dict[str, dict[str, Any]] = raw.get("providers", {})
        self.model_routes: dict[str, dict[str, Any]] = raw.get("model_routes", {})
        self.generation: dict[str, Any] = raw.get("generation", {})

    def provider(self, name: str) -> dict[str, Any]:
        return self.providers.get(name, {})

    def route(self, task_type: str) -> dict[str, Any]:
        return self.model_routes.get(task_type, {})


@lru_cache
def get_settings() -> Settings:
    return Settings()


@lru_cache
def get_model_config() -> ModelConfig:
    settings = get_settings()
    path = settings.model_config_file
    if not path.exists():
        raise FileNotFoundError(f"Model config not found: {path}")
    with open(path, "r", encoding="utf-8") as fh:
        raw = yaml.safe_load(fh) or {}
    return ModelConfig(raw)
