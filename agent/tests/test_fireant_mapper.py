from datetime import datetime, timezone
import unittest

from agent.mappers.fireant_mapper import extract_fireant_metrics


class FireantMapperTests(unittest.TestCase):
    def test_metrics_mapping(self) -> None:
        payload = {
            "ratios": {
                "data": {
                    "symbol": "VCI",
                    "market_cap": 1000.0,
                    "pe_multiple": 10.0,
                    "pb_multiple": 1.5,
                    "dividend_yield": 0.02,
                    "eps": 100.0,
                    "roe": 0.1,
                }
            },
            "price_history": {
                "data": {
                    "quotes": [
                        {
                            "date": "2026-05-14T00:00:00",
                            "close": 10.0,
                        }
                    ]
                }
            },
            "financials": {
                "data": {
                    "financial_values": {
                        "totalDebt": 300.0,
                        "cash": 50.0,
                        "ebitda": 200.0,
                        "dividendPerShare": 0.4,
                    }
                }
            },
            "reports": {
                "data": {
                    "reports": [
                        {
                            "field": "NetCashFromOperatingActivities",
                            "values": [{"value": 120.0}, {"value": 130.0}],
                        },
                        {
                            "field": "Capex",
                            "values": [{"value": -40.0}, {"value": -50.0}],
                        },
                    ]
                }
            },
        }

        as_of = datetime(2026, 5, 15, tzinfo=timezone.utc)
        metrics = extract_fireant_metrics(payload, as_of=as_of)

        self.assertAlmostEqual(metrics["shares_outstanding"], 100.0)
        self.assertAlmostEqual(metrics["net_debt"], 250.0)
        self.assertAlmostEqual(metrics["dividend_per_share"], 0.4)
        self.assertEqual(metrics["data_recency_days"], 1)
        self.assertEqual(metrics["fcfs"], [160.0, 180.0])

    def test_dividend_fallback(self) -> None:
        payload = {
            "ratios": {
                "data": {
                    "symbol": "VCI",
                    "market_cap": 1000.0,
                    "dividend_yield": 0.02,
                }
            },
            "price_history": {
                "data": {
                    "quotes": [
                        {
                            "date": "2026-05-14T00:00:00",
                            "close": 10.0,
                        }
                    ]
                }
            },
        }

        metrics = extract_fireant_metrics(payload)
        self.assertAlmostEqual(metrics["dividend_per_share"], 0.2)

    def test_free_cash_flow_fallback(self) -> None:
        payload = {
            "financials": {
                "data": {
                    "financial_values": {
                        "freeCashFlow": 50.0
                    }
                }
            }
        }

        metrics = extract_fireant_metrics(payload)
        self.assertEqual(metrics["fcfs"], [50.0, 50.0])


if __name__ == "__main__":
    unittest.main()
