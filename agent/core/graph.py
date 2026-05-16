"""LangGraph core workflow for the agent."""

from __future__ import annotations

import json
import re
from typing import Any, AsyncIterator, Dict, Iterator, List, Optional

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
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
from .llm import PlanSchema, build_llm, build_structured_llm
from .state import AgentState, HistoryMessage
from .tools import DataGatewayClient

# ---------------------------------------------------------------------------
# Module-level constants
# ---------------------------------------------------------------------------

# Fallback: strips ```json ... ``` wrappers when structured output is unavailable.
_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*([\s\S]*?)\s*```", re.IGNORECASE)

# Common English and Vietnamese words that match the 2-5-alpha rule but are
# never ticker symbols.  Extend as needed.
_SYMBOL_STOP_WORDS: frozenset[str] = frozenset({
    "A", "AN", "THE", "AND", "OR", "OF", "IN", "ON", "AT", "TO", "BY",
    "IS", "IT", "BE", "DO", "GO", "HAS", "WAS", "ARE", "FOR", "NOT",
    "WITH", "FROM", "THAT", "THIS", "HAVE", "GIVE", "WILL", "THAN",
    "THEN", "THEY", "THEM", "WHAT", "WHEN", "WHICH", "WHO", "HOW",
    "ABOUT", "STOCK", "SHARE", "PRICE", "FUND", "RATIO",
    # Vietnamese common words (ASCII-uppercased, no diacritics)
    "MUA", "BAN", "CO", "LA", "VA", "DE", "NEN", "KHI", "VOI", "THEO",
    "HOI", "TAI", "HOA", "HOP", "GIA", "TI", "CHI", "THE", "NHUNG",
})

# Maximum number of history turns to include in the planner context.
_MAX_HISTORY_TURNS = 6


# ---------------------------------------------------------------------------
# AgentNodes class
# ---------------------------------------------------------------------------

class AgentNodes:
    """Encapsulates all LangGraph node functions with injected dependencies.

    Injecting llm, structured_llm, and data_client allows each node method
    to be unit-tested in isolation with mocked collaborators.
    """

    def __init__(
        self,
        cfg: AgentConfig,
        llm: Any,
        structured_llm: Any,
        data_client: DataGatewayClient,
    ) -> None:
        self._cfg = cfg
        self._llm = llm
        self._structured_llm = structured_llm
        self._data_client = data_client

    # ------------------------------------------------------------------
    # Node: planner  (structured output + conversation memory)
    # ------------------------------------------------------------------

    def plan_step(self, state: AgentState) -> AgentState:
        query = state.get("query", "")
        history: List[HistoryMessage] = state.get("history", [])

        system = SystemMessage(
            content=(
                "You are a finance planning assistant for Vietnam-listed equities.\n"
                "Given the conversation history and the latest user query, extract:\n"
                "  • symbol      – ticker (e.g. VNM). Infer from history if omitted.\n"
                "  • needs_price – whether to fetch historical prices.\n"
                "  • needs_financials – whether to fetch income/balance/cash-flow data.\n"
                "  • needs_ratios – whether to fetch P/E, P/B, EPS, ROE ratios.\n"
                "  • needs_reports – whether to fetch financial reports per period.\n"
                "  • needs_posts – whether to fetch posts about company.\n"
                "  • needs_estimated_price – whether to fetch value estimation.\n"
                "  • valuation_models – which models to run.\n"
                "Valid models: multiples, dcf, ddm, book_value, graham."
            )
        )

        # Build message list: system + last N history turns + current query.
        messages: list = [system]
        for turn in history[-_MAX_HISTORY_TURNS:]:
            if turn["role"] == "user":
                messages.append(HumanMessage(content=turn["content"]))
            else:
                messages.append(AIMessage(content=turn["content"]))
        messages.append(HumanMessage(content=query))

        plan: Dict[str, Any]
        try:
            # Primary path: structured output — always returns a valid PlanSchema.
            result: PlanSchema = self._structured_llm.invoke(messages)
            plan = result.model_dump()
            
            # Free models often hallucinate empty lists or False for required fields
            if not plan.get("valuation_models"):
                plan["valuation_models"] = ["multiples", "dcf"]
            for flag in ["needs_price", "needs_financials", "needs_ratios", "needs_reports", "needs_posts", "needs_estimated_price"]:
                if plan.get(flag) is False:
                    plan[flag] = True
        except Exception:
            # Fallback: plain LLM + JSON parsing (e.g. provider lacks tool-calling).
            try:
                raw = self._llm.invoke(messages)
                plan = _parse_json_response(raw.content)
            except Exception:
                plan = {
                    "symbol": _extract_symbol(query) or _symbol_from_history(history),
                    "needs_price": True,
                    "needs_financials": True,
                    "needs_ratios": True,
                    "needs_reports": True,
                    "needs_posts": True,
                    "needs_estimated_price": True,
                    "valuation_models": ["multiples", "dcf"],
                }

        state["plan"] = plan
        state["symbol"] = plan.get("symbol")
        state["iterations"] = state.get("iterations", 0)
        state["max_iterations"] = self._cfg.max_iterations
        return state

    # ------------------------------------------------------------------
    # Node: fetch_data
    # ------------------------------------------------------------------

    def fetch_data(self, state: AgentState) -> AgentState:
        symbol = state.get("symbol")
        plan = state.get("plan", {})
        data: Dict[str, Any] = state.get("data", {})
        warnings: List[str] = state.get("warnings", [])
        sources: List[str] = state.get("sources", [])

        if not symbol:
            warnings.append("missing symbol")
            state["warnings"] = warnings
            return state

        if plan.get("needs_price"):
            try:
                data["price_history"] = self._data_client.price_history(symbol)
            except Exception as exc:  # noqa: BLE001
                warnings.append(f"price_history fetch failed for {symbol}: {exc}")

        if plan.get("needs_financials"):
            try:
                data["financials"] = self._data_client.financials(symbol)
            except Exception as exc:  # noqa: BLE001
                warnings.append(f"financials fetch failed for {symbol}: {exc}")

        if plan.get("needs_ratios"):
            try:
                data["ratios"] = self._data_client.ratios(symbol)
            except Exception as exc:  # noqa: BLE001
                warnings.append(f"ratios fetch failed for {symbol}: {exc}")

        if plan.get("needs_reports"):
            try:
                data["reports"] = self._data_client.reports(symbol)
            except Exception as exc:  # noqa: BLE001
                warnings.append(f"reports fetch failed for {symbol}: {exc}")

        if plan.get("needs_posts"):
            try:
                data["posts"] = self._data_client.posts(symbol)
            except Exception as exc:  # noqa: BLE001
                warnings.append(f"posts fetch failed for {symbol}: {exc}")

        if plan.get("needs_estimated_price"):
            try:
                data["estimated_price"] = self._data_client.estimated_price(symbol)
            except Exception as exc:  # noqa: BLE001
                warnings.append(f"estimated_price fetch failed for {symbol}: {exc}")

        state["data"] = data
        state["warnings"] = warnings
        if data and "fireant" not in sources:
            sources.append("fireant")
        state["sources"] = sources
        return state

    # ------------------------------------------------------------------
    # Node: run_models
    # ------------------------------------------------------------------

    def run_models(self, state: AgentState) -> AgentState:
        models = state.get("plan", {}).get("valuation_models", [])
        valuations: List[Dict[str, Any]] = []
        data = state.get("data", {})
        warnings: List[str] = state.get("warnings", [])

        metrics = extract_fireant_metrics(data)

        if "multiples" in models:
            try:
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
            except ValueError as exc:
                warnings.append(f"multiples skipped: {exc}")

        if "dcf" in models and metrics.get("fcfs"):
            try:
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
            except ValueError as exc:
                warnings.append(f"dcf skipped: {exc}")

        if "ddm" in models and metrics.get("dividend_per_share"):
            try:
                valuations.append(
                    valuation_ddm(
                        dividend_per_share=metrics["dividend_per_share"],
                        dividend_growth_rate=metrics.get("dividend_growth_rate", 0.02),
                        discount_rate=metrics.get("discount_rate", 0.12),
                        data_recency_days=metrics.get("data_recency_days"),
                    ).to_dict()
                )
            except ValueError as exc:
                warnings.append(f"ddm skipped: {exc}")

        if "book_value" in models and metrics.get("book_value_per_share"):
            try:
                valuations.append(
                    valuation_book_value(
                        book_value_per_share=metrics["book_value_per_share"],
                        target_pb=metrics.get("pb_multiple", 1.0),
                        data_recency_days=metrics.get("data_recency_days"),
                    ).to_dict()
                )
            except ValueError as exc:
                warnings.append(f"book_value skipped: {exc}")

        if "graham" in models and metrics.get("eps") and metrics.get("book_value_per_share"):
            try:
                valuations.append(
                    valuation_graham(
                        eps=metrics["eps"],
                        book_value_per_share=metrics["book_value_per_share"],
                        data_recency_days=metrics.get("data_recency_days"),
                    ).to_dict()
                )
            except ValueError as exc:
                warnings.append(f"graham skipped: {exc}")

        capm: Optional[Dict[str, Any]] = None
        if metrics.get("beta") is not None:
            capm = estimate_cost_of_equity_capm(
                risk_free_rate=metrics.get("risk_free_rate", 0.04),
                beta=metrics["beta"],
                market_risk_premium=metrics.get("market_risk_premium", 0.06),
            )

        state["valuations"] = valuations
        state["capm_result"] = capm
        state["warnings"] = warnings
        state["confidence"] = _aggregate_confidence(valuations)
        return state

    # ------------------------------------------------------------------
    # Node: draft_answer  (supports both invoke and stream)
    # ------------------------------------------------------------------

    def _build_draft_messages(self, state: AgentState) -> list:
        """Build the message list for the draft_answer LLM call."""
        locale = state.get("locale", "vi")
        currency = "VND" if locale == "vi" else "USD"
        lang = "Vietnamese" if locale == "vi" else "English"

        system = SystemMessage(
            content=(
                "You are a professional investment analyst covering Vietnam-listed equities.\n"
                f"User locale: '{locale}'. All prices are in {currency}.\n\n"
                "You receive a JSON payload with:\n"
                "  • query – the user's original question\n"
                "  • symbol – the ticker\n"
                "  • valuations – list of price-estimate models, each containing:\n"
                "      - model: model name\n"
                "      - estimate: fair-value price\n"
                "      - range.low / range.high: sensitivity range\n"
                "      - confidence: 0-100 (higher = more reliable)\n"
                "  • cost_of_equity_capm (optional) – CAPM required return\n"
                "  • posts (optional) – recent news or expert posts about the company\n"
                "  • estimated_price (optional) – analyst value estimation\n"
                "  • warnings – data quality issues\n\n"
                "Your response must:\n"
                "1. Summarise each model's estimate and confidence in plain language.\n"
                "2. Give a consensus fair-value range (weight by confidence).\n"
                "3. Compare the consensus to the current market price when available, and to the analyst estimated_price if provided.\n"
                "4. Incorporate sentiment and insights from recent posts if provided.\n"
                "5. Issue a clear signal: BUY / HOLD / SELL with a brief rationale.\n"
                "6. Note any warnings that affect analysis reliability.\n"
                "7. End with: 'This is not personal financial advice.'\n"
                f"Respond in {lang}."
            )
        )

        payload: Dict[str, Any] = {
            "query": state.get("query"),
            "symbol": state.get("symbol"),
            "valuations": state.get("valuations", []),
            "warnings": state.get("warnings", []),
        }
        data = state.get("data", {})
        if "posts" in data:
            payload["posts"] = data["posts"]
        if "estimated_price" in data:
            payload["estimated_price"] = data["estimated_price"]
        if state.get("capm_result"):
            payload["cost_of_equity_capm"] = state["capm_result"]

        return [system, HumanMessage(content=json.dumps(payload))]

    def draft_answer(self, state: AgentState) -> AgentState:
        """Non-streaming node used by the standard graph.invoke() path."""
        messages = self._build_draft_messages(state)
        response = self._llm.invoke(messages)
        state["answer"] = response.content
        return state

    def stream_answer(self, state: AgentState) -> Iterator[str]:
        """Yield answer tokens one chunk at a time for SSE streaming.

        This is NOT a graph node — it is called directly by the /agent/stream
        endpoint after all non-streaming nodes have completed.
        """
        messages = self._build_draft_messages(state)
        for chunk in self._llm.stream(messages):
            if chunk.content:
                yield chunk.content

    async def astream_answer(self, state: AgentState) -> AsyncIterator[str]:
        """Async variant of stream_answer for use with FastAPI async endpoints."""
        messages = self._build_draft_messages(state)
        try:
            async for chunk in self._llm.astream(messages):
                if chunk.content:
                    yield chunk.content
        except Exception as e:
            yield f"\n\n[System Error: LLM request failed: {e}]"

    # ------------------------------------------------------------------
    # Node: evaluate
    # ------------------------------------------------------------------

    def evaluate(self, state: AgentState) -> AgentState:
        iterations = state.get("iterations", 0)
        confidence = state.get("confidence", 0)
        missing = _missing_financial_data(state.get("data", {}))
        should_retry = (
            confidence < self._cfg.min_confidence
            and missing
            and iterations < self._cfg.max_iterations
        )
        state["should_retry"] = should_retry
        state["iterations"] = iterations + 1
        return state


# ---------------------------------------------------------------------------
# Graph builder
# ---------------------------------------------------------------------------

def build_agent_graph(cfg: AgentConfig) -> StateGraph:
    """Compile the LangGraph workflow.

    The standard graph runs plan→fetch→models→draft→evaluate and uses
    blocking llm.invoke() in draft_answer.  For streaming, callers should
    run the graph up to (but not including) draft_answer, then call
    nodes.stream_answer() / nodes.astream_answer() directly.
    """
    nodes = AgentNodes(
        cfg,
        build_llm(cfg),
        build_structured_llm(cfg),
        DataGatewayClient(cfg.gateway_url),
    )

    graph = StateGraph(AgentState)
    graph.add_node("planner", nodes.plan_step)
    graph.add_node("fetch_data", nodes.fetch_data)
    graph.add_node("run_models", nodes.run_models)
    graph.add_node("draft_answer", nodes.draft_answer)
    graph.add_node("evaluate", nodes.evaluate)

    graph.set_entry_point("planner")
    graph.add_edge("planner", "fetch_data")
    graph.add_edge("fetch_data", "run_models")
    graph.add_edge("run_models", "draft_answer")
    graph.add_edge("draft_answer", "evaluate")

    def route(state: AgentState) -> str:
        return "fetch_data" if state.get("should_retry") else END

    graph.add_conditional_edges("evaluate", route, {"fetch_data": "fetch_data", END: END})
    return graph


def build_pre_draft_graph(cfg: AgentConfig) -> tuple[StateGraph, AgentNodes]:
    """Build a graph that stops before draft_answer, plus the nodes object.

    Used by the streaming endpoint: run this graph to get a fully-populated
    state (symbol, data, valuations, confidence), then call
    nodes.astream_answer(state) to stream the LLM response token-by-token.
    """
    nodes = AgentNodes(
        cfg,
        build_llm(cfg),
        build_structured_llm(cfg),
        DataGatewayClient(cfg.gateway_url),
    )

    graph = StateGraph(AgentState)
    graph.add_node("planner", nodes.plan_step)
    graph.add_node("fetch_data", nodes.fetch_data)
    graph.add_node("run_models", nodes.run_models)
    # No draft_answer or evaluate — stream endpoint handles those.

    graph.set_entry_point("planner")
    graph.add_edge("planner", "fetch_data")
    graph.add_edge("fetch_data", "run_models")
    graph.add_edge("run_models", END)

    return graph, nodes


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _parse_json_response(content: str) -> Dict[str, Any]:
    """Fallback: parse JSON, stripping markdown fences if present."""
    content = content.strip()
    match = _JSON_FENCE_RE.search(content)
    if match:
        content = match.group(1).strip()
    return json.loads(content)


def _extract_symbol(query: str) -> Optional[str]:
    """Best-effort ticker extraction — only used when the LLM planner fails."""
    for token in query.split():
        t = token.strip().upper()
        if 2 <= len(t) <= 5 and t.isalpha() and t not in _SYMBOL_STOP_WORDS:
            return t
    return None


def _symbol_from_history(history: List[HistoryMessage]) -> Optional[str]:
    """Scan recent history for a ticker when the current query omits it."""
    for turn in reversed(history[-_MAX_HISTORY_TURNS:]):
        candidate = _extract_symbol(turn["content"])
        if candidate:
            return candidate
    return None


def _aggregate_confidence(valuations: List[Dict[str, Any]]) -> int:
    scores = [v.get("confidence", 0) for v in valuations if isinstance(v, dict)]
    if not scores:
        return 0
    return int(sum(scores) / len(scores))


def _missing_financial_data(data: Dict[str, Any]) -> bool:
    """True when key financial data is absent (partial fetch counts)."""
    if not data:
        return True
    has_fundamentals = "ratios" in data or "fundamental" in data
    has_financials = "financials" in data
    return not (has_fundamentals and has_financials)
