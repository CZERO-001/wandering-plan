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
                       "dashGrid", "今日操作", "明天买卖提醒", "未来几日计划操作",
                       "BP2.3 首页", "双波策略 V1.1"):
            self.assertIn(marker, html, marker)
        self.assertNotIn("爆破2.3实时策略页", html)
        self.assertNotIn("<title>BP2.3</title>", html)


if __name__ == "__main__":
    unittest.main()
