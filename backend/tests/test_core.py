"""Core unit tests - no external services needed."""
from __future__ import annotations

import sys
from pathlib import Path

# Ensure backend is importable
BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))


def test_model_config_loads():
    from app.core.config import get_model_config

    cfg = get_model_config()
    assert cfg.default_model.startswith("ollama/")
    assert "sql_generation" in cfg.model_routes
    assert "evaluator" in cfg.model_routes


def test_router_resolves_routes():
    from app.core.model_router import ModelRouter
    from app.core.schemas import TaskType

    router = ModelRouter()
    sql_model = router.resolve(TaskType.SQL_GENERATION)
    assert sql_model
    assert router.chain(TaskType.EVALUATOR)
    assert router.routed_models()
    models = router.available_models()
    assert models
    # All providers should be represented per spec (free vendors kept)
    providers = {p for _, p, _ in models}
    assert "ollama" in providers


def test_router_override():
    from app.core.model_router import ModelRouter
    from app.core.schemas import TaskType

    router = ModelRouter()
    overridden = router.resolve(TaskType.ROUTING, "openai/gpt-4o")
    assert overridden == "openai/gpt-4o"


def test_metrics_parse_score():
    from app.evaluation.metrics import parse_score, parse_score_pair

    assert parse_score("0.85") == 0.85
    assert parse_score("85") == 0.85
    assert parse_score("score: 0.7") == 0.7
    assert parse_score("no numbers") == 0.0
    assert parse_score_pair("8/10") == (0.8, 0.8)


def test_vector_store_chunking():
    from app.services.vector_store import VectorStore

    store = VectorStore()
    chunks = store._chunk_text("word " * 300, size=100, overlap=10)
    assert len(chunks) > 1
    assert all(0 < len(c) <= 100 for c in chunks)
    assert store._chunk_text("   ") == []


def test_sql_clean():
    from app.services.sql_engine import SQLEngine

    assert SQLEngine._clean_sql("SELECT 1;") == "SELECT 1"
    assert SQLEngine._clean_sql("```sql\nSELECT 1```") == "SELECT 1"
