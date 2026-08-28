"""Response Agent.

Synthesizes the final answer from collected citations/context using the
final_synth model, producing a crafted response with inline citations.
"""
from __future__ import annotations

from ..core.logging import get_logger
from ..core.model_gateway import get_gateway
from ..core.model_router import ModelRouter
from ..core.schemas import Citation, TaskType

logger = get_logger("response_agent")


class ResponseAgent:
    def __init__(self) -> None:
        self.gateway = get_gateway()
        self.router = ModelRouter()

    async def synthesize(self, question: str, citations: list[Citation],
                         model_override: str | None = None) -> str:
        """Build the final grounded answer text from the citations."""
        model = self.router.resolve(TaskType.FINAL_SYNTH, model_override)
        context = self._format_context(citations)

        prompt = (
            "You are a precise enterprise knowledge assistant. Answer the user's "
            "question using ONLY the provided context below. If the context does not "
            "contain the answer, say you could not find it. Cite sources inline as "
            "[1], [2] matching the numbered list. Be concise and factual.\n\n"
            "CONTEXT:\n" + (context or "(no context available)") + "\n\n"
            "QUESTION: " + question + "\n\n"
            "ANSWER:"
        )

        result = await self.gateway.complete(
            model,
            [{"role": "user", "content": prompt}],
            task_type=TaskType.FINAL_SYNTH,
        )
        if result.error:
            logger.warning("synthesis_failed", error=result.error)
            return "I'm sorry, I could not generate an answer right now."
        return result.text

    @staticmethod
    def _format_context(citations: list[Citation]) -> str:
        lines = []
        for i, c in enumerate(citations, 1):
            lines.append(f"[{i}] ({c.type.value}) {c.title}: {c.snippet}")
        return "\n".join(lines)
