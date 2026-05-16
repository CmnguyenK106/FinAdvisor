"""FastAPI service for the Python agent."""

from __future__ import annotations

import json
from typing import AsyncIterator, List

from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from agent.core.config import load_config
from agent.core.graph import build_agent_graph, build_pre_draft_graph
from agent.core.state import HistoryMessage


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------

class AgentRequest(BaseModel):
    query: str
    locale: str | None = None
    # Caller passes the last N turns so the planner can resolve follow-ups.
    history: List[HistoryMessage] = []


class AgentResponse(BaseModel):
    answer: str
    confidence: int
    valuations: list
    sources: list[str] = []
    warnings: list[str] = []


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------

def create_app() -> FastAPI:
    cfg = load_config()
    graph = build_agent_graph(cfg).compile()
    pre_draft_graph, nodes = build_pre_draft_graph(cfg)
    pre_draft_graph = pre_draft_graph.compile()

    app = FastAPI(title="Agent Service")

    # ------------------------------------------------------------------ #
    # POST /agent/run  — blocking, returns full JSON response             #
    # ------------------------------------------------------------------ #
    @app.post("/agent/run", response_model=AgentResponse)
    def run_agent(req: AgentRequest) -> AgentResponse:
        state = {
            "query": req.query,
            "locale": req.locale or "vi",
            "history": req.history,
        }
        result = graph.invoke(state)
        return AgentResponse(
            answer=result.get("answer", ""),
            confidence=result.get("confidence", 0),
            valuations=result.get("valuations", []),
            sources=result.get("sources", []),
            warnings=result.get("warnings", []),
        )

    # ------------------------------------------------------------------ #
    # POST /agent/stream  — SSE streaming, tokens arrive as they are     #
    # generated; metadata (valuations, confidence) sent as final event   #
    # ------------------------------------------------------------------ #
    @app.post("/agent/stream")
    async def stream_agent(req: AgentRequest) -> StreamingResponse:
        state = {
            "query": req.query,
            "locale": req.locale or "vi",
            "history": req.history,
        }

        async def event_stream() -> AsyncIterator[str]:
            import asyncio

            try:
                populated_state = await asyncio.to_thread(pre_draft_graph.invoke, state)
            except Exception as e:
                yield f"data: {json.dumps({'type': 'token', 'content': f'\\n\\n[System Error: Agent failed to initialize: {e}]'})}\n\n"
                yield f"data: {json.dumps({'type': 'done', 'confidence': 0, 'valuations': [], 'sources': [], 'warnings': [str(e)], 'symbol': ''})}\n\n"
                return

            # 2. Stream answer tokens as SSE data events.
            async for token in nodes.astream_answer(populated_state):
                yield f"data: {json.dumps({'type': 'token', 'content': token})}\n\n"

            # 3. Final event with full metadata.
            meta = {
                "type": "done",
                "confidence": populated_state.get("confidence", 0),
                "valuations": populated_state.get("valuations", []),
                "sources": populated_state.get("sources", []),
                "warnings": populated_state.get("warnings", []),
                "symbol": populated_state.get("symbol"),
            }
            yield f"data: {json.dumps(meta)}\n\n"

        return StreamingResponse(
            event_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",  # disables nginx buffering
            },
        )

    return app


app = create_app()
