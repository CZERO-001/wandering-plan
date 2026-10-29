# -*- coding: utf-8 -*-
"""把当日信号烘成站点同格式 JSON（与 bp2_3.json 对齐，app.js 直接渲染）。"""
from __future__ import annotations

import json
from datetime import datetime

import numpy as np
import pandas as pd

from . import calendar_utils, config, names

BENCH_CSV = config.ROOT / "data" / "index" / "sh000300.csv"


def _load_history() -> dict:
    p = config.HISTORY_JSON
    if not p.exists():
        return {"overall": {}, "yearly": [], "stocks": [], "trades": [], "_missing": True}
    return json.loads(p.read_text(encoding="utf-8"))


def _board(symbol: str) -> str:
    s = str(symbol).zfill(6)
    if s.startswith(("300", "301")):
        return "创业板"
    if s.startswith(("600", "601", "603", "605", "000", "001", "002", "003")):
        return "主板"
    return "其他"


def _bench_series() -> pd.Series:
    try:
        b = pd.read_csv(BENCH_CSV, encoding="utf-8-sig")
        b["date"] = pd.to_datetime(b["date"])
        return b.sort_values("date").drop_duplicates("date").set_index("date")["close"]
    except Exception:
        return pd.Series(dtype=float)


def _bench_at(bench: pd.Series, d) -> float | None:
    if bench.empty:
        return None
    d = pd.Timestamp(d)
    s = bench[bench.index <= d]
    if len(s):
        return float(s.iloc[-1])
    s = bench[bench.index >= d]
    return float(s.iloc[0]) if len(s) else None


