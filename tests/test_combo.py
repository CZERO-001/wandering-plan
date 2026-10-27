# -*- coding: utf-8 -*-
import unittest

import pandas as pd

from src import combo
from src import calendar_utils


def mk(source, symbol, buy, sell=None):
    return {"source": source, "symbol": symbol, "name": "", "signal_date": pd.Timestamp(buy) - pd.Timedelta(days=3),
            "buy_date": pd.Timestamp(buy), "sell_date": pd.Timestamp(sell) if sell else None}


class TestCombo(unittest.TestCase):
    def setUp(self):
        self.cal = calendar_utils.trade_calendar()
        # 数据日 2026-10-23（周五），下一交易日 2026-10-26
        self.data_date = pd.Timestamp("2026-10-23")
        self.next_day = calendar_utils.next_trading_day(self.cal, self.data_date)

    def test_priority_and_cap(self):
        sig = [
            mk("V12", "000001", self.next_day),
            mk("QL2", "000002", self.next_day),
            mk("B1", "000003", self.next_day),
        ]
        plan = combo.build_plan(sig, self.cal, self.data_date, capital=100000)
        self.assertEqual(plan["status"], "buy")
        self.assertEqual([s["source"] for s in plan["buys"]], ["B1", "QL2"])
        self.assertEqual(plan["buys"][0]["position_amount"], 50000)

    def test_no_signal(self):
        sig = [mk("B1", "000003", pd.Timestamp("2026-10-20"))]
        plan = combo.build_plan(sig, self.cal, self.data_date, capital=100000)
        self.assertEqual(plan["status"], "no_signal")
        self.assertEqual(plan["buys"], [])

    def test_single_stream_cap(self):
        sig = [mk("B1", f"00000{i}", self.next_day) for i in range(1, 5)]
        plan = combo.build_plan(sig, self.cal, self.data_date, capital=100000)
        self.assertLessEqual(len(plan["buys"]), 2)


if __name__ == "__main__":
    unittest.main()
