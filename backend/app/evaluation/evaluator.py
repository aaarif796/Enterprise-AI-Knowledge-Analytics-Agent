"""Evaluator - LLM-as-judge for Faithfulness, Relevance, and Correctness.

Each metric is scored 0-1 using the cheap/fast evaluator model, then an
overall confidence is the average of the three.
"""
from __future__ import annotations

from ..core.logging import get_logger
from ..core.model_gateway import get_gateway
from ..core.model_router import ModelRouter
from ..core.schemas import EvaluationResult, TaskType
from .metrics import parse_score

logger = get_logger("evaluator")


class Evaluator:
    def __init__(self) -> None:
        self.gateway = get_gateway()
        self.router = ModelRouter()

    async def evaluate(self, question: str, answer: str,
                       context: str) -> EvaluationResult:
        model = self.router.resolve(TaskType.EVALUATOR)
        context = context or "(no context)"
        answer = answer or "(no answer)"

        faithfulness = await self._judge(
            model,
            "You are a strict faithfulness judge. Score 0.0 to 1.0 for how "
            "much the ANSWER is supported by (not contradicting) the CONTEXT. "
            "Respond with only a number between 0.0 and 1.0.",
            f"CONTEXT:\n{context}\n\nANSWER:\n{answer}",
        )
        relevance = await self._judge(
            model,
            "You are a relevance judge. Score 0.0 to 1.0 for how well the "
            "ANSWER addresses the QUESTION. Respond with only a number between 0.0 and 1.0.",
            f"QUESTION:\n{question}\n\nANSWER:\n{answer}",
        )
        correctness = await self._judge(
            model,
            "You are a factual correctness judge. Score 0.0 to 1.0 for the "
            "factual accuracy of the ANSWER. Respond with only a number between 0.0 and 1.0.",
            f"QUESTION:\n{question}\n\nANSWER:\n{answer}",
        )

        result = EvaluationResult(
            faithfulness=faithfulness,
            relevance=relevance,
            correctness=correctness,
        )
        logger.info("evaluation_complete", **result.details)
        return result

    async def _judge(self, model: str, system: str, user: str) -> float:
        result = await self.gateway.complete(
            model,
            [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=0.0,
            max_tokens=20,
            task_type=TaskType.EVALUATOR,
            use_cache=False,
        )
        if result.error:
            return 0.5
        return parse_score(result.text)
