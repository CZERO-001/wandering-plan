# -*- coding: utf-8 -*-
import unittest

from src import ql2_exit


class TestQl2Exit(unittest.TestCase):
    def test_no_trigger_uses_close(self):
        px, reason = ql2_exit.stop_loss_exit(10.0, 10.2, 9.5, 9.8, 0.10, 9.7)
        self.assertEqual(px, 9.7)
        self.assertEqual(reason, "TIME")

    def test_intraday_trigger_fills_threshold(self):
        px, reason = ql2_exit.stop_loss_exit(10.0, 10.2, 9.0, 9.8, 0.10, 9.6)
        self.assertAlmostEqual(px, 9.1)
        self.assertEqual(reason, "STOP")

    def test_gap_down_fills_open(self):
        px, reason = ql2_exit.stop_loss_exit(10.0, 8.5, 8.2, 9.0, 0.10, 8.4)
        self.assertAlmostEqual(px, 8.5)
        self.assertEqual(reason, "STOP")

    def test_limit_down_blocked_uses_close(self):
        # 前收 9.0，跌停 8.1；跳空开在跌停附近，fill <= 跌停+容差 -> 不卖
        px, reason = ql2_exit.stop_loss_exit(10.0, 8.1, 8.0, 9.0, 0.10, 8.2)
        self.assertEqual(px, 8.2)
        self.assertEqual(reason, "TIME")

    def test_missing_data_uses_close(self):
        px, reason = ql2_exit.stop_loss_exit(10.0, None, None, 9.8, 0.10, 9.7)
        self.assertEqual(px, 9.7)
        self.assertEqual(reason, "TIME")

    def test_chinext_limit_rate(self):
        self.assertEqual(ql2_exit.limit_rate_of("300001"), 0.20)
        self.assertEqual(ql2_exit.limit_rate_of("000001"), 0.10)


if __name__ == "__main__":
    unittest.main()
