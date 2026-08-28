"""Unified Model Gateway.

Wraps LiteLLM to provide a single interface for chatting, streaming, and
embedding across ALL supported providers (Ollama, Groq, OpenRouter, OpenAI,
Anthropic, Gemini, DeepSeek, and any OpenAI-compatible endpoint).

The gateway is provider-agnostic: you write a fully-qualified model name
(e.g. "ollama/llama3.1", "groq/llama-3.1-8b-instant") and LiteLLM handles
routing to the right provider. Keys/base URLs come from the environment.

Caching is applied at this layer so repeated work never re-bills.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Optional

from litellm import acompletion, aembedding

from .cache import get_cache
from .config import get_settings
from .logging import get_logger
from .schemas import TaskType

logger = get_logger("gateway")


@dataclass
class GatewayResult:
    text: str = ""
    model_used: str = ""
    provider: str = ""
    cached: bool = False
    error: Optional[str] = None
    finish_reason: Optional[str] = None


@dataclass
class RouteDecision:
    model: str
    provider: str
    api_base: Optional[str] = None
    api_key: Optional[str] = None
    temperature: float = 0.2
    max_tokens: int = 2048
    extra: dict[str, Any] = field(default_factory=dict)


class ModelGateway:
    """Unified client backed by LiteLLM with caching + failover."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self.cache = get_cache()


    # ---------------- provider resolution ----------------
    def _resolve_route(self, model: str, temperature: float | None = None,
                       max_tokens: int | None = None) -> RouteDecision:
        """Resolve a fully-qualified model string into an actionable route."""
        provider, _, bare = model.partition("/")
        route = RouteDecision(
            model=model,
            provider=provider,
            temperature=temperature or 0.2,
            max_tokens=max_tokens or 2048,
        )

        base_url_env = None
        key_env = None
        if provider == "ollama":
            route.api_base = self.settings.ollama_base_url
        elif provider == "openai":
            base_url_env = self.settings.openai_api_base
            key_env = self.settings.openai_api_key
        elif provider == "anthropic":
            key_env = self.settings.anthropic_api_key
        elif provider == "groq":
            key_env = self.settings.groq_api_key
        elif provider == "openrouter":
            key_env = self.settings.openrouter_api_key
        elif provider == "gemini":
            key_env = self.settings.gemini_api_key
        elif provider == "deepseek":
            key_env = self.settings.deepseek_api_key

        if base_url_env:
            route.api_base = base_url_env
        if key_env:
            route.api_key = key_env
        return route

    # ---------------- completion ----------------
    async def complete(self, model: str, messages: list[dict[str, str]],
                       temperature: float | None = None,
                       max_tokens: int | None = None,
                       use_cache: bool = True,
                       task_type: Optional[TaskType] = None) -> GatewayResult:
        route = self._resolve_route(model, temperature, max_tokens)

        prompt_key = self._prompt_key(route, messages)
        if use_cache:
            cached = self.cache.get_cached_completion(route.model, prompt_key)
            if cached:
                return GatewayResult(text=cached, model_used=route.model,
                                     provider=route.provider, cached=True)

        try:
            kwargs: dict[str, Any] = dict(
                model=route.model,
                messages=messages,
                temperature=route.temperature,
                max_tokens=route.max_tokens,
            )
            if route.api_base:
                kwargs["api_base"] = route.api_base
            if route.api_key:
                kwargs["api_key"] = route.api_key

            resp = await acompletion(**kwargs)
            text = resp.choices[0].message.content or ""

            if use_cache and text:
                self.cache.cache_completion(route.model, prompt_key, text)
            return GatewayResult(text=text, model_used=route.model,
                                 provider=route.provider,
                                 finish_reason=getattr(resp.choices[0], "finish_reason", None))
        except Exception as exc:
            logger.warning("completion_failed", model=route.model, error=str(exc))
            return GatewayResult(error=str(exc), model_used=route.model, provider=route.provider)

    # ---------------- streaming ----------------
    async def stream(self, model: str, messages: list[dict[str, str]],
                     temperature: float | None = None,
                     max_tokens: int | None = None) -> AsyncIterator[str]:
        route = self._resolve_route(model, temperature, max_tokens)
        kwargs: dict[str, Any] = dict(
            model=route.model, messages=messages,
            temperature=route.temperature, max_tokens=route.max_tokens,
            stream=True,
        )
        if route.api_base:
            kwargs["api_base"] = route.api_base
        if route.api_key:
            kwargs["api_key"] = route.api_key

        try:
            async for chunk in await acompletion(**kwargs):
                delta = chunk.choices[0].delta.content if chunk.choices else None
                if delta:
                    yield delta
        except Exception as exc:
            logger.warning("stream_failed", model=route.model, error=str(exc))
            yield f"[stream error: {exc}]"

    # ---------------- embeddings ----------------
    async def embed(self, model: str, texts: list[str]) -> Optional[list[list[float]]]:
        route = self._resolve_route(model)
        vectors: list[list[float]] = []
        missing: list[tuple[int, str]] = []
        for idx, t in enumerate(texts):
            cached = self.cache.get_cached_embedding(route.model, t)
            if cached is not None:
                vectors.append(cached)
            else:
                missing.append((len(vectors), t))
                vectors.append([0.0])  # placeholder replaced below

        if missing:
            missing_texts = [t for _, t in missing]
            try:
                kwargs: dict[str, Any] = dict(model=route.model, input=missing_texts)
                if route.api_base:
                    kwargs["api_base"] = route.api_base
                if route.api_key:
                    kwargs["api_key"] = route.api_key
                resp = await aembedding(**kwargs)
                raw = [d["embedding"] for d in resp.data]
                for (orig_idx, text), vec in zip(missing, raw):
                    vectors[orig_idx] = vec
                    self.cache.cache_embedding(route.model, text, vec)
            except Exception as exc:
                logger.warning("embed_failed", model=route.model, error=str(exc))
                return None

        return vectors

    # ---------------- helpers ----------------
    @staticmethod
    def _prompt_key(route: RouteDecision, messages: list[dict[str, str]]) -> str:
        import hashlib
        joined = "|".join(f"{m.get('role')}:{m.get('content','')}" for m in messages)
        return hashlib.sha256(joined.encode("utf-8")).hexdigest()[:40]


_gateway: Optional[ModelGateway] = None


def get_gateway() -> ModelGateway:
    global _gateway
    if _gateway is None:
        _gateway = ModelGateway()
    return _gateway

