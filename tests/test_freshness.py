# -*- coding: utf-8 -*-
import unittest

import pandas as pd

from src import freshness


class TestFreshness(unittest.TestCase):
    def setUp(self):
        self.cal = [pd.Timestamp("2026-10-27"), pd.Timestamp("2026-10-28"),
                    pd.Timestamp("2026-10-29"), pd.Timestamp("2026-10-30")]

    def test_before_close_uses_previous_day(self):
        self.assertEqual(freshness.last_completed_trading_day(self.cal, pd.Timestamp("2026-10-29 14:59")),
                         pd.Timestamp("2026-10-28"))

    def test_after_close_uses_today(self):
        self.assertEqual(freshness.last_completed_trading_day(self.cal, pd.Timestamp("2026-10-29 15:00")),
                         pd.Timestamp("2026-10-29"))

    def test_weekend_uses_friday(self):
        self.assertEqual(freshness.last_completed_trading_day(self.cal, pd.Timestamp("2026-10-31 12:00")),
                         pd.Timestamp("2026-10-30"))


if __name__ == "__main__":
    unittest.main()
