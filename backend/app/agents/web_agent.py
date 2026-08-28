"""Web Agent - real-time web search and summarization."""
from __future__ import annotations

from ..core.logging import get_logger
from ..core.schemas import AgentContext
from ..services.web_search import WebSearch

logger = get_logger("web_agent")


class WebAgent:
    def __init__(self) -> None:
        self.web_search = WebSearch()

    async def run(self, query: str, max_results: int = 5) -> AgentContext:
        citations = self.web_search.search(query, max_results=max_results)
        logger.info("web_searched", query=query, hits=len(citations))
        context = AgentContext(sources=citations, tool_calls=["web_search"])
        context.content = "\n\n".join(
            f"[{i}] {c.title}: {c.snippet}" for i, c in enumerate(citations, 1)
        )
        return context
