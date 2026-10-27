# -*- coding: utf-8 -*-
import unittest

import pandas as pd

from src import calendar_utils, site_data


class TestSiteData(unittest.TestCase):
    def setUp(self):
        self.cal = calendar_utils.trade_calendar()
        self.data_date = pd.Timestamp("2026-10-23")
        next_day = calendar_utils.next_trading_day(self.cal, self.data_date)
        def mk(source, symbol, sig, buy, sell):
            return {"source": source, "symbol": symbol, "name": "", "signal_date": pd.Timestamp(sig),
                    "buy_date": pd.Timestamp(buy), "sell_date": pd.Timestamp(sell)}
        self.signals = [
            mk("B1", "000001", "2026-10-20", next_day, next_day),
            mk("QL2", "000002", "2026-10-23", "2026-10-27", "2026-10-28"),
            mk("V12", "000003", "2026-10-21", next_day, "2026-11-19"),
        ]
        self.plan = {"buys": [{"symbol": "000001", "buy_date": str(next_day), "position_amount": 50000,
                               "source": "B1", "name": ""}], "sells": []}

    def test_schema(self):
        payload = site_data.build(self.plan, self.signals, self.cal, self.data_date,
                                  "2026-10-23", False)
        for key in ("meta", "overall", "yearly", "latest", "pending", "stocks", "trades"):
            self.assertIn(key, payload)
        m = payload["meta"]
        for key in ("model", "generated_at", "signal_as_of", "stale", "warnings"):
            self.assertIn(key, m)
        self.assertIn("curve", payload)
        self.assertIn("benchmark_curve", payload)
        self.assertIn("year_curves", payload)
        self.assertEqual(payload["latest"]["signal_date"], "2026-10-23")
        chosen = [c for c in payload["latest"]["candidates"] if c["decision"] == "计划买入"]
        self.assertTrue(chosen)
        self.assertEqual(chosen[0]["symbol"], "000001")
        self.assertIsInstance(chosen[0]["weight"], float)
        for p in payload["pending"]:
            self.assertIn(p["decision"], ("计划买入", "计划卖出"))

    def test_stale_warning(self):
        payload = site_data.build(self.plan, self.signals, self.cal, self.data_date,
                                  "2026-10-27", True)
        self.assertTrue(payload["meta"]["stale"])
        self.assertTrue(payload["meta"]["warnings"])


if __name__ == "__main__":
    unittest.main()
