# -*- coding: utf-8 -*-
import unittest

from src import public_page


BASE = {"data_date": "2026-10-23", "next_day": "2026-10-26", "updated_at": "2026-10-23T18:00:00",
        "capital": 100000, "buys": [], "sells": [], "recent": [],
        "counts": {"B1": 0, "QL2": 0, "V12": 0}}


class TestPage(unittest.TestCase):
    def test_buy_state(self):
        plan = dict(BASE, status="buy", buys=[{
            "source": "B1", "symbol": "000001", "name": "测试股", "buy_date": "2026-10-26",
            "sell_date": "2026-10-27", "position_amount": 50000}])
        html = public_page.render(plan)
        self.assertIn("今天要买", html)
        self.assertIn("000001", html)
        self.assertIn("2026-10-26 09:30", html)
        self.assertIn("50,000", html)

    def test_no_signal_state(self):
        html = public_page.render(dict(BASE, status="no_signal"))
        self.assertIn("今天不用买", html)

    def test_stale_state(self):
        html = public_page.render(dict(BASE, status="buy"), stale=True, stale_reason="数据只到 2026-10-20")
        self.assertIn("信号未更新", html)
        self.assertIn("不要照做", html)

    def test_no_local_paths(self):
        html = public_page.render(dict(BASE, status="no_signal"))
        self.assertNotIn("D:\\", html)
        self.assertNotIn("AStockWorker", html)


if __name__ == "__main__":
    unittest.main()
