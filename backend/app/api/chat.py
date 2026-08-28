"""Chat endpoint - full agent pipeline (classify -> route -> synthesize -> evaluate)."""
from __future__ import annotations

import json
import time
import uuid

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse

from ..agents.orchestrator import Orchestrator
from ..core.cache import get_cache
from ..core.schemas import ChatRequest, ChatResponse

router = APIRouter(prefix="/api", tags=["chat"])


@router.post("/chat", response_model=ChatResponse)
async def chat(payload: ChatRequest) -> JSONResponse:
    session_id = payload.session_id or str(uuid.uuid4())
    cache = get_cache()
    orchestrator = Orchestrator()

    # Load prior history (multi-turn memory)
    history = cache.get_session(session_id) or []
    history.append({"role": "user", "content": payload.message})

    start = time.perf_counter()
    try:
        result = await orchestrator.run(payload.message, payload.task_overrides)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Agent pipeline error: {exc}")

    history.append({"role": "assistant", "content": result["answer"]})
    cache.set_session(session_id, history)

    latency_ms = int((time.perf_counter() - start) * 1000)
    response = ChatResponse(
        session_id=session_id,
        answer=result["answer"],
        confidence=result["evaluation"].confidence if result["evaluation"] else 0.0,
        evaluation=result["evaluation"],
        citations=result["citations"],
        routed_models=result["routed_models"],
        latency_ms=latency_ms,
    )
    return JSONResponse(response.model_dump())


@router.post("/chat/stream")
async def chat_stream(payload: ChatRequest):
    """Streaming chat. Returns Server-Sent Events with token + meta events."""
    from fastapi.responses import StreamingResponse

    session_id = payload.session_id or str(uuid.uuid4())
    orchestrator = Orchestrator()
    cache = get_cache()

    async def event_stream():
        # 1) run pipeline for citations + confidence (production would optimize)
        import asyncio
        result = await orchestrator.run(payload.message, payload.task_overrides)
        answer_lines = result["answer"]

        # Emit citations + confidence first
        yield f"data: {json.dumps({'type':'meta','citations':[c.model_dump() for c in result['citations']], 'confidence': result['evaluation'].confidence if result['evaluation'] else 0.0, 'routed_models': result['routed_models']})}\n\n"
        # Stream answer in word chunks
        for word in answer_lines.split(" "):
            yield f"data: {json.dumps({'type':'token','content': word + ' '})}\n\n"
            await asyncio.sleep(0.02)
        yield f"data: {json.dumps({'type':'done','session_id':session_id})}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
