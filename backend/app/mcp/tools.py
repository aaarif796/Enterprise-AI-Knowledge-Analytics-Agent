"""MCP Tool Layer - standardized tools exposed to agents and external clients.

Implements a minimal MCP-style registry where each tool has a name, a schema,
and an async handler. This gives a clean, composable tool surface consumed by
the orchestrator/agents and any MCP-compatible client.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

from ..core.logging import get_logger
from ..core.schemas import Citation

logger = get_logger("mcp_tools")

ToolHandler = Callable[..., Awaitable[Any]]


@dataclass
class Tool:
    name: str
    description: str
    parameters: dict[str, Any]
    handler: ToolHandler


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def list(self) -> list[dict[str, Any]]:
        return [
            {"name": t.name, "description": t.description, "parameters": t.parameters}
            for t in self._tools.values()
        ]

    async def call(self, name: str, **kwargs: Any) -> Any:
        tool = self._tools.get(name)
        if tool is None:
            raise KeyError(f"Unknown tool: {name}")
        logger.info("tool_call", tool=name)
        return await tool.handler(**kwargs)


_registry: ToolRegistry | None = None


def get_registry() -> ToolRegistry:
    global _registry
    if _registry is None:
        from ..services.sql_engine import SQLEngine
        from ..services.vector_store import VectorStore
        from ..services.web_search import WebSearch

        _registry = ToolRegistry()

        async def vector_search(query: str, top_k: int = 5) -> list[dict]:
            results: list[Citation] = await VectorStore().search(query, top_k=top_k)
            return [c.model_dump() for c in results]

        async def web_search(query: str, max_results: int = 5) -> list[dict]:
            results = WebSearch().search(query, max_results=max_results)
            return [c.model_dump() for c in results]

        async def run_sql(question: str) -> dict:
            citation = await SQLEngine().answer_question(question)
            return citation.model_dump()

        _registry.register(Tool(
            name="vector_search",
            description="Semantic search over the ingested enterprise knowledge base (pgvector).",
            parameters={"query": {"type": "string"}, "top_k": {"type": "integer"}},
            handler=vector_search,
        ))
        _registry.register(Tool(
            name="web_search",
            description="Search the live web (DuckDuckGo / SERP).",
            parameters={"query": {"type": "string"}, "max_results": {"type": "integer"}},
            handler=web_search,
        ))
        _registry.register(Tool(
            name="run_sql",
            description="Answer an analytics question against the PostgreSQL warehouse.",
            parameters={"question": {"type": "string"}},
            handler=run_sql,
        ))
    return _registry
