"""Pydantic schemas - shared data contracts across the API, agents, and evaluation."""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class TaskType(str, Enum):
    """Tasks the model gateway routes by."""

    ROUTING = "routing"
    EMBEDDING = "embedding"
    SQL_GENERATION = "sql_generation"
    RAG_CONTEXT = "rag_context"
    WEB_SUMMARY = "web_summary"
    FINAL_SYNTH = "final_synth"
    EVALUATOR = "evaluator"


class SourceType(str, Enum):
    VECTOR = "vector"
    SQL = "sql"
    WEB = "web"


class Citation(BaseModel):
    """A single source reference returned with an answer."""

    type: SourceType
    title: str
    snippet: str = ""
    url: Optional[str] = None
    score: Optional[float] = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class AgentContext(BaseModel):
    """Structured result returned by an agent."""

    content: str = ""
    sources: list[Citation] = Field(default_factory=list)
    tool_calls: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class EvaluationResult(BaseModel):
    faithfulness: float = 0.0
    relevance: float = 0.0
    correctness: float = 0.0

    @property
    def confidence(self) -> float:
        return round((self.faithfulness + self.relevance + self.correctness) / 3.0, 3)

    @property
    def details(self) -> dict[str, float]:
        return {
            "faithfulness": self.faithfulness,
            "relevance": self.relevance,
            "correctness": self.correctness,
            "confidence": self.confidence,
        }


# ---------- API request / response ----------

class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1)
    session_id: Optional[str] = None
    model_override: Optional[str] = None          # per-task override map as JSON string
    task_overrides: dict[str, str] = Field(default_factory=dict)  # task_type -> model


class ChatResponse(BaseModel):
    session_id: str
    answer: str = ""
    confidence: float = 0.0
    evaluation: Optional[EvaluationResult] = None
    citations: list[Citation] = Field(default_factory=list)
    routed_models: dict[str, str] = Field(default_factory=dict)  # task -> model used
    latency_ms: int = 0


class StreamEvent(BaseModel):
    type: str  # "token" | "citations" | "confidence" | "done" | "error"
    content: Any = None


class HealthResponse(BaseModel):
    status: str
    environment: str
    version: str
    services: dict[str, str] = Field(default_factory=dict)


class ModelInfo(BaseModel):
    model: str
    provider: str
    free: bool


class ConfigResponse(BaseModel):
    default_model: str
    active_providers: list[str]
    routes: dict[str, Any]
    available_models: list[ModelInfo]


class IngestRequest(BaseModel):
    document: str = Field(..., min_length=1)
    source_name: str = "document"


class IngestResponse(BaseModel):
    chunks_ingested: int
    source_name: str
    ok: bool = True
