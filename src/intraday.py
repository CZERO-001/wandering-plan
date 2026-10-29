# -*- coding: utf-8 -*-
"""交易日 12:00 盘中快照：更新持仓现价与浮动盈亏（不改历史账本）。"""
from __future__ import annotations

import argparse
import json
import re
import urllib.request
from pathlib import Path

import pandas as pd

from . import b1_signal, calendar_utils, config, names, prices, ql2_signal, site_data, v12_signal

SINA_URL = "https://hq.sinajs.cn/list="
quotes: dict[str, dict] = {}


def _tx_symbol(symbol: str) -> str:
    s = str(symbol).zfill(6)
    return ("sh" if s.startswith(("5", "6", "9")) else "sz") + s


def parse_sina(raw: str) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for line in raw.splitlines():
        m = re.match(r'var hq_str_(\w+)="(.*?)";', line.strip())
        if not m:
            continue
        code = m.group(1)[2:]
        f = m.group(2).split(",")
        if len(f) < 32:
            continue
        try:
            out[code] = {"name": f[0], "open": float(f[1]), "prev_close": float(f[2]),
                         "price": float(f[3]), "high": float(f[4]), "low": float(f[5]),
                         "date": f[30], "time": f[31]}
        except (ValueError, IndexError):
            continue
    return out


def fetch_quotes(symbols: list[str]) -> dict[str, dict]:
    """Sina 批量实时行情；失败返回 {}。"""
    syms = [str(s).zfill(6) for s in symbols if s]
    if not syms:
        return {}
    out: dict[str, dict] = {}
    for i in range(0, len(syms), 40):
        batch = syms[i:i + 40]
        url = SINA_URL + ",".join(_tx_symbol(s) for s in batch)
        try:
            req = urllib.request.Request(url, headers={
                "Referer": "https://finance.sina.com.cn", "User-Agent": "Mozilla/5.0"})
            raw = urllib.request.urlopen(req, timeout=15).read().decode("gbk", "replace")
        except Exception:
            continue
        out.update(parse_sina(raw))
    return out


