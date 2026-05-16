"""LLM client setup for OpenRouter."""

from __future__ import annotations

from typing import List, Literal

from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from .config import AgentConfig


# ---------------------------------------------------------------------------
# Structured output schema for the planner node
# ---------------------------------------------------------------------------

class PlanSchema(BaseModel):
    """Validated plan produced by the planner LLM call.

    Using with_structured_output() guarantees we always receive a well-typed
    object instead of relying on brittle JSON string parsing.
    """

    symbol: str = Field(description="Ticker symbol, e.g. VNM")
    needs_price: bool = Field(default=True, description="Whether to fetch price history")
    needs_financials: bool = Field(default=True, description="Whether to fetch financials")
    needs_ratios: bool = Field(default=True, description="Whether to fetch fundamental ratios")
    needs_reports: bool = Field(default=True, description="Whether to fetch financial reports per period")
    needs_posts: bool = Field(default=True, description="Whether to fetch posts about company")
    needs_estimated_price: bool = Field(default=True, description="Whether to fetch value estimation")
    valuation_models: List[
        Literal["multiples", "dcf", "ddm", "book_value", "graham"]
    ] = Field(
        default=["multiples", "dcf"],
        description="Valuation models to run",
    )


# ---------------------------------------------------------------------------
# LLM factories
# ---------------------------------------------------------------------------

def build_llm(cfg: AgentConfig) -> ChatOpenAI:
    """Plain chat LLM used for draft_answer (streaming-compatible)."""
    return ChatOpenAI(
        openai_api_key=cfg.openrouter_api_key,
        base_url=cfg.openrouter_base_url,
        model=cfg.openrouter_model,
        temperature=0.2,
    )


def build_structured_llm(cfg: AgentConfig) -> ChatOpenAI:
    """LLM bound to PlanSchema via with_structured_output.

    Returns a runnable that always produces a PlanSchema instance,
    eliminating the need for regex/JSON fence stripping in plan_step.
    Falls back gracefully: if the provider does not support tool/function
    calling, LangChain raises during invoke and plan_step catches it.
    """
    base = build_llm(cfg)
    return base.with_structured_output(PlanSchema)
