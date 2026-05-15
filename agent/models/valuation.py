"""Valuation models with confidence scoring and sensitivity analysis."""

from __future__ import annotations

from dataclasses import dataclass
from math import sqrt
from typing import Any, Dict, List, Optional, Tuple


def _require_positive(name: str, value: float) -> None:
    if value <= 0:
        raise ValueError(f"{name} must be positive")


def _clamp(value: float, min_value: float, max_value: float) -> float:
    return max(min_value, min(max_value, value))


def _confidence_score(
    completeness: float,
    sensitivity_ratio: float,
    data_recency_days: Optional[int] = None,
    peer_count: Optional[int] = None,
) -> int:
    completeness = _clamp(completeness, 0.0, 1.0)
    sensitivity_ratio = _clamp(sensitivity_ratio, 0.0, 1.0)

    score = 40.0
    score += 35.0 * completeness
    score += 15.0 * (1.0 - sensitivity_ratio)

    if data_recency_days is not None:
        if data_recency_days <= 30:
            score += 5.0
        elif data_recency_days <= 90:
            score += 2.5

    if peer_count is not None:
        score += 5.0 * _clamp(peer_count / 10.0, 0.0, 1.0)

    return int(_clamp(score, 0.0, 100.0))


def _sensitivity_band(estimate: float, delta: float) -> Dict[str, float]:
    return {
        "low": estimate * (1.0 - delta),
        "high": estimate * (1.0 + delta),
        "delta": delta,
    }


@dataclass
class ValuationResult:
    model: str
    estimate: float
    range_low: float
    range_high: float
    confidence: int
    details: Dict[str, Any]
    sensitivity: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "model": self.model,
            "estimate": self.estimate,
            "range": {"low": self.range_low, "high": self.range_high},
            "confidence": self.confidence,
            "details": self.details,
            "sensitivity": self.sensitivity,
        }


def valuation_multiples(
    *,
    eps: Optional[float],
    ebitda: Optional[float],
    book_value_per_share: Optional[float],
    shares_outstanding: Optional[float],
    net_debt: float = 0.0,
    pe_multiple: Optional[float] = None,
    ev_ebitda_multiple: Optional[float] = None,
    pb_multiple: Optional[float] = None,
    data_recency_days: Optional[int] = None,
    peer_count: Optional[int] = None,
) -> ValuationResult:
    estimates: List[float] = []
    detail = {
        "inputs": {
            "eps": eps,
            "ebitda": ebitda,
            "book_value_per_share": book_value_per_share,
            "shares_outstanding": shares_outstanding,
            "net_debt": net_debt,
            "pe_multiple": pe_multiple,
            "ev_ebitda_multiple": ev_ebitda_multiple,
            "pb_multiple": pb_multiple,
        }
    }

    if eps is not None and pe_multiple and eps > 0:
        # Skip P/E for loss-making companies (negative EPS is valid data, not an error).
        _require_positive("pe_multiple", pe_multiple)
        estimates.append(eps * pe_multiple)

    if ebitda is not None and ev_ebitda_multiple and shares_outstanding:
        _require_positive("ebitda", ebitda)
        _require_positive("ev_ebitda_multiple", ev_ebitda_multiple)
        _require_positive("shares_outstanding", shares_outstanding)
        enterprise_value = ebitda * ev_ebitda_multiple
        equity_value = enterprise_value - net_debt
        estimates.append(equity_value / shares_outstanding)

    if book_value_per_share is not None and pb_multiple:
        _require_positive("book_value_per_share", book_value_per_share)
        _require_positive("pb_multiple", pb_multiple)
        estimates.append(book_value_per_share * pb_multiple)

    if not estimates:
        raise ValueError("no usable inputs for multiples valuation")

    estimate = sum(estimates) / len(estimates)
    range_low = min(estimates)
    range_high = max(estimates)

    sensitivity = {
        "pe": _sensitivity_band(estimate, 0.1) if pe_multiple else None,
        "ev_ebitda": _sensitivity_band(estimate, 0.1) if ev_ebitda_multiple else None,
        "pb": _sensitivity_band(estimate, 0.1) if pb_multiple else None,
    }
    sensitivity_ratio = (range_high - range_low) / estimate if estimate else 1.0
    completeness = len(estimates) / 3.0

    confidence = _confidence_score(completeness, sensitivity_ratio, data_recency_days, peer_count)
    return ValuationResult(
        model="multiples",
        estimate=estimate,
        range_low=range_low,
        range_high=range_high,
        confidence=confidence,
        details=detail,
        sensitivity=sensitivity,
    )