def build_snapshot(payload: dict, now=None) -> tuple[dict, str]:
    now = pd.Timestamp(now) if now is not None else pd.Timestamp.now()
    today = now.normalize()
    cal = calendar_utils.trade_calendar()
    if today not in set(pd.Timestamp(x) for x in cal):
        return payload, "non-trading-day"
    meta = payload.get("meta", {})
    data_date = pd.Timestamp(meta.get("price_as_of") or meta.get("signal_as_of"))
    hist = site_data._load_history()
    hist_trades = list(hist.get("trades", []))
    last_bt = max((pd.Timestamp(t["sell_date"]) for t in hist_trades if t.get("sell_date")), default=None)
    signals = b1_signal.load_signals() + ql2_signal.load_signals(cal) + v12_signal.load_signals(cal)
    allocated = site_data._replay_live(signals, cal, data_date, last_bt)
    trades = list(payload.get("trades", []))
    tmap = {(t.get("symbol"), str(t.get("buy_date"))): t for t in trades}

    def trade_of(sym, bd):
        return tmap.get((sym, str(pd.Timestamp(bd).strftime("%Y-%m-%d"))))

    def latest_equity():
        curve = payload.get("curve") or []
        if curve:
            return float(curve[-1].get("equity") or config.INITIAL_CAPITAL)
        return float(config.INITIAL_CAPITAL)

    holdings = []
    for a in sorted(allocated, key=lambda x: x["buy_date"], reverse=True):
        bd = pd.Timestamp(a["buy_date"])
        sd = pd.Timestamp(a["sell_date"]) if a.get("sell_date") is not None else None
        if bd > today or (sd is not None and sd < today):
            continue
        tr = trade_of(a["symbol"], bd)
        entry = None
        if tr and tr.get("buy_price"):
            entry = float(tr["buy_price"])
        if entry is None:
            entry = prices.open_on(a["symbol"], bd)
        q = quotes.get(a["symbol"])
        if entry is None and bd == today and q and q.get("open"):
            entry = q["open"]
        last = q["price"] if q else prices.close_on_or_before(a["symbol"], data_date)[1]
        if entry is None or last is None or entry <= 0:
            continue
        pos_amt = float(tr.get("position_amount") or 0) if tr else 0.0
        if pos_amt <= 0:
            pos_amt = latest_equity() * config.SLOT_WEIGHT
        pnl_pct = (float(last) / float(entry) - 1.0) * 100.0
        stop_px = round(float(entry) * (1.0 - config.QL2_STOP), 2) if a.get("source") == "QL2" else None
        holdings.append({
            "symbol": a["symbol"], "name": a.get("name") or names.name_of(a["symbol"]),
            "source": a.get("source", ""),
            "buy_date": bd.strftime("%Y-%m-%d"),
            "sell_date": sd.strftime("%Y-%m-%d") if sd is not None else None,
            "entry": round(float(entry), 3), "last": round(float(last), 3),
            "pnl_pct": round(pnl_pct, 2), "pnl_amount": round(float(pos_amt) * pnl_pct / 100.0, 2),
            "stop_px": stop_px, "quote_time": (q.get("time") if q else ""),
        })
        if len(holdings) >= config.SLOTS:
            break

    actions = []
    for a in allocated:
        bd = pd.Timestamp(a["buy_date"])
        sd = pd.Timestamp(a["sell_date"]) if a.get("sell_date") is not None else None
        q = quotes.get(a["symbol"])
        if bd == today:
            px = q["open"] if q and q.get("open") else prices.open_on(a["symbol"], bd)
            actions.append({"symbol": a["symbol"], "name": a.get("name") or names.name_of(a["symbol"]), "source": a.get("source", ""),
                            "date": today.strftime("%Y-%m-%d"), "action": "买入", "time": "09:30",
                            "price": round(float(px), 3) if px else None})
        if sd is not None and sd == today:
            tr = trade_of(a["symbol"], bd)
            entry = float(tr["buy_price"]) if tr and tr.get("buy_price") else prices.open_on(a["symbol"], bd)
            px = q["price"] if q and q.get("price") else prices.close_on(a["symbol"], today)
            if px is None:
                px = prices.close_on_or_before(a["symbol"], data_date)[1]
            it = {"symbol": a["symbol"], "name": a.get("name") or names.name_of(a["symbol"]),
                  "source": a.get("source", ""),
                  "date": today.strftime("%Y-%m-%d"), "action": "卖出", "time": "15:00",
                  "entry": entry, "price": round(float(px), 3) if px else None}
            if entry and px:
                it["pnl_pct"] = round((float(px) / float(entry) - 1.0) * 100.0, 2)
            if a.get("source") == "QL2" and entry:
                stop_px = round(float(entry) * (1.0 - config.QL2_STOP), 2)
                it["stop_px"] = stop_px
                it["note"] = f"盘中跌破 {stop_px:.2f} 止损，否则 15:00 收盘卖"
            actions.append(it)
    actions.sort(key=lambda x: 0 if x["action"] == "买入" else 1)

    dash = dict(payload.get("dashboard") or {})
    dash["holdings"] = holdings
    dash["today_actions"] = actions
    dash["intraday_at"] = now.strftime("%Y-%m-%d %H:%M:%S")
    dash["intraday_quotes"] = len(quotes)
    payload["dashboard"] = dash
    meta["intraday_at"] = now.strftime("%Y-%m-%d %H:%M:%S")
    meta["intraday_quotes"] = len(quotes)
    warnings = list(meta.get("warnings") or [])
    warnings = [w for w in warnings if "盘中快照" not in w]
    warnings.append(f"盘中快照：{now:%H:%M} 更新持仓现价与浮动盈亏（不改历史账本）。")
    meta["warnings"] = warnings
    return payload, "ok"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="流浪计划盘中快照")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--no-deploy", action="store_true")
    a = ap.parse_args(argv)
    payload = json.loads(config.SITE_DATA_OUT.read_text(encoding="utf-8"))
    global quotes
    symbols = []
    for h in ((payload.get("dashboard") or {}).get("holdings") or []):
        if h.get("symbol"):
            symbols.append(h["symbol"])
    # 持仓可能尚未写入旧 payload；从 allocations 取
    try:
        cal = calendar_utils.trade_calendar()
        hist = site_data._load_history()
        hist_trades = list(hist.get("trades", []))
        last_bt = max((pd.Timestamp(t["sell_date"]) for t in hist_trades if t.get("sell_date")), default=None)
        signals = b1_signal.load_signals() + ql2_signal.load_signals(cal) + v12_signal.load_signals(cal)
        allocated = site_data._replay_live(signals, cal, pd.Timestamp.now().normalize(), last_bt)
        symbols += [x["symbol"] for x in allocated]
    except Exception:
        pass
    quotes = fetch_quotes(sorted(set(symbols)))
    if not quotes:
        print("quotes empty; skip")
        return 1
    payload, status = build_snapshot(payload)
    if status != "ok":
        print("skip:", status)
        return 0
    print("intraday:", status, "holdings", len(payload["dashboard"]["holdings"]))
    if a.dry_run or a.no_deploy:
        return 0
    config.SITE_DATA_OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    from .daily_run import _deploy
    ok, detail = _deploy(config.SITE_OUT / "index.html")
    print("deploy:", ok, detail)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
