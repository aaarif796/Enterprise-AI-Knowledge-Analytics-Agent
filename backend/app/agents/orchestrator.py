"""Agent Orchestrator / Router.

Classifies an incoming query into an intent using the cheap routing model,
dispatches to the appropriate agent(s) (RAG / SQL / Web), collects their
context, streams/assembles a grounded answer via the Response Agent, then
scores it with the Evaluator.

The dispatch itself is deterministic rule + LLM-backed classification so it
is reliable in production and cheap (small routing model).
"""
from __future__ import annotations

import json
from typing import Optional

from ..core.cache import get_cache
from ..core.logging import get_logger
from ..core.model_gateway import get_gateway
from ..core.model_router import ModelRouter
from ..core.schemas import (
    AgentContext,
    Citation,
    EvaluationResult,
    SourceType,
    TaskType,
)
from ..evaluation.evaluator import Evaluator
from ..services.response_agent import ResponseAgent
from .rag_agent import RAGAgent
from .sql_agent import SQLAgent
from .web_agent import WebAgent

logger = get_logger("orchestrator")

INTENT_SYSTEM = (
    "Classify the user's query into exactly one intent. Reply with ONLY a "
    "single keyword from: {routing, rag, sql, web, general}. "
    "rules: rag=asking about ingested documents/knowledge base; "
    "sql=asking for analytics, numbers, sales, revenue, totals, products, stock, "
    "orders, data in a database; "
    "web=asking for current/live info, news, today, latest, real-time; "
    "routing/general=anything else."
)


class Orchestrator:
    def __init__(self) -> None:
        self.gateway = get_gateway()
        self.router = ModelRouter()
        self.cache = get_cache()
        self.rag = RAGAgent()
        self.sql = SQLAgent()
        self.web = WebAgent()
        self.response_agent = ResponseAgent()
        self.evaluator = Evaluator()

    async def classify(self, query: str, override: Optional[str] = None) -> str:
        """Return the intent string for a query."""
        # Keyword pre-classification for common analytics terms
        lowered = query.lower()
        analytics_words = ("sales", "revenue", "total", "sum", "average", "stock",
                           "product", "order", "customer", "how many", "count",
                           "profit", "price", "analytics", "database")
        web_words = ("news", "today", "latest", "current", "live", "weather",
                     "headline", "breaking")

        if any(w in lowered for w in analytics_words):
            return "sql"
        if any(w in lowered for w in web_words):
            return "web"

        model = self.router.resolve(TaskType.ROUTING, override)
        result = await self.gateway.complete(
            model,
            [
                {"role": "system", "content": INTENT_SYSTEM},
                {"role": "user", "content": query},
            ],
            temperature=0.0,
            max_tokens=10,
            task_type=TaskType.ROUTING,
            use_cache=False,
        )
        text = (result.text or "").strip().lower()
        for intent in ("rag", "sql", "web", "general", "routing"):
            if intent in text:
                return intent if intent != "routing" else "general"
        return "general"

    async def run(self, query: str,
                  task_overrides: Optional[dict[str, str]] = None) -> dict:
        """Full pipeline: classify -> route -> synthesize -> evaluate."""
        task_overrides = task_overrides or {}
        intent = await self.classify(query, task_overrides.get("routing"))

        contexts: list[AgentContext] = []
        if intent in ("rag", "general"):
            contexts.append(await self.rag.run(query))
        if intent in ("sql", "general"):
            contexts.append(await self.sql.run(query))
        if intent in ("web", "general"):
            contexts.append(await self.web.run(query))

        # Deduplicate and merge citations
        citations: list[Citation] = []
        for ctx in contexts:
            citations.extend(ctx.sources)

        context_text = "\n\n".join((c.content or "") for c in contexts if c.content)
        answer = await self.response_agent.synthesize(
            query, citations, task_overrides.get("final_synth")
        )
        evaluation = await self.evaluator.evaluate(query, answer, context_text)

        routed_models = self.router.routed_models(task_overrides)
        return {
            "answer": answer,
            "evaluation": evaluation,
            "citations": citations,
            "routed_models": routed_models,
            "intent": intent,
        }
