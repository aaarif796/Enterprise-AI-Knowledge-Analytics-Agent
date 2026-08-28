"""Redis client + caching layer.

Used for:
  - LLM response caching (avoid re-billing/re-computing -> saves money)
  - Embedding caching (reuse vectors for repeated chunks)
  - Session / conversation memory (multi-turn context)
  - Rate limiting (protect free API tiers)
"""
from __future__ import annotations

import hashlib
import json
import time
from typing import Any, Optional

import redis

from .config import get_settings
from .logging import get_logger

logger = get_logger("cache")


class RedisCache:
    """Thin wrapper around redis for our caching needs.

    Gracefully degrades to a no-op in-memory cache if Redis is down,
    so the app still works without Redis (development-friendly).
    """

    def __init__(self, url: str, use_redis: bool = True) -> None:
        self._client: Optional[redis.Redis] = None
        self._memory: dict[str, tuple[float, str]] = {}
        self._ttl: int = 3600
        if use_redis:
            try:
                self._client = redis.Redis.from_url(url, decode_responses=True)
                self._client.ping()
                logger.info("redis_connected")
            except Exception as exc:  # pragma: no cover - env dependent
                logger.warning("redis_unavailable_falling_back_to_memory", error=str(exc))
                self._client = None

    # ---------------- primitives ----------------
    def get(self, key: str) -> Optional[str]:
        if self._client is not None:
            try:
                return self._client.get(key)
            except Exception:
                return None
        item = self._memory.get(key)
        if item and item[0] > time.time():
            return item[1]
        return None

    def set(self, key: str, value: str, ttl: int | None = None) -> None:
        ttl = ttl or self._ttl
        if self._client is not None:
            try:
                self._client.set(key, value, ex=ttl)
                return
            except Exception:
                pass
        self._memory[key] = (time.time() + ttl, value)

    def delete(self, key: str) -> None:
        if self._client is not None:
            try:
                self._client.delete(key)
                return
            except Exception:
                pass
        self._memory.pop(key, None)

    def exists(self, key: str) -> bool:
        return self.get(key) is not None

    def incr(self, key: str, ttl: int | None = None) -> int:
        ttl = ttl or 60
        if self._client is not None:
            try:
                pipe = self._client.pipeline()
                pipe.incr(key)
                pipe.expire(key, ttl)
                result = pipe.execute()[0]
                return int(result)
            except Exception:
                pass
        val = int(self._memory.get(key, (0, "0"))[1] or 0) + 1
        self._memory[key] = (time.time() + ttl, str(val))
        return val

    # ---------------- typed helpers ----------------
    def get_json(self, key: str) -> Optional[Any]:
        raw = self.get(key)
        if raw is None:
            return None
        try:
            return json.loads(raw)
        except Exception:
            return None

    def set_json(self, key: str, value: Any, ttl: int | None = None) -> None:
        self.set(key, json.dumps(value, default=str), ttl)

    # ---------------- domain helpers ----------------
    @staticmethod
    def _hash(*parts: str) -> str:
        joined = "|".join(parts)
        return hashlib.sha256(joined.encode("utf-8")).hexdigest()[:48]

    def get_cached_completion(self, model: str, prompt_key: str) -> Optional[str]:
        return self.get(f"llm:{model}:{prompt_key}")

    def cache_completion(self, model: str, prompt_key: str, text: str, ttl: int = 86400) -> None:
        self.set(f"llm:{model}:{prompt_key}", text, ttl)

    def get_cached_embedding(self, model: str, text: str) -> Optional[list[float]]:
        raw = self.get(f"emb:{model}:{self._hash(text)}")
        return json.loads(raw) if raw else None

    def cache_embedding(self, model: str, text: str, vector: list[float], ttl: int = 86400) -> None:
        self.set(f"emb:{model}:{self._hash(text)}", json.dumps(vector), ttl)

    def get_session(self, session_id: str) -> Optional[list[dict[str, Any]]]:
        return self.get_json(f"session:{session_id}")

    def set_session(self, session_id: str, history: list[dict[str, Any]], ttl: int = 7200) -> None:
        self.set_json(f"session:{session_id}", history[-50:], ttl)

    def rate_limit(self, key: str, limit: int, window: int = 60) -> bool:
        """Return True if the key is within the rate limit."""
        count = self.incr(f"rl:{key}", ttl=window)
        return count <= limit


_cache: Optional[RedisCache] = None


def get_cache() -> RedisCache:
    """Get the shared RedisCache singleton."""
    global _cache
    if _cache is None:
        settings = get_settings()
        _cache = RedisCache(settings.redis_url)
    return _cache
