# -*- coding: utf-8 -*-
"""生成公网页面（自包含 HTML，无外部依赖、无 API、无需登录）。"""
from __future__ import annotations

import html as _html

from . import config

CSS = """
:root{--bg:#0d1117;--card:#161b22;--fg:#e6edf3;--muted:#8b949e;--green:#3fb950;--red:#f85149;--yellow:#d29922;--blue:#58a6ff}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);font-family:-apple-system,"PingFang SC","Microsoft YaHei",sans-serif}
.wrap{max-width:720px;margin:0 auto;padding:20px 16px 48px}
.title{font-size:20px;color:var(--muted);text-align:center;margin:8px 0 4px}
.sub{text-align:center;color:var(--muted);font-size:13px;margin-bottom:18px}
.card{background:var(--card);border-radius:18px;padding:26px 22px;margin-bottom:16px;border:1px solid #21262d}
.big{font-size:44px;font-weight:800;line-height:1.15;margin:6px 0}
.code{font-size:26px;color:var(--blue);font-weight:700;letter-spacing:1px}
.row{display:flex;justify-content:space-between;align-items:center;padding:14px 0;border-bottom:1px solid #21262d;font-size:17px}
.row:last-child{border-bottom:none}
.row .k{color:var(--muted)}
.row .v{font-weight:700;text-align:right}
.tag{display:inline-block;font-size:13px;padding:3px 10px;border-radius:999px;background:#1f6feb33;color:var(--blue);margin-right:6px}
.green{color:var(--green)}.red{color:var(--red)}.yellow{color:var(--yellow)}
.banner{background:#d2992233;border:1px solid var(--yellow);color:var(--yellow);border-radius:12px;padding:12px 16px;font-size:15px;margin-bottom:16px}
.h2{font-size:15px;color:var(--muted);margin:22px 0 10px;letter-spacing:1px}
.list{background:var(--card);border-radius:14px;overflow:hidden}
.item{padding:13px 16px;border-bottom:1px solid #21262d;font-size:15px;display:flex;justify-content:space-between}
.item:last-child{border-bottom:none}
.foot{color:var(--muted);font-size:12px;line-height:1.7;margin-top:24px;text-align:center}
.warn{color:var(--yellow)}
"""


def _fmt(d) -> str:
    return d.strftime("%m-%d") if hasattr(d, "strftime") else str(d)


def render(plan: dict, stale: bool = False, stale_reason: str = "") -> str:
    status = "stale" if stale else plan.get("status")
    updated = plan.get("updated_at", "")[:16].replace("T", " ")
    next_day = plan.get("next_day") or "-"
    cards: list[str] = []

    if status == "stale":
        cards.append(f'<div class="banner">⚠️ 信号未更新：{_html.escape(stale_reason or "数据还没准备好")}。以下为昨日内容，<b>不要照做</b>。</div>')
        status = plan.get("status", "no_signal")

    if status == "buy":
        for s in plan.get("buys", []):
            src = _html.escape(s.get("source", ""))
            code = _html.escape(s.get("symbol", ""))
            name = _html.escape(s.get("name", "") or "股票")
            buy = _html.escape(str(s.get("buy_date", ""))[:10])
            sell = _html.escape(str(s.get("sell_date", ""))[:10])
            amt = s.get("position_amount") or int(config.INITIAL_CAPITAL * config.SLOT_WEIGHT)
            cards.append(f"""
<div class="card">
  <div class="title">今天要买</div>
  <div class="big green">{name}<br><span class="code">{code}</span></div>
  <div style="margin-top:10px"><span class="tag">{src}</span></div>
  <div style="margin-top:14px">
    <div class="row"><span class="k">买入时间</span><span class="v">{buy} 09:30 开盘</span></div>
    <div class="row"><span class="k">卖出时间</span><span class="v">{sell} 14:57 收盘</span></div>
    <div class="row"><span class="k">建议仓位</span><span class="v">{amt:,.0f} 元（一半资金）</span></div>
  </div>
  <div class="foot" style="text-align:left;margin-top:14px">开盘若已涨停（买不进）就放弃这笔。</div>
</div>""")
    elif status == "no_signal":
        cards.append("""
<div class="card">
  <div class="title">今天不用买</div>
  <div class="big">空仓等待</div>
  <div class="foot" style="text-align:left">三路信号今天都没有触发买入。下一个交易日收盘后（约 17:45）再看。</div>
</div>""")

    sells = plan.get("sells", [])
    sell_html = ""
    if sells:
        items = "".join(
            f'<div class="item"><span>{_html.escape(s.get("symbol",""))} {_html.escape(s.get("name",""))}</span>'
            f'<span>{_html.escape(str(s.get("sell_date",""))[:10])} 收盘卖</span></div>'
            for s in sells)
        sell_html = f'<div class="h2">下一交易日要卖的</div><div class="list">{items}</div>'

    recent = plan.get("recent", [])
    recent_html = ""
    if recent:
        items = ""
        for s in recent:
            ret = s.get("return_pct")
            cls = "green" if (ret or 0) >= 0 else "red"
            rets = f"{ret:+.1f}%" if ret is not None else "—"
            items += (f'<div class="item"><span>{_html.escape(str(s.get("buy_date",""))[:10])} '
                      f'{_html.escape(s.get("symbol",""))} {_html.escape(s.get("source",""))}</span>'
                      f'<span class="{cls}">{rets}</span></div>')
        recent_html = f'<div class="h2">最近信号（已卖出）</div><div class="list">{items}</div>'

    counts = plan.get("counts", {})
    return f"""<!doctype html>
<html lang="zh-CN"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1">
<title>流浪计划 · 今日信号</title>
<style>{CSS}</style>
</head><body><div class="wrap">
<div class="title">流浪计划 · 今日信号</div>
<div class="sub">数据日期 {_html.escape(plan.get("data_date","-"))} · 更新 {_html.escape(updated)}</div>
{''.join(cards)}
{sell_html}
{recent_html}
<div class="h2">这一次看什么</div>
<div class="list">
  <div class="item"><span>三路信号</span><span>B1 {counts.get("B1",0)} / QL2 {counts.get("QL2",0)} / 双波 {counts.get("V12",0)}</span></div>
  <div class="item"><span>仓位规则</span><span>最多 2 笔，每笔一半资金</span></div>
  <div class="item"><span>下次更新时间</span><span>下个交易日 17:45 左右</span></div>
</div>
<div class="foot">
  研究演示，<span class="warn">不构成投资建议</span>，历史收益不代表未来。<br>
  数据来源：本地行情与 L2 数据；信号只在本机生成。
</div>
</div></body></html>"""


def write_page(plan: dict, stale: bool = False, stale_reason: str = "") -> str:
    config.SITE_OUT.mkdir(parents=True, exist_ok=True)
    html = render(plan, stale=stale, stale_reason=stale_reason)
    path = config.SITE_OUT / "index.html"
    path.write_text(html, encoding="utf-8")
    return html
