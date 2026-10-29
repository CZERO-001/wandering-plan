# -*- coding: utf-8 -*-
import unittest

from src import site_page


class TestSitePage(unittest.TestCase):
    def test_page_shell(self):
        path, missing = site_page.build_page(backup=False)
        self.assertEqual(missing, [])
        html = open(path, encoding="utf-8").read()
        for marker in ("流浪计划实时策略页", 'data-api="/api/wandering-plan/data"',
                       "assets/app.js", "latestCards", "pendingTable", "yearCards",
                       "curveBox", "yearCurveBox", "资金曲线", "年度曲线", "沪深300",
                       "dashHold", "dashToday", "dashTmr", "dashTodo", "今日持仓",
                       "今日操作", "明日买卖提醒", "交易日待办", "dash-title",
                       "V1.1", "止损", "0.91"):
            self.assertIn(marker, html, marker)
        self.assertNotIn("爆破2.3实时策略页", html)
        self.assertNotIn("<title>BP2.3</title>", html)
        # 只保留「我的实盘」入口，其余策略导航隐藏
        self.assertIn('href="/live/"', html)
        for gone in ('href="/bp2-0/"', 'href="/ql2/"', 'href="/double-wave/"', 'href="/bp2-3/"'):
            self.assertNotIn(gone, html, gone)


if __name__ == "__main__":
    unittest.main()
