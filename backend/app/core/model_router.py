"""Smart Model Router.

Selects the best (cheapest/free) model per task type from the route table
in models.yaml, and provides failover across vendors.

The router understands "this task wants a code model" vs "this task wants a
cheap fast classifier" etc., and resolves the right provider/model with a
fallback chain. Overrides can be provided per request (from the UI Model
Picker) to force a specific model for a task.
"""
from __future__ import annotations

from typing import Optional

from .config import get_model_config, get_settings
from .logging import get_logger
from .schemas import TaskType

logger = get_logger("router")


class ModelRouter:
    def __init__(self) -> None:
        self.model_config = get_model_config()
        self.settings = get_settings()

    def resolve(self, task_type: TaskType, override: Optional[str] = None) -> str:
        """Return the primary model for a task, considering per-request override."""
        if override:
            return self._normalize(override)
        route = self.model_config.route(task_type.value)
        primary = route.get("primary") or self.model_config.default_model
        return self._normalize(primary)

    def chain(self, task_type: TaskType) -> list[str]:
        """Return the ordered failover chain for a task."""
        route = self.model_config.route(task_type.value)
        chain = [route.get("primary")] if route.get("primary") else []
        chain += route.get("fallback", [])
        if not chain:
            chain = [self.model_config.default_model]
        # Append default at the end as a final safety net
        if self.model_config.default_model not in chain:
            chain.append(self.model_config.default_model)
        return [self._normalize(m) for m in chain if m]

    def default(self) -> str:
        return self._normalize(self.model_config.default_model)

    def routed_models(self, overrides: Optional[dict[str, str]] = None) -> dict[str, str]:
        """Return which model each task currently resolves to (for UI/debug)."""
        overrides = overrides or {}
        result: dict[str, str] = {}
        for task in TaskType:
            result[task.value] = self.resolve(task, overrides.get(task.value))
        return result

    def available_models(self) -> list[tuple[str, str, bool]]:
        """List of (model, provider, is_free) from all configured routes."""
        seen: set[str] = set()
        out: list[tuple[str, str, bool]] = []
        for task in TaskType:
            for model in self.chain(task):
                if model in seen:
                    continue
                seen.add(model)
                provider, _, _ = model.partition("/")
                free = provider in ("ollama", "groq", "openrouter") or ":free" in model
                out.append((model, provider, free))
        return out

    @staticmethod
    def _normalize(model: str) -> str:
        return model.strip()
