"""Map FireAnt payloads into normalized valuation metrics."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


def extract_fireant_metrics(data: Dict[str, Any], as_of: Optional[datetime] = None) -> Dict[str, Any]:
    if as_of is None:
        as_of = datetime.now(timezone.utc)

    metrics: Dict[str, Any] = {}

    # Only "ratios" is populated by the graph (via DataGatewayClient.ratios).
    # The former "fundamental" alias has been removed to avoid implying that
    # /data/fundamental is ever fetched.
    fundamental = _get_envelope_data(data, "ratios")
    if isinstance(fundamental, dict):
        metrics["market_cap"] = fundamental.get("market_cap")
        metrics["pe_multiple"] = fundamental.get("pe_multiple")
        metrics["pb_multiple"] = fundamental.get("pb_multiple")
        metrics["dividend_yield"] = fundamental.get("dividend_yield")
        metrics["eps"] = fundamental.get("eps")
        metrics["roe"] = fundamental.get("roe")
        metrics["roa"] = fundamental.get("roa")
        metrics["net_profit_margin"] = fundamental.get("net_profit_margin")

    price_history = _get_envelope_data(data, "price_history")
    last_close, last_date = _extract_last_close(price_history)
    if last_close is not None:
        metrics["last_close"] = last_close
    if last_date is not None:
        metrics["data_recency_days"] = max(0, (as_of - last_date).days)

    if metrics.get("market_cap") and last_close:
        metrics["shares_outstanding"] = metrics["market_cap"] / last_close

    financials = _get_envelope_data(data, "financials")
    if isinstance(financials, dict):
        values = financials.get("financial_values") or financials.get("financialValues")
        if isinstance(values, dict):
            metrics["ebitda"] = _first_value(values, ["ebitda", "EBITDA", "operatingProfit"])
            metrics["book_value_per_share"] = _first_value(
                values,
                ["bookValuePerShare", "book_value_per_share", "bvps"],
            )
            metrics["dividend_per_share"] = _first_value(
                values,
                ["dividendPerShare", "dividend_per_share"],
            )
            metrics["dividend_growth_rate"] = _first_value(
                values,
                ["dividendGrowthRate", "dividend_growth_rate"],
            )

            total_debt = _first_value(values, ["totalDebt", "total_debt"])
            cash = _first_value(
                values,
                ["cash", "cashAndCashEquivalents", "cash_and_equivalents"],
            )
            if total_debt is not None:
                metrics["net_debt"] = total_debt - (cash or 0.0)

            free_cash_flow = _first_value(
                values,
                ["freeCashFlow", "free_cash_flow", "fcf"],
            )
            if free_cash_flow is not None:
                metrics["fcfs"] = _ensure_list(free_cash_flow)

    if metrics.get("dividend_per_share") is None and metrics.get("dividend_yield") and last_close:
        metrics["dividend_per_share"] = metrics["dividend_yield"] * last_close

    if metrics.get("fcfs") is None:
        reports = _get_envelope_data(data, "reports")
        if isinstance(reports, dict) and isinstance(reports.get("reports"), list):
            fcfs = _extract_fcf_from_reports(reports.get("reports", []))
            if fcfs:
                metrics["fcfs"] = fcfs

    if metrics.get("book_value_per_share") is None and metrics.get("shares_outstanding"):
        if isinstance(financials, dict):
            values = financials.get("financial_values") or financials.get("financialValues")
            equity = _first_value(values or {}, ["equity", "totalEquity", "shareholdersEquity"])
            if equity is not None:
                metrics["book_value_per_share"] = equity / metrics["shares_outstanding"]

    return {k: v for k, v in metrics.items() if v is not None}


def _get_envelope_data(data: Dict[str, Any], key: str) -> Any:
    envelope = data.get(key)
    if isinstance(envelope, dict) and "data" in envelope:
        return envelope.get("data")
    return envelope


def _extract_last_close(price_history: Any) -> tuple[Optional[float], Optional[datetime]]:
    if not isinstance(price_history, dict):
        return None, None
    quotes = price_history.get("quotes")
    if not isinstance(quotes, list) or not quotes:
        return None, None

    for item in reversed(quotes):
        if not isinstance(item, dict):
            continue
        close = item.get("close")
        date_value = _parse_date(item.get("date"))
        if close is not None:
            return float(close), date_value

    return None, None


def _parse_date(value: Any) -> Optional[datetime]:
    if not isinstance(value, str) or not value:
        return None

    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            parsed = datetime.strptime(value, fmt)
            if parsed.tzinfo is None:
                return parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc)
        except ValueError:
            continue
    return None


def _first_value(values: Dict[str, Any], keys: List[str]) -> Optional[float]:
    for key in keys:
        if key in values and values[key] is not None:
            try:
                return float(values[key])
            except (TypeError, ValueError):
                continue
    return None


def _ensure_list(value: float) -> List[float]:
    # Return a genuine single-element list.
    # valuation_dcf requires at least 2 periods; with only one FCF available it
    # will raise ValueError, which run_models catches and records as a warning.
    # Previously this duplicated the value ([v, v]), silently inflating DCF estimates.
    return [float(value)]


def _extract_fcf_from_reports(reports: List[Dict[str, Any]]) -> List[float]:
    cfo_fields = {
        "NetCashFromOperatingActivities",
        "NetCashFlowFromOperatingActivities",
        "OperatingCashFlow",
        "CFO",
    }
    capex_fields = {"Capex", "CapitalExpenditure", "PurchaseOfFixedAssets"}

    cfo_values = _find_report_values(reports, cfo_fields)
    capex_values = _find_report_values(reports, capex_fields)

    if not cfo_values or not capex_values:
        return []

    length = min(len(cfo_values), len(capex_values))
    fcfs: List[float] = []
    for idx in range(length):
        cfo = cfo_values[idx]
        capex = capex_values[idx]
        if capex < 0:
            fcf = cfo + abs(capex)
        else:
            fcf = cfo - capex
        fcfs.append(fcf)
    return fcfs


def _find_report_values(reports: List[Dict[str, Any]], fields: set[str]) -> List[float]:
    for item in reports:
        if not isinstance(item, dict):
            continue
        field = item.get("field")
        if field not in fields:
            continue
        values = item.get("values")
        if not isinstance(values, list):
            return []
        extracted: List[float] = []
        for entry in values:
            if isinstance(entry, dict) and entry.get("value") is not None:
                extracted.append(float(entry.get("value")))
        return extracted
    return []
