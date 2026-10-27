# -*- coding: utf-8 -*-
"""从 BP2.3 页面模板生成『流浪计划』页面（与现有策略页同壳）。"""
from __future__ import annotations

import datetime
import shutil

from . import config

TPL = config.CZERO_WEB / "site" / "bp2-3" / "index.html"
OUT_DIR = config.SITE_OUT
OUT = OUT_DIR / "index.html"

REPL = [
    ("<title>BP2.3</title>", "<title>流浪计划</title>"),
    ('<div class="eyebrow">BP2.3</div>', '<div class="eyebrow">流浪计划</div>'),
    ("<h1>爆破2.3实时策略页</h1>", "<h1>流浪计划实时策略页</h1>"),
    ('<body data-api="/api/bp2-3/data">', '<body data-api="/api/wandering-plan/data">'),
    ("<div>数据源：本机 BP2.3 回测与每日信号；每年独立按 10 万本金重算，最新候选单独列出。</div>",
     "<div>数据源：已逐笔核验的 610 笔回测（B1 313 / QL2 266 / V12 31）；2 仓 × 50% 复利。</div>"),
    ("<div>冠军参数 m3|1.0/1.0/0.8|low0.1|q40|zskip|k3|h1；已知代价：全期最大回撤 -44.70%（BP2.2 为 -44.55%）。</div>",
     "<div>三路信号：B1 爆破 / QL2 冠军 / 双波 O1+C3（V1.2 离场）；每日 17:45 自动更新。</div>"),
]


def build_page(backup: bool = True) -> tuple[str, list[str]]:
    if not TPL.exists():
        raise FileNotFoundError(f"template missing: {TPL}")
    html = TPL.read_text(encoding="utf-8")
    missing = []
    for a, b in REPL:
        if a not in html:
            missing.append(a[:50])
            continue
        html = html.replace(a, b)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    if backup and OUT.exists():
        shutil.copy2(OUT, OUT_DIR / ("index.html.bak-" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S")))
    OUT.write_text(html, encoding="utf-8")
    return str(OUT), missing