def valuation_dcf(
    *,
    fcfs: List[float],
    discount_rate: float,
    terminal_growth_rate: float,
    shares_outstanding: float,
    net_debt: float = 0.0,
    data_recency_days: Optional[int] = None,
) -> ValuationResult:
    if len(fcfs) < 2:
        raise ValueError("fcfs must contain at least 2 years")

    _require_positive("discount_rate", discount_rate)
    _require_positive("shares_outstanding", shares_outstanding)

    if discount_rate <= terminal_growth_rate:
        raise ValueError("discount_rate must be greater than terminal_growth_rate")

    present_value = 0.0
    for idx, fcf in enumerate(fcfs, start=1):
        present_value += fcf / ((1.0 + discount_rate) ** idx)

    terminal_value = fcfs[-1] * (1.0 + terminal_growth_rate) / (discount_rate - terminal_growth_rate)
    terminal_present = terminal_value / ((1.0 + discount_rate) ** len(fcfs))

    enterprise_value = present_value + terminal_present
    equity_value = enterprise_value - net_debt
    estimate = equity_value / shares_outstanding

    sensitivity = _dcf_sensitivity(fcfs, discount_rate, terminal_growth_rate, shares_outstanding, net_debt)
    range_low, range_high = _range_from_sensitivity(sensitivity["scenarios"])
    sensitivity_ratio = (range_high - range_low) / estimate if estimate else 1.0

    confidence = _confidence_score(0.9, sensitivity_ratio, data_recency_days, None)
    return ValuationResult(
        model="dcf",
        estimate=estimate,
        range_low=range_low,
        range_high=range_high,
        confidence=confidence,
        details={
            "inputs": {
                "fcfs": fcfs,
                "discount_rate": discount_rate,
                "terminal_growth_rate": terminal_growth_rate,
                "shares_outstanding": shares_outstanding,
                "net_debt": net_debt,
            }
        },
        sensitivity=sensitivity,
    )


def _dcf_sensitivity(
    fcfs: List[float],
    discount_rate: float,
    terminal_growth_rate: float,
    shares_outstanding: float,
    net_debt: float,
) -> Dict[str, Any]:
    dr_variants = [discount_rate - 0.01, discount_rate, discount_rate + 0.01]
    tg_variants = [terminal_growth_rate - 0.005, terminal_growth_rate, terminal_growth_rate + 0.005]

    scenarios: List[Dict[str, float]] = []
    for dr in dr_variants:
        for tg in tg_variants:
            if dr <= tg or dr <= 0:
                continue
            estimate = valuation_dcf(
                fcfs=fcfs,
                discount_rate=dr,
                terminal_growth_rate=tg,
                shares_outstanding=shares_outstanding,
                net_debt=net_debt,
            ).estimate
            scenarios.append({
                "discount_rate": dr,
                "terminal_growth_rate": tg,
                "price": estimate,
            })

    return {"scenarios": scenarios, "type": "grid"}


