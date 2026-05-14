"""Configuration helpers for the agent runtime."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass
class AgentConfig:
    gateway_url: str
    openrouter_api_key: str
    openrouter_base_url: str
    openrouter_model: str
    max_iterations: int
    min_confidence: int


def load_config() -> AgentConfig:
    return AgentConfig(
        gateway_url=os.getenv("GATEWAY_URL", "http://localhost:8081"),
        openrouter_api_key=os.getenv("OPENROUTER_API_KEY", ""),
        openrouter_base_url=os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
        openrouter_model=os.getenv("OPENROUTER_MODEL", "google/gemma-4-9b-it"),
        max_iterations=int(os.getenv("AGENT_MAX_ITERATIONS", "2")),
        min_confidence=int(os.getenv("AGENT_MIN_CONFIDENCE", "60")),
    )
