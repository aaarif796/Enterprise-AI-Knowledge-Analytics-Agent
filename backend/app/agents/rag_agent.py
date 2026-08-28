"""RAG Agent - retrieval-augmented generation over pgvector."""
from __future__ import annotations

from ..core.logging import get_logger
from ..core.schemas import AgentContext, Citation
from ..services.vector_store import VectorStore

logger = get_logger("rag_agent")


class RAGAgent:
    def __init__(self) -> None:
        self.vector_store = VectorStore()

    async def run(self, query: str, top_k: int | None = None) -> AgentContext:
        citations = await self.vector_store.search(query, top_k=top_k)
        logger.info("rag_retrieved", query=query, hits=len(citations))
        context = AgentContext(sources=citations, tool_calls=["vector_search"])
        if citations:
            context.content = "\n\n".join(
                f"[{i}] {c.title}: {c.snippet}" for i, c in enumerate(citations, 1)
            )
        return context
