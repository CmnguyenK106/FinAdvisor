"""HTTP client for the Go data gateway."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict

import requests


@dataclass
class DataGatewayClient:
    base_url: str
    timeout_seconds: int = 20

    def _get(self, path: str, params: Dict[str, Any]) -> Dict[str, Any]:
        url = f"{self.base_url}{path}"
        response = requests.get(url, params=params, timeout=self.timeout_seconds)
        response.raise_for_status()
        return response.json()

    def price_history(
        self,
        symbol: str,
        range_param: str | None = "1y",
        start_date: str | None = None,
        end_date: str | None = None,
        limit: int | None = None,
    ) -> Dict[str, Any]:
        params: Dict[str, Any] = {"symbol": symbol}
        if start_date and end_date:
            params["startDate"] = start_date
            params["endDate"] = end_date
        elif range_param:
            params["range"] = range_param
        if limit:
            params["limit"] = limit
        return self._get("/data/price", params)

    def financials(self, symbol: str) -> Dict[str, Any]:
        return self._get("/data/financials", {"symbol": symbol})

    def ratios(self, symbol: str) -> Dict[str, Any]:
        """Fetch fundamental ratios (P/E, P/B, EPS, ROE) from the gateway.

        The `fundamental()` method that previously existed here was removed
        because it was never called by the graph — `/data/ratios` is the
        single source for fundamental data.  The mapper alias for "fundamental"
        has also been removed from fireant_mapper.py.
        """
        return self._get("/data/ratios", {"symbol": symbol})
