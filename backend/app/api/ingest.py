"""Document ingestion endpoint for the RAG knowledge base."""
from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from ..core.schemas import IngestRequest, IngestResponse
from ..services.vector_store import VectorStore

router = APIRouter(prefix="/api", tags=["ingest"])


@router.post("/documents", response_model=IngestResponse)
async def ingest_document(payload: IngestRequest) -> JSONResponse:
    store = VectorStore()
    count = await store.ingest(payload.document, payload.source_name)
    return JSONResponse(
        IngestResponse(chunks_ingested=count, source_name=payload.source_name).model_dump()
    )
