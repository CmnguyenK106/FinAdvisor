"""Agent state definition for LangGraph."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, TypedDict


class AgentState(TypedDict, total=False):
    query: str
    locale: str
    symbol: Optional[str]
    plan: Dict[str, Any]
    data: Dict[str, Any]
    news: Dict[str, Any]
    valuations: List[Dict[str, Any]]
    answer: str
    confidence: int
    warnings: List[str]
    iterations: int
    max_iterations: int
    should_retry: bool