def _extend_bench(bench: pd.Series, data_date) -> pd.Series:
    if bench.empty:
        return bench
    d = pd.Timestamp(data_date)
    if bench.index.max() >= d:
        return bench
    try:
        import urllib.request
        req = urllib.request.Request("https://hq.sinajs.cn/list=sh000300",
                                     headers={"Referer": "https://finance.sina.com.cn",
                                              "User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=8) as r:
            txt = r.read().decode("gbk", "replace")
        f = txt.split('"')[1].split(",")
        cur_date = pd.Timestamp(f[30])
        close, prev = float(f[3]), float(f[2])
        prev_day = pd.Timestamp(pd.bdate_range(end=cur_date, periods=2)[0])
        add = {}
        if prev_day > bench.index.max() and prev_day <= d:
            add[prev_day] = prev
        if cur_date > bench.index.max() and cur_date <= d:
            add[cur_date] = close
        if add:
            bench = pd.concat([bench, pd.Series(add)]).sort_index()
    except Exception:
        pass
    return bench


def _enrich_curves(hist: dict) -> dict:
    """给 history 补 benchmark_curve / year_curves / yearly.benchmark_return。"""
    bench = _bench_series()
    curve = [dict(x) for x in hist.get("curve", []) if x.get("equity")]
    if not curve or bench.empty:
        hist["benchmark_curve"] = []
        hist["year_curves"] = {}
        return hist
    b0 = _bench_at(bench, curve[0]["date"])
    bcurve = []
    for p in curve:
        b = _bench_at(bench, p["date"])
        if b is None or not b0:
            continue
        bcurve.append({"date": p["date"], "equity": round(100000.0 * b / b0, 2),
                       "return_pct": round((b / b0 - 1) * 100, 2)})
    hist["benchmark_curve"] = bcurve
    hist["meta_benchmark_as_of"] = bench.index.max().strftime("%Y-%m-%d") if len(bench) else None
    # yearly benchmark return
    yearly = hist.get("yearly", [])
    by_year = {}
    for y in yearly:
        yy = str(y["year"])
        arr = [p for p in curve if str(p["date"]).startswith(yy)]
        if len(arr) >= 1:
            bs = _bench_at(bench, arr[0]["date"])
            be = _bench_at(bench, arr[-1]["date"])
            by_year[int(y["year"])] = {"start_equity": arr[0]["equity"],
                                        "benchmark_return": (be / bs - 1) if bs and be else None}
            y["benchmark_return"] = by_year[int(y["year"])]["benchmark_return"]
            y["start_equity"] = arr[0]["equity"]
    year_curves = {}
    for yy in by_year:
        arr = [p for p in curve if str(p["date"]).startswith(str(yy))]
        if len(arr) < 2:
            continue
        base_eq = float(arr[0]["equity"])
        b0y = _bench_at(bench, arr[0]["date"])
        strategy = [{"date": p["date"], "equity": round(100000.0 * p["equity"] / base_eq, 2),
                     "return_pct": round((p["equity"] / base_eq - 1) * 100, 2)} for p in arr]
        bcurve_y = []
        for p in arr:
            b = _bench_at(bench, p["date"])
            if b is None or not b0y:
                continue
            bcurve_y.append({"date": p["date"], "equity": round(100000.0 * b / b0y, 2),
                             "return_pct": round((b / b0y - 1) * 100, 2)})
        year_curves[str(yy)] = {"base_date": arr[0]["date"], "strategy": strategy, "benchmark": bcurve_y}
    hist["year_curves"] = year_curves
    return hist


def _next_days(cal, data_date, n: int = 5) -> list[pd.Timestamp]:
    days = [d for d in cal if d > pd.Timestamp(data_date)]
    return days[:n]


def _replay_live(sig: list[dict], cal: list[pd.Timestamp], data_date, last_bt) -> list[dict]:
    """按 QL2.0 规则（delay=2 hold=1 满 3 个交易日才接下一信号）与 2 槽/单路上限回放。"""
    cal_idx = {pd.Timestamp(d): i for i, d in enumerate(cal)}
    ql2 = sorted([s for s in sig if s["source"] == "QL2"], key=lambda s: pd.Timestamp(s["signal_date"]))
    kept_ql2, last_si = [], None
    gap = config.BUY_DELAY["QL2"] + config.SELL_DELAY["QL2"]
    for s in ql2:
        si = cal_idx.get(pd.Timestamp(s["signal_date"]))
        if si is None:
            continue
        if last_si is not None and si - last_si < gap:
            continue
        kept_ql2.append(s)
        last_si = si
    cands = {}
    for s in [x for x in sig if x["source"] != "QL2"] + kept_ql2:
        if s.get("buy_date") is None:
            continue
        bd = pd.Timestamp(s["buy_date"])
        if last_bt is not None and bd <= last_bt:
            continue
        key = (s["symbol"], bd)
        cur = cands.get(key)
        if cur is None or config.PRIORITY.index(s["source"]) < config.PRIORITY.index(cur["source"]):
            cands[key] = s
    ordered = sorted(cands.values(), key=lambda s: (pd.Timestamp(s["buy_date"]), config.PRIORITY.index(s["source"])))
    allocated: list[dict] = []
    for s in ordered:
        bd = pd.Timestamp(s["buy_date"])
        sd = pd.Timestamp(s["sell_date"]) if s.get("sell_date") is not None else None
        active = [a for a in allocated if a["sell_date"] is not None and a["sell_date"] > bd]
        if len(active) >= config.SLOTS:
            continue
        if sum(1 for a in active if a["source"] == s["source"]) >= config.MAX_PER_STREAM.get(s["source"], 1):
            continue
        allocated.append({"symbol": s["symbol"], "name": s.get("name", ""), "source": s["source"],
                          "signal_date": pd.Timestamp(s["signal_date"]),
                          "buy_date": bd, "sell_date": sd})
    return allocated


def _dashboard(sig: list[dict], cal: list[pd.Timestamp], eff_date: pd.Timestamp, data_date: pd.Timestamp,
               allocated: list[dict], trades: list[dict] | None = None) -> dict:
    from . import prices

    today = pd.Timestamp.today().normalize()
    next_day = calendar_utils.next_trading_day(cal, today)
    data_date = pd.Timestamp(data_date)
    trade_map = {}
    for t in (trades or []):
        trade_map[(t.get("symbol"), str(t.get("buy_date")))] = t

    def _trade_of(sym, bd):
        return trade_map.get((sym, str(pd.Timestamp(bd).strftime("%Y-%m-%d"))))

    def _item(a, kind, show_pnl=False):
        d = pd.Timestamp(a["buy_date"]) if kind == "买入" else (pd.Timestamp(a["sell_date"]) if a.get("sell_date") is not None else None)
        if d is None:
            return None
        it = {"symbol": a["symbol"], "name": a.get("name", ""), "source": a["source"],
              "date": d.strftime("%Y-%m-%d"), "action": kind,
              "time": "09:30" if kind == "买入" else "15:00"}
        if kind == "买入":
            it["price"] = prices.open_on(a["symbol"], d)
        else:
            entry = prices.open_on(a["symbol"], pd.Timestamp(a["buy_date"]))
            exitp = prices.close_on(a["symbol"], d)
            if exitp is None:
                exitp = prices.close_on_or_before(a["symbol"], data_date)[1]
            it["entry"] = entry
            it["price"] = exitp
            if show_pnl:
                tr = _trade_of(a["symbol"], a["buy_date"])
                if tr is not None:
                    it["pnl_pct"], it["pnl_amount"] = tr.get("return_pct"), tr.get("net_profit")
        return it

    order = {"买入": 0, "卖出": 1}
    today_actions, tomorrow_actions = [], []
    for a in allocated:
        bd, sd = a["buy_date"], a.get("sell_date")
        if bd == today:
            today_actions.append(_item(a, "买入"))
        if sd is not None and sd == today:
            today_actions.append(_item(a, "卖出", True))
        if next_day is not None and bd == next_day:
            tomorrow_actions.append(_item(a, "买入"))
        if next_day is not None and sd is not None and sd == next_day:
            tomorrow_actions.append(_item(a, "卖出", True))
    today_actions = [x for x in today_actions if x]
    tomorrow_actions = [x for x in tomorrow_actions if x]
    today_actions.sort(key=lambda x: order.get(x["action"], 9))
    tomorrow_actions.sort(key=lambda x: order.get(x["action"], 9))

    holdings = []
    for a in sorted(allocated, key=lambda x: x["buy_date"], reverse=True):
        bd, sd = a["buy_date"], a.get("sell_date")
        if bd < today and (sd is None or sd > today):
            entry = prices.open_on(a["symbol"], bd)
            last = prices.close_on(a["symbol"], data_date)
            if last is None:
                last = prices.close_on_or_before(a["symbol"], data_date)[1]
            tr = _trade_of(a["symbol"], bd)
            pct = tr.get("return_pct") if tr else None
            if pct is None and entry and last:
                pct = round((last / entry - 1) * 100, 2)
            holdings.append({"symbol": a["symbol"], "name": a.get("name", ""), "source": a["source"],
                             "buy_date": bd.strftime("%Y-%m-%d"),
                             "sell_date": sd.strftime("%Y-%m-%d") if sd is not None else None,
                             "entry": entry, "last": last, "pnl_pct": pct, "pnl_amount": None})
        if len(holdings) >= 2:
            break

    future_days = [d for d in cal if next_day is not None and pd.Timestamp(d) > next_day][:6]
    future_set = {pd.Timestamp(d) for d in future_days}
    todo: dict[str, list[dict]] = {}
    for a in allocated:
        for kind, d in (("买入", a["buy_date"]), ("卖出", a.get("sell_date"))):
            if d is None or pd.Timestamp(d) not in future_set:
                continue
            it = _item(a, kind)
            if it:
                todo.setdefault(pd.Timestamp(d).strftime("%Y-%m-%d"), []).append(it)
    todo_days = [{"date": k, "items": sorted(v, key=lambda x: order.get(x["action"], 9))}
                 for k, v in sorted(todo.items())]

    latest_signals = [{"symbol": s["symbol"], "name": s.get("name", ""), "source": s["source"],
                       "signal_date": pd.Timestamp(s["signal_date"]).strftime("%Y-%m-%d"),
                       "buy_date": pd.Timestamp(s["buy_date"]).strftime("%Y-%m-%d"),
                       "sell_date": pd.Timestamp(s["sell_date"]).strftime("%Y-%m-%d") if s.get("sell_date") is not None else None}
                      for s in sig if pd.Timestamp(s["signal_date"]) == pd.Timestamp(eff_date)]
    return {"today": today.strftime("%Y-%m-%d"), "data_date": data_date.strftime("%Y-%m-%d"),
            "next_day": next_day.strftime("%Y-%m-%d") if next_day is not None else None,
            "holdings": holdings, "today_actions": today_actions,
            "tomorrow_actions": tomorrow_actions, "latest_signals": latest_signals,
            "todo_days": todo_days}


def build(plan: dict, signals: list[dict], cal: list[pd.Timestamp], data_date,
          expected_last: str | None, stale: bool, history: dict | None = None,
          stream_as_of: dict | None = None) -> dict:
    hist = _enrich_curves(history if history is not None else _load_history())
    data_date = pd.Timestamp(data_date)
    sig = [s for s in signals if s.get("symbol") and s.get("buy_date") is not None]
    for s in sig:
        s["name"] = s.get("name") or names.name_of(s["symbol"])

    # 最近有信号的那一天作为页面"最近信号日"；候选 = 该日信号 + 下一交易日要买的（延迟不同，信号日可能更早）
    sig_dates = [pd.Timestamp(s["signal_date"]) for s in sig if pd.Timestamp(s["signal_date"]) <= data_date]
    eff_date = max(sig_dates) if sig_dates else data_date
    next_day = calendar_utils.next_trading_day(cal, data_date)
    hist_trades = list(hist.get("trades", []))
    last_bt = max((pd.Timestamp(t["sell_date"]) for t in hist_trades if t.get("sell_date")), default=None)
    curve_list = hist.get("curve") or []
    allocated = _replay_live(sig, cal, data_date, last_bt)
    alloc_buys = {(a["symbol"], a["buy_date"]) for a in allocated}
    todays = []
    seen_sig = set()
    for s in sig:
        in_day = pd.Timestamp(s["signal_date"]) == eff_date
        actionable = next_day is not None and pd.Timestamp(s["buy_date"]) == pd.Timestamp(next_day)
        if not (in_day or actionable):
            continue
        key = (s["symbol"], pd.Timestamp(s["buy_date"]))
        if key in seen_sig:
            continue
        seen_sig.add(key)
        todays.append(s)

    candidates = []
    for s in sorted(todays, key=lambda x: (x["source"], x["symbol"])):
        key = (s["symbol"], pd.Timestamp(s["buy_date"]))
        chosen = key in alloc_buys
        decision = "计划买入" if chosen else "候选（未进仓位）"
        candidates.append({
            "symbol": s["symbol"],
            "name": s.get("name", ""),
            "board": _board(s["symbol"]),
            "source": s["source"],
            "signal_date": pd.Timestamp(s["signal_date"]).strftime("%Y-%m-%d"),
            "buy_date": pd.Timestamp(s["buy_date"]).strftime("%Y-%m-%d"),
            "sell_date": pd.Timestamp(s["sell_date"]).strftime("%Y-%m-%d") if s.get("sell_date") is not None else None,
            "hit_count": 1 if chosen else 0,
            "weight": 50.0 if chosen else 0.0,
            "decision": decision,
        })

    win = _next_days(cal, data_date, 5)
    win_set = set(win)
    pending = []
    seen = set()
    for s in sig:
        bd = pd.Timestamp(s["buy_date"])
        sd = pd.Timestamp(s["sell_date"]) if s.get("sell_date") is not None else None
        for kind, d in (("buy", bd), ("sell", sd)):
            if d is None or d not in win_set:
                continue
            k = (kind, s["symbol"], d)
            if k in seen:
                continue
            seen.add(k)
            pending.append({
                "symbol": s["symbol"],
                "name": s.get("name", ""),
                "board": _board(s["symbol"]),
                "signal_date": pd.Timestamp(s["signal_date"]).strftime("%Y-%m-%d"),
                "buy_date": bd.strftime("%Y-%m-%d") if kind == "buy" else ("—" if sd is None else bd.strftime("%Y-%m-%d")),
                "sell_date": sd.strftime("%Y-%m-%d") if sd is not None else None,
                "hit_count": 1 if kind == "buy" else 1,
                "weight": 50.0,
                "decision": "计划买入" if kind == "buy" else "计划卖出",
                "source": s["source"],
                "action_date": d.strftime("%Y-%m-%d"),
            })
    pending.sort(key=lambda x: (x["action_date"], 0 if x["decision"] == "计划买入" else 1))

    # ---- 按槽位/单路上限回放后的实盘成交并入逐笔与个股 ----
    from . import prices as _prices
    live_rows = []
    for a in allocated:
        bd = a["buy_date"]
        if bd > data_date:
            continue
        entry = _prices.open_on(a["symbol"], bd)
        if entry is None:
            continue
        sd = a.get("sell_date")
        closed = sd is not None and sd <= data_date
        if closed:
            exitp = _prices.close_on(a["symbol"], sd)
            status = "已平仓"
        else:
            exitp = _prices.close_on_or_before(a["symbol"], data_date)[1]
            status = "持仓中"
        if exitp is None:
            continue
        ret = exitp / entry - 1.0 - config.COST
        live_rows.append({
            "symbol": a["symbol"], "name": a.get("name", ""), "board": _board(a["symbol"]),
            "source": a["source"], "year": int(bd.year),
            "signal_date": pd.Timestamp(a["signal_date"]).strftime("%Y-%m-%d"),
            "buy_date": bd.strftime("%Y-%m-%d"),
            "sell_date": sd.strftime("%Y-%m-%d") if closed else None,
            "buy_price": round(float(entry), 2),
            "sell_price": round(float(exitp), 2) if closed else None,
            "return_pct": round(ret * 100, 2),
            "net_profit": 0.0,
            "position_amount": 0.0, "position_pct": 50.0,
            "balance_after": 0.0,
            "exit_reason": "TIME" if closed else "持仓中",
            "hit_count": 1, "weight": 50.0,
            "buy_time": "09:30", "sell_time": "15:00",
            "status": status,
        })
    trades = hist_trades + live_rows
    live_rows.sort(key=lambda r: (r.get("sell_date") or "9999-12-31", r["buy_date"]))
    _eq = float(curve_list[-1]["equity"]) if curve_list else float(config.INITIAL_CAPITAL)
    for _r in live_rows:
        _ret = float(_r["return_pct"]) / 100.0
        _pos = _eq * config.SLOT_WEIGHT
        _pnl = _pos * _ret
        _r["position_amount"] = round(_pos, 2)
        _r["net_profit"] = round(_pnl, 2)
        _r["balance_after"] = round(_eq + _pnl, 2)
        _eq = _eq + _pnl
    final_eq = _eq
    agg = {}
    for t in trades:
        sym = t["symbol"]
        a = agg.setdefault(sym, {"symbol": sym, "name": t.get("name", ""),
                                 "board": t.get("board") or _board(sym),
                                 "n": 0, "win": 0, "sum": 0.0, "net": 0.0, "last": ""})
        a["n"] += 1
        r = float(t.get("return_pct") or 0)
        a["sum"] += r
        a["net"] += float(t.get("net_profit") or 0)
        if r > 0:
            a["win"] += 1
        d = str(t.get("sell_date") or t.get("buy_date") or "")
        if d > a["last"]:
            a["last"] = d
    stocks = [{"symbol": k, "name": v["name"], "board": v["board"],
               "trades": v["n"], "win_rate": round(v["win"] / v["n"] * 100, 2),
               "avg_return": round(v["sum"] / v["n"], 2), "net_profit": round(v["net"], 2),
               "last_sell": v["last"]}
              for k, v in agg.items()]
    stocks.sort(key=lambda x: x["last_sell"], reverse=True)

    # ---- 曲线 / 基准 / 年化 / 回撤同步到最新（含 10 月实盘） ----
    curve = [dict(x) for x in curve_list]
    for _r in live_rows:
        if _r.get("sell_date"):
            curve.append({"date": _r["sell_date"], "equity": float(_r["balance_after"])})
    curve.append({"date": pd.Timestamp(data_date).strftime("%Y-%m-%d"), "equity": round(final_eq, 2)})
    _cmap = {}
    for _p in curve:
        _cmap[pd.Timestamp(_p["date"])] = float(_p["equity"])
    curve = [{"date": _d.strftime("%Y-%m-%d"), "equity": round(_v, 2),
              "return_pct": round((_v / config.INITIAL_CAPITAL - 1) * 100, 2)}
             for _d, _v in sorted(_cmap.items())]
    hist["curve"] = curve

    bench = _extend_bench(_bench_series(), data_date)
    b0 = _bench_at(bench, curve[0]["date"])
    bcurve = []
    for _p in curve:
        _b = _bench_at(bench, _p["date"])
        if _b is None or not b0:
            continue
        bcurve.append({"date": _p["date"], "equity": round(100000.0 * _b / b0, 2),
                       "return_pct": round((_b / b0 - 1) * 100, 2)})
    hist["benchmark_curve"] = bcurve
    hist["meta_benchmark_as_of"] = bench.index.max().strftime("%Y-%m-%d") if len(bench) else None

    yearly = hist.get("yearly", [])
    year_curves = {}
    for _y in yearly:
        _yy = str(_y["year"])
        _arr = [x for x in curve if str(x["date"]).startswith(_yy)]
        if not _arr:
            continue
        _prev = [x for x in curve if pd.Timestamp(x["date"]) < pd.Timestamp(f"{_yy}-01-01")]
        _start_eq = float(_prev[-1]["equity"]) if _prev else float(config.INITIAL_CAPITAL)
        _y["start_equity"] = round(_start_eq, 2)
        _y["year_return"] = round(_arr[-1]["equity"] / _start_eq - 1, 6)
        _nd = len([d for d in cal if pd.Timestamp(f"{_yy}-01-01") <= pd.Timestamp(d) <= pd.Timestamp(_arr[-1]["date"])])
        _y["trading_days"] = int(_nd)
        _complete = pd.Timestamp(data_date) >= pd.Timestamp(f"{int(_yy)}-12-31")
        _y["partial"] = not _complete
        if _complete:
            # 完整年度本身就是一年，年化=当年收益，不再用 252/交易日放大
            _y["annualized_return"] = round(_y["year_return"], 6)
        else:
            _y["annualized_return"] = round((1 + _y["year_return"]) ** (252.0 / max(_nd, 1)) - 1, 6)
        _vals = [_start_eq] + [x["equity"] for x in _arr]
        _ss = pd.Series(_vals)
        _y["max_drawdown"] = round(float((_ss / _ss.cummax() - 1).min()), 6)
        _sub = [t for t in trades if int(t.get("year") or 0) == int(_y["year"])]
        _y["trades"] = len(_sub)
        _y["net_profit"] = round(sum(float(t.get("net_profit") or 0) for t in _sub), 2)
        if _sub:
            _y["win_rate"] = round(sum(1 for t in _sub if float(t.get("return_pct") or 0) > 0) / len(_sub) * 100, 2)
        _b0 = _bench_at(bench, _arr[0]["date"])
        _strat = [{"date": x["date"], "equity": round(100000.0 * x["equity"] / _start_eq, 2),
                   "return_pct": round((x["equity"] / _start_eq - 1) * 100, 2)} for x in _arr]
        _by = []
        for x in _arr:
            _b = _bench_at(bench, x["date"])
            if _b is None or not _b0:
                continue
            _by.append({"date": x["date"], "equity": round(100000.0 * _b / _b0, 2),
                        "return_pct": round((_b / _b0 - 1) * 100, 2)})
        _y["benchmark_return"] = (_by[-1]["return_pct"] / 100.0) if _by else None
        year_curves[_yy] = {"base_date": _arr[0]["date"], "strategy": _strat, "benchmark": _by}
    hist["year_curves"] = year_curves

    overall = dict(hist.get("overall", {}))
    _fd = pd.Timestamp(curve[0]["date"]); _ld = pd.Timestamp(curve[-1]["date"])
    _years = max((_ld - _fd).days / 365.25, 0.1)
    _total = final_eq / config.INITIAL_CAPITAL - 1
    _eqs = pd.Series([x["equity"] for x in curve])
    _mdd = float((_eqs / _eqs.cummax() - 1).min())
    overall["total_return"] = round(_total, 6)
    overall["total_profit"] = round(final_eq - config.INITIAL_CAPITAL, 2)
    overall["annualized_return"] = round((1 + _total) ** (1 / _years) - 1, 6)
    overall["max_drawdown"] = round(_mdd, 6)
    overall["calmar"] = round(overall["annualized_return"] / abs(_mdd), 3) if _mdd else None
    overall["closed_trades"] = sum(1 for t in trades if t.get("sell_date"))

    warnings = []
    if stale:
        warnings.append(f"数据只到 {data_date.date()}（最近交易日 {expected_last}），以下为旧信号，请勿照做。")
    else:
        warnings.append(f"数据截至 {data_date.date()}；每个交易日 17:45 自动更新。红色=本策略，灰色=沪深300。")
    if hist.get("_missing"):
        warnings.append("历史绩效快照缺失：overall/yearly/trades 为空，仅展示当日信号。")
    # 分流数据管道日期（如实提示，避免误解为"信号丢失"）
    if stream_as_of:
        lagging = []
        for src in ("B1", "QL2", "V12"):
            dt = stream_as_of.get(src)
            if dt and pd.Timestamp(dt) < data_date:
                lagging.append(f"{src} 数据至 {pd.Timestamp(dt).date()}")
        if lagging:
            warnings.append("部分管道最后信号较旧：" + "、".join(lagging) + "（无新信号时不产生候选）")

    meta = {
        "model": "流浪计划",
        "version": config.__dict__.get("__version__", "1.0.0") if False else "1.0.0",
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "signal_as_of": eff_date.strftime("%Y-%m-%d"),
        "price_as_of": data_date.strftime("%Y-%m-%d"),
        "table_generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "last_trading_day": expected_last,
        "benchmark_as_of": hist.get("meta_benchmark_as_of"),
        "initial_cash": config.INITIAL_CAPITAL,
        "capital_mode": "two_slot_50pct",
        "capital_mode_label": "2 仓 × 50% 复利",
        "warnings": warnings,
        "stale": bool(stale),
        "signals": {
            "B1": sum(1 for s in sig if s["source"] == "B1"),
            "QL2": sum(1 for s in sig if s["source"] == "QL2"),
            "V12": sum(1 for s in sig if s["source"] == "V12"),
        },
    }
    return {
        "meta": meta,
        "overall": overall,
        "yearly": hist.get("yearly", []),
        "latest": {"signal_date": eff_date.strftime("%Y-%m-%d"), "candidates": candidates},
        "pending": pending,
        "future_window": [],
        "stocks": stocks,
        "trades": trades,
        "curve": hist.get("curve", []),
        "benchmark_curve": hist.get("benchmark_curve", []),
        "year_curves": hist.get("year_curves", {}),
        "dashboard": _dashboard(sig, cal, eff_date, data_date, allocated, trades),
    }


def write(payload: dict, path=None) -> str:
    p = path or config.SITE_DATA_OUT
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    return str(p)
