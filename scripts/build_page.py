"""Generate site page from the BP2.3 template (same shell as other strategies)."""
from __future__ import annotations

import datetime
import shutil
from pathlib import Path

import sys
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from src import config  # noqa: E402

TPL = config.CZERO_WEB / "site" / "bp2-3" / "index.html"
OUT_DIR = config.SITE_OUT
OUT = OUT_DIR / "index.html"

REPL = [
    ("<title>BP2.3</title>", "<title>流浪计划</title>"),
    ('<div class="eyebrow">BP2.3</div>', '<div class="eyebrow">流浪计划</div>'),
    ("<h1>爆破2.3实时策略页</h1>", "<h1>流浪计划实时策略页</h1>"),
    ('<body data-api="/api/bp2-3/data">', '<body data-api="/api/wandering-plan/data">'),
    ('<div class="top-actions"><a class="nav-link" href="/bp2-0/">BP2.0 对照</a><a class="nav-link" href="/ql1/">QL1.0 收益冠军</a><a class="nav-link" href="/double-wave/">双波策略 V1.1</a><a class="nav-link" href="/live/">我的实盘</a>',
     '<div class="top-actions"><a class="nav-link" href="/">BP2.3 首页</a><a class="nav-link" href="/bp2-0/">BP2.0 对照</a><a class="nav-link" href="/ql2/">QL2.0 收益冠军</a><a class="nav-link" href="/double-wave/">双波策略 V1.1</a><a class="nav-link" href="/live/">我的实盘</a>'),
    ("<div>数据源：本机 BP2.3 回测与每日信号；每年独立按 10 万本金重算，最新候选单独列出。</div>",
     "<div>数据源：已逐笔核验的 610 笔回测（B1 313 / QL2 266 / V12 31）；2 仓 × 50% 复利。</div>"),
    ("<div>冠军参数 m3|1.0/1.0/0.8|low0.1|q40|zskip|k3|h1；已知代价：全期最大回撤 -44.70%（BP2.2 为 -44.55%）。</div>",
     "<div>三路信号：B1 爆破 / QL2 冠军 / 双波 O1+C3（V1.2 离场）；每日 17:45 自动更新。</div>"),
]


def main() -> int:
    if not TPL.exists():
        print("template missing:", TPL)
        return 1
    html = TPL.read_text(encoding="utf-8")
    missing = []
    for a, b in REPL:
        if a not in html:
            missing.append(a[:50])
            continue
        html = html.replace(a, b)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    if OUT.exists():
        shutil.copy2(OUT, OUT_DIR / ("index.html.bak-" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S")))
    OUT.write_text(html, encoding="utf-8")
    print("written", OUT, len(html), "missing:", missing)
    return 0 if not missing else 2


if __name__ == "__main__":
    raise SystemExit(main())
