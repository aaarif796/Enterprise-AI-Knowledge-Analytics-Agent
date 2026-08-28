"""Web search service.

Default engagement is DuckDuckGo (free, no API key). Supports SERPAPI /
Google as an alternative via configuration. Returns results as citations.
"""
from __future__ import annotations

from typing import Optional

from ..core.config import get_settings
from ..core.logging import get_logger
from ..core.schemas import Citation, SourceType

logger = get_logger("web_search")

try:
    from duckduckgo_search import DDGS
    DDGS_AVAILABLE = True
except Exception:  # pragma: no cover
    DDGS_AVAILABLE = False


class WebSearch:
    def __init__(self) -> None:
        self.settings = get_settings()

    def search(self, query: str, max_results: int = 5) -> list[Citation]:
        engine = self.settings.web_search_engine
        if engine == "duckduckgo":
            return self._duckduckgo(query, max_results)
        if engine in ("serpapi", "google"):
            return self._serpapi(query, max_results)
        return self._duckduckgo(query, max_results)

    def _duckduckgo(self, query: str, max_results: int) -> list[Citation]:
        citations: list[Citation] = []
        if not DDGS_AVAILABLE:
            logger.warning("duckduckgo_search_not_installed")
            return citations
        try:
            with DDGS() as ddgs:
                for r in list(ddgs.text(query, max_results=max_results)):
                    citations.append(
                        Citation(
                            type=SourceType.WEB,
                            title=r.get("title") or "Web result",
                            snippet=(r.get("body") or r.get("snippet") or "")[:300],
                            url=r.get("href"),
                            score=float(r.get("rank") or 0),
                        )
                    )
        except Exception as exc:
            logger.warning("web_search_failed", error=str(exc))
        return citations

    def _serpapi(self, query: str, max_results: int) -> list[Citation]:
        # Optional SERPAPI integration (keyed); skipped unless key present
        import httpx

        key = self.settings.serpapi_key
        if not key:
            logger.warning("serpapi_key_missing")
            return []
        params = {
            "engine": "google", "q": query, "api_key": key,
            "num": max_results,
        }
        try:
            resp = httpx.get("https://serpapi.com/search.json", params=params, timeout=20)
            data = resp.json()
            citations: list[Citation] = []
            for item in data.get("organic_results", [])[:max_results]:
                citations.append(
                    Citation(
                        type=SourceType.WEB,
                        title=item.get("title", "Web result"),
                        snippet=(item.get("snippet") or "")[:300],
                        url=item.get("link"),
                    )
                )
            return citations
        except Exception as exc:
            logger.warning("serpapi_failed", error=str(exc))
            return []
