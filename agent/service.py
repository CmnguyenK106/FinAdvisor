"""FastAPI service for the Python agent."""

from __future__ import annotations

from fastapi import FastAPI
from pydantic import BaseModel

from agent.core.config import load_config
from agent.core.graph import build_agent_graph


class AgentRequest(BaseModel):
    query: str
    locale: str | None = None


class AgentResponse(BaseModel):
    answer: str
    confidence: int
    valuations: list
    sources: list[str] = []


def create_app() -> FastAPI:
    cfg = load_config()
    graph = build_agent_graph(cfg).compile()

    app = FastAPI(title="Agent Service")

    @app.post("/agent/run", response_model=AgentResponse)
    def run_agent(req: AgentRequest) -> AgentResponse:
        state = {
            "query": req.query,
            "locale": req.locale or "vi",
        }
        result = graph.invoke(state)
        return AgentResponse(
            answer=result.get("answer", ""),
            confidence=result.get("confidence", 0),
            valuations=result.get("valuations", []),
            sources=result.get("sources", []),
        )

    return app


app = create_app()