def valuation_ddm(
    *,
    dividend_per_share: float,
    dividend_growth_rate: float,
    discount_rate: float,
    data_recency_days: Optional[int] = None,
) -> ValuationResult:
    _require_positive("dividend_per_share", dividend_per_share)
    _require_positive("discount_rate", discount_rate)

    if discount_rate <= dividend_growth_rate:
        raise ValueError("discount_rate must be greater than dividend_growth_rate")

    estimate = dividend_per_share * (1.0 + dividend_growth_rate) / (discount_rate - dividend_growth_rate)

    sensitivity = _ddm_sensitivity(dividend_per_share, dividend_growth_rate, discount_rate)
    range_low, range_high = _range_from_sensitivity(sensitivity["scenarios"])
    sensitivity_ratio = (range_high - range_low) / estimate if estimate else 1.0

    confidence = _confidence_score(0.8, sensitivity_ratio, data_recency_days, None)
    return ValuationResult(
        model="ddm",
        estimate=estimate,
        range_low=range_low,
        range_high=range_high,
        confidence=confidence,
        details={
            "inputs": {
                "dividend_per_share": dividend_per_share,
                "dividend_growth_rate": dividend_growth_rate,
                "discount_rate": discount_rate,
            }
        },
        sensitivity=sensitivity,
    )


def _ddm_sensitivity(
    dividend_per_share: float,
    dividend_growth_rate: float,
    discount_rate: float,
) -> Dict[str, Any]:
    growth_variants = [dividend_growth_rate - 0.01, dividend_growth_rate, dividend_growth_rate + 0.01]
    discount_variants = [discount_rate - 0.01, discount_rate, discount_rate + 0.01]

    scenarios: List[Dict[str, float]] = []
    for g in growth_variants:
        for r in discount_variants:
            if r <= g or r <= 0:
                continue
            estimate = dividend_per_share * (1.0 + g) / (r - g)
            scenarios.append({
                "dividend_growth_rate": g,
                "discount_rate": r,
                "price": estimate,
            })

    return {"scenarios": scenarios, "type": "grid"}


def valuation_book_value(
    *,
    book_value_per_share: float,
    target_pb: float,
    data_recency_days: Optional[int] = None,
) -> ValuationResult:
    _require_positive("book_value_per_share", book_value_per_share)
    _require_positive("target_pb", target_pb)

    estimate = book_value_per_share * target_pb
    sensitivity = {"pb": _sensitivity_band(estimate, 0.15)}
    range_low = sensitivity["pb"]["low"]
    range_high = sensitivity["pb"]["high"]
    sensitivity_ratio = (range_high - range_low) / estimate if estimate else 1.0

    confidence = _confidence_score(0.6, sensitivity_ratio, data_recency_days, None)
    return ValuationResult(
        model="book_value",
        estimate=estimate,
        range_low=range_low,
        range_high=range_high,
        confidence=confidence,
        details={"inputs": {"book_value_per_share": book_value_per_share, "target_pb": target_pb}},
        sensitivity=sensitivity,
    )


def valuation_graham(
    *,
    eps: float,
    book_value_per_share: float,
    data_recency_days: Optional[int] = None,
) -> ValuationResult:
    _require_positive("eps", eps)
    _require_positive("book_value_per_share", book_value_per_share)

    estimate = sqrt(22.5 * eps * book_value_per_share)
    sensitivity = {"inputs": _sensitivity_band(estimate, 0.2)}
    range_low = sensitivity["inputs"]["low"]
    range_high = sensitivity["inputs"]["high"]
    sensitivity_ratio = (range_high - range_low) / estimate if estimate else 1.0

    confidence = _confidence_score(0.5, sensitivity_ratio, data_recency_days, None)
    return ValuationResult(
        model="graham",
        estimate=estimate,
        range_low=range_low,
        range_high=range_high,
        confidence=confidence,
        details={"inputs": {"eps": eps, "book_value_per_share": book_value_per_share}},
        sensitivity=sensitivity,
    )


def estimate_cost_of_equity_capm(
    *,
    risk_free_rate: float,
    beta: float,
    market_risk_premium: float,
) -> Dict[str, float]:
    _require_positive("risk_free_rate", risk_free_rate)

    cost = risk_free_rate + beta * market_risk_premium
    return {
        "method": "capm",
        "risk_free_rate": risk_free_rate,
        "beta": beta,
        "market_risk_premium": market_risk_premium,
        "cost_of_equity": cost,
    }


def _range_from_sensitivity(scenarios: List[Dict[str, float]]) -> Tuple[float, float]:
    prices = [s["price"] for s in scenarios if "price" in s]
    if not prices:
        return 0.0, 0.0
    return min(prices), max(prices)
