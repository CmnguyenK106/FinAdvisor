"""LLM client setup for OpenRouter."""

from __future__ import annotations

from langchain_openai import ChatOpenAI

from .config import AgentConfig


def build_llm(cfg: AgentConfig) -> ChatOpenAI:
    return ChatOpenAI(
        openai_api_key=cfg.openrouter_api_key,
        base_url=cfg.openrouter_base_url,
        model=cfg.openrouter_model,
        temperature=0.2,
    )
