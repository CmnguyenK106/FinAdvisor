"""LangGraph core workflow for the agent."""

from __future__ import annotations

import json
from typing import Any, Dict, List

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, StateGraph

from agent.mappers.fireant_mapper import extract_fireant_metrics
from agent.models.valuation import (
    estimate_cost_of_equity_capm,
    valuation_book_value,
    valuation_dcf,
    valuation_ddm,
    valuation_graham,
    valuation_multiples,
)

from .config import AgentConfig
from .llm import build_llm
from .state import AgentState
from .tools import DataGatewayClient


def build_agent_graph(cfg: AgentConfig) -> StateGraph:
    llm = build_llm(cfg)
    data_client = DataGatewayClient(cfg.gateway_url)

    graph = StateGraph(AgentState)

    def plan_step(state: AgentState) -> AgentState:
        query = state.get("query", "")
        system = SystemMessage(
            content=(
                "You are a finance planning assistant. Extract the ticker symbol, "
                "decide which data you need, and suggest valuation models. "
                "Return JSON with keys: symbol, needs_price, needs_financials, "
                "needs_ratios, valuation_models."
            )
        )
        response = llm.invoke([system, HumanMessage(content=query)])
        plan: Dict[str, Any]
        try:
            plan = json.loads(response.content)
        except Exception:
            plan = {
                "symbol": _extract_symbol(query),
                "needs_price": True,
                "needs_financials": True,
                "needs_ratios": True,
                "valuation_models": ["multiples", "dcf"],
            }

        state["plan"] = plan
        state["symbol"] = plan.get("symbol")
        state["iterations"] = state.get("iterations", 0)
        state["max_iterations"] = cfg.max_iterations
        return state

    def fetch_data(state: AgentState) -> AgentState:
        symbol = state.get("symbol")
        plan = state.get("plan", {})
        data: Dict[str, Any] = state.get("data", {})
        warnings: List[str] = state.get("warnings", [])

        if not symbol:
            warnings.append("missing symbol")
            state["warnings"] = warnings
            return state

        if plan.get("needs_price"):
            data["price_history"] = data_client.price_history(symbol)
        if plan.get("needs_financials"):
            data["financials"] = data_client.financials(symbol)
        if plan.get("needs_ratios"):
            data["ratios"] = data_client.ratios(symbol)

        state["data"] = data
        state["warnings"] = warnings
        return state

    def run_models(state: AgentState) -> AgentState:
        models = state.get("plan", {}).get("valuation_models", [])
        valuations: List[Dict[str, Any]] = []
        data = state.get("data", {})

        metrics = _extract_metrics(data)
        if "multiples" in models:
            valuations.append(
                valuation_multiples(
                    eps=metrics.get("eps"),
                    ebitda=metrics.get("ebitda"),
                    book_value_per_share=metrics.get("book_value_per_share"),
                    shares_outstanding=metrics.get("shares_outstanding"),
                    net_debt=metrics.get("net_debt", 0.0),
                    pe_multiple=metrics.get("pe_multiple"),
                    ev_ebitda_multiple=metrics.get("ev_ebitda_multiple"),
                    pb_multiple=metrics.get("pb_multiple"),
                    data_recency_days=metrics.get("data_recency_days"),
                    peer_count=metrics.get("peer_count"),
                ).to_dict()
            )
        if "dcf" in models and metrics.get("fcfs"):
            valuations.append(
                valuation_dcf(
                    fcfs=metrics["fcfs"],
                    discount_rate=metrics.get("discount_rate", 0.12),
                    terminal_growth_rate=metrics.get("terminal_growth_rate", 0.03),
                    shares_outstanding=metrics.get("shares_outstanding", 1.0),
                    net_debt=metrics.get("net_debt", 0.0),
                    data_recency_days=metrics.get("data_recency_days"),
                ).to_dict()
            )
        if "ddm" in models and metrics.get("dividend_per_share"):
            valuations.append(
                valuation_ddm(
                    dividend_per_share=metrics["dividend_per_share"],
                    dividend_growth_rate=metrics.get("dividend_growth_rate", 0.02),
                    discount_rate=metrics.get("discount_rate", 0.12),
                    data_recency_days=metrics.get("data_recency_days"),
                ).to_dict()
            )
        if "book_value" in models and metrics.get("book_value_per_share"):
            valuations.append(
                valuation_book_value(
                    book_value_per_share=metrics["book_value_per_share"],
                    target_pb=metrics.get("pb_multiple", 1.0),
                    data_recency_days=metrics.get("data_recency_days"),
                ).to_dict()
            )
        if "graham" in models and metrics.get("eps") and metrics.get("book_value_per_share"):
            valuations.append(
                valuation_graham(
                    eps=metrics["eps"],
                    book_value_per_share=metrics["book_value_per_share"],
                    data_recency_days=metrics.get("data_recency_days"),
                ).to_dict()
            )

        if metrics.get("beta") is not None:
            valuations.append(
                estimate_cost_of_equity_capm(
                    risk_free_rate=metrics.get("risk_free_rate", 0.04),
                    beta=metrics["beta"],
                    market_risk_premium=metrics.get("market_risk_premium", 0.06),
                )
            )

        state["valuations"] = valuations
        state["confidence"] = _aggregate_confidence(valuations)
        return state

    def draft_answer(state: AgentState) -> AgentState:
        system = SystemMessage(
            content=(
                "You are an investment analyst. Use the provided valuations to answer "
                "the query. Provide a short recommendation and cite sources."
            )
        )
        payload = {
            "query": state.get("query"),
            "symbol": state.get("symbol"),
            "valuations": state.get("valuations", []),
        }
        response = llm.invoke([system, HumanMessage(content=json.dumps(payload))])
        state["answer"] = response.content
        return state

    def evaluate(state: AgentState) -> AgentState:
        iterations = state.get("iterations", 0)
        confidence = state.get("confidence", 0)
        missing_data = _missing_data(state.get("data", {}))
        should_retry = confidence < cfg.min_confidence and missing_data and iterations < cfg.max_iterations

        state["should_retry"] = should_retry
        state["iterations"] = iterations + 1
        return state

    graph.add_node("plan", plan_step)
    graph.add_node("fetch_data", fetch_data)
    graph.add_node("run_models", run_models)
    graph.add_node("draft_answer", draft_answer)
    graph.add_node("evaluate", evaluate)

    graph.set_entry_point("plan")
    graph.add_edge("plan", "fetch_data")
    graph.add_edge("fetch_data", "run_models")
    graph.add_edge("run_models", "draft_answer")
    graph.add_edge("draft_answer", "evaluate")

    def route(state: AgentState) -> str:
        return "fetch_data" if state.get("should_retry") else END

    graph.add_conditional_edges("evaluate", route, {"fetch_data": "fetch_data", END: END})

    return graph


def _extract_symbol(query: str) -> str | None:
    tokens = [token.strip().upper() for token in query.split()]
    for token in tokens:
        if 2 <= len(token) <= 5 and token.isalpha():
            return token
    return None


def _extract_metrics(data: Dict[str, Any]) -> Dict[str, Any]:
    return extract_fireant_metrics(data)


def _aggregate_confidence(valuations: List[Dict[str, Any]]) -> int:
    scores = [val.get("confidence", 0) for val in valuations if isinstance(val, dict)]
    if not scores:
        return 0
    return int(sum(scores) / len(scores))


def _missing_data(data: Dict[str, Any]) -> bool:
    return not bool(data)
