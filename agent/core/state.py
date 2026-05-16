"""Agent state definition for LangGraph."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, TypedDict


class HistoryMessage(TypedDict):
    """A single turn of conversation history."""
    role: str   # "user" | "assistant"
    content: str


class AgentState(TypedDict, total=False):
    query: str
    locale: str
    symbol: Optional[str]
    plan: Dict[str, Any]
    data: Dict[str, Any]
    sources: List[str]
    valuations: List[Dict[str, Any]]
    # CAPM result is stored separately because it is a cost-of-equity estimate,
    # not a price estimate, and must not pollute the valuations confidence average.
    capm_result: Optional[Dict[str, Any]]
    answer: str
    confidence: int
    warnings: List[str]
    iterations: int
    max_iterations: int
    should_retry: bool
    # Conversation memory: prior turns passed in by the caller so the planner
    # can resolve follow-up questions like "what about its debt?".
    history: List[HistoryMessage]
