"""SQL Agent - natural language analytics over PostgreSQL."""
from __future__ import annotations

from ..core.logging import get_logger
from ..core.schemas import AgentContext, Citation
from ..services.sql_engine import SQLEngine

logger = get_logger("sql_agent")


class SQLAgent:
    def __init__(self) -> None:
        self.engine = SQLEngine()

    async def run(self, query: str) -> AgentContext:
        citation = await self.engine.answer_question(query)
        logger.info("sql_answered", query=query, has_result=bool(citation.metadata.get("result")))
        context = AgentContext(sources=[citation], tool_calls=["run_sql"])
        context.content = citation.snippet
        return context
