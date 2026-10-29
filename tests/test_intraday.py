# -*- coding: utf-8 -*-
import unittest

import pandas as pd

from src import intraday


SAMPLE = ('var hq_str_sz301313="凡拓数创,60.510,63.000,64.900,68.700,60.510,'
          '64.900,64.910,24333755,1578856848.800,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,'
          '2026-10-29,14:39:06,00";')


class TestIntraday(unittest.TestCase):
    def test_parse_sina(self):
        q = intraday.parse_sina(SAMPLE)
        self.assertIn("301313", q)
        self.assertEqual(q["301313"]["name"], "凡拓数创")
        self.assertAlmostEqual(q["301313"]["price"], 64.9)
        self.assertAlmostEqual(q["301313"]["open"], 60.51)
        self.assertEqual(q["301313"]["time"], "14:39:06")

    def test_non_trading_day_skips(self):
        payload = {}
        out, status = intraday.build_snapshot(payload, now=pd.Timestamp("2026-10-31 12:00"))
        self.assertEqual(status, "non-trading-day")
        self.assertEqual(out, {})


if __name__ == "__main__":
    unittest.main()
