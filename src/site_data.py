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


def build(plan: dict, signals: list[dict], cal: list[pd.Timestamp], data_date,
          expected_last: str | None, stale: bool, history: dict | None = None) -> dict:
    hist = _enrich_curves(history if history is not None else _load_history())
    data_date = pd.Timestamp(data_date)
    sig = [s for s in signals if s.get("symbol") and s.get("buy_date") is not None]
    for s in sig:
        s["name"] = s.get("name") or names.name_of(s["symbol"])

    # 最近有信号的那一天作为页面"最近信号日"；候选 = 该日信号 + 下一交易日要买的（延迟不同，信号日可能更早）
    sig_dates = [pd.Timestamp(s["signal_date"]) for s in sig if pd.Timestamp(s["signal_date"]) <= data_date]
    eff_date = max(sig_dates) if sig_dates else data_date
    next_day = calendar_utils.next_trading_day(cal, data_date)
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

    selected = {(b["symbol"], pd.Timestamp(b["buy_date"])) for b in plan.get("buys", [])}
    candidates = []
    for s in sorted(todays, key=lambda x: (x["source"], x["symbol"])):
        key = (s["symbol"], pd.Timestamp(s["buy_date"]))
        chosen = key in selected
        decision = "计划买入" if chosen else ("候选（未进仓位）" if plan.get("buys") else "不买")
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

    warnings = []
    if stale:
        warnings.append(f"数据只到 {data_date.date()}（最近交易日 {expected_last}），以下为旧信号，请勿照做。")
    else:
        warnings.append(f"数据截至 {data_date.date()}；每个交易日 17:45 自动更新。红色=本策略，灰色=沪深300。")
    if hist.get("_missing"):
        warnings.append("历史绩效快照缺失：overall/yearly/trades 为空，仅展示当日信号。")

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
        "overall": hist.get("overall", {}),
        "yearly": hist.get("yearly", []),
        "latest": {"signal_date": eff_date.strftime("%Y-%m-%d"), "candidates": candidates},
        "pending": pending,
        "future_window": [],
        "stocks": hist.get("stocks", []),
        "trades": hist.get("trades", []),
        "curve": hist.get("curve", []),
        "benchmark_curve": hist.get("benchmark_curve", []),
        "year_curves": hist.get("year_curves", {}),
    }


def write(payload: dict, path=None) -> str:
    p = path or config.SITE_DATA_OUT
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    return str(p)
