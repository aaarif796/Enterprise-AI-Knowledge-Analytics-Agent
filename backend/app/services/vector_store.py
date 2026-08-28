"""Vector store - RAG retrieval over pgvector.

Documents are split into chunks, embedded via the Model Gateway, and stored
in the `embeddings` table. Retrieval uses pgvector cosine distance (<=>).
"""
from __future__ import annotations

import json
import re
from typing import Any, Optional

from sqlalchemy import select, text

from ..core.config import get_settings
from ..core.logging import get_logger
from ..core.model_gateway import get_gateway
from ..core.model_router import ModelRouter
from ..core.schemas import Citation, SourceType, TaskType
from .database import get_session_factory
from .models import EmbeddingDocument

logger = get_logger("vector_store")


class VectorStore:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.gateway = get_gateway()
        self.router = ModelRouter()

    # ---------------- ingestion ----------------
    async def ingest(self, text_content: str, source_name: str = "document") -> int:
        chunks = self._chunk_text(text_content)
        if not chunks:
            return 0

        embed_model = self.router.resolve(TaskType.EMBEDDING)
        vectors = await self.gateway.embed(embed_model, chunks)
        if vectors is None or len(vectors) != len(chunks):
            logger.error("ingest_embedding_failed", source=source_name, chunks=len(chunks))
            return 0

        session_factory = get_session_factory()
        with session_factory() as db:
            for idx, (chunk, vec) in enumerate(zip(chunks, vectors)):
                doc = EmbeddingDocument(
                    source_name=source_name,
                    chunk_index=idx,
                    content=chunk,
                    metadata_json=json.dumps({"source": source_name, "chunk": idx}),
                    embedding=vec,
                )
                db.add(doc)
            db.commit()
        logger.info("ingested", source=source_name, chunks=len(chunks))
        return len(chunks)

    # ---------------- retrieval ----------------
    async def search(self, query: str, top_k: int | None = None) -> list[Citation]:
        top_k = top_k or self.settings.top_k_retrieval
        embed_model = self.router.resolve(TaskType.EMBEDDING)
        vectors = await self.gateway.embed(embed_model, [query])
        if vectors is None or not vectors:
            return []
        query_vec = vectors[0]

        session_factory = get_session_factory()
        with session_factory() as db:
            # pgvector cosine distance operator '<->' ; closest first
            stmt = text(
                "SELECT id, source_name, chunk_index, content, metadata_json, "
                "1 - (embedding <=> :qv) AS score "
                "FROM embeddings ORDER BY embedding <=> :qv LIMIT :k"
            )
            rows = db.execute(stmt, {"qv": query_vec, "k": top_k}).mappings().all()

        citations: list[Citation] = []
        for row in rows:
            meta = json.loads(row["metadata_json"] or "{}")
            citations.append(
                Citation(
                    type=SourceType.VECTOR,
                    title=row["source_name"],
                    snippet=(row["content"] or "")[:300],
                    score=float(row["score"]),
                    metadata=meta,
                )
            )
        return citations

    # ---------------- text splitting ----------------
    def _chunk_text(self, text_content: str, size: int | None = None,
                    overlap: int | None = None) -> list[str]:
        size = size or self.settings.chunk_size
        overlap = overlap or self.settings.chunk_overlap
        # normalize whitespace
        text_content = re.sub(r"\s+", " ", text_content).strip()
        if not text_content:
            return []
        chunks: list[str] = []
        start = 0
        n = len(text_content)
        while start < n:
            end = min(start + size, n)
            chunks.append(text_content[start:end])
            if end >= n:
                break
            start = max(end - overlap, start + 1)
        return chunks
