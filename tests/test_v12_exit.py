# -*- coding: utf-8 -*-
import unittest

import pandas as pd

from src import bars, v12_signal


class TestV12Exit(unittest.TestCase):
    def test_300061_early_exit(self):
        d = bars.load_bars("300061", "2024-07-09", "2024-09-30")
        self.assertFalse(d.empty, "300061 无行情")
        buy_price = float(d.iloc[0]["raw_open"]) * 1.0005
        r = v12_signal.exit_decision(d, "2024-07-09", buy_price)
        self.assertEqual(r["reason"], "LIMIT_BREAK_CLOSE")
        self.assertEqual(pd.Timestamp(r["exit_date"]).strftime("%Y-%m-%d"), "2024-08-01")
        self.assertAlmostEqual(r["exit_price"], 8.61, places=2)

    def test_000793_limit_down_defer(self):
        d = bars.load_bars("000793", "2024-06-03", "2024-09-30")
        self.assertFalse(d.empty)
        buy_price = float(d.iloc[0]["raw_open"]) * 1.0005
        r = v12_signal.exit_decision(d, "2024-06-03", buy_price)
        self.assertIn(r["reason"], ("LIMIT_BREAK_DEFERRED",))
        self.assertEqual(pd.Timestamp(r["exit_date"]).strftime("%Y-%m-%d"), "2024-06-18")
        self.assertAlmostEqual(r["exit_price"], 1.45, places=2)
        self.assertEqual(r["defer_days"], 1)

    def test_time_exit_no_trigger(self):
        d = bars.load_bars("002420", "2018-02-07", "2018-12-31")
        if d.empty:
            self.skipTest("无 002420 行情")
        buy_price = float(d.iloc[0]["raw_open"]) * 1.0005
        r = v12_signal.exit_decision(d, "2018-02-07", buy_price)
        self.assertIn(r["reason"], ("TIME", "TIME_DEFERRED"))


if __name__ == "__main__":
    unittest.main()
