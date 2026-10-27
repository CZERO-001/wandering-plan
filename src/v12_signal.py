# -*- coding: utf-8 -*-
"""V12（O1+C3 + V1.2 离场）信号与离场判定。"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from . import bars, calendar_utils, config


# ---------------- 离场规则 ----------------

def _limit_price(prev_close: float, rate: float) -> float:
    return round(prev_close * (1.0 + rate), 2)


def _limit_down_price(prev_close: float, rate: float) -> float:
    return round(prev_close * (1.0 - rate), 2)


def _at(close: float, limit: float) -> bool:
    return bool(abs(close - limit) <= config.LIMIT_TOL)


def exit_decision(daily: pd.DataFrame, buy_date, buy_price: float,
                  hold_days: int = config.V12_HOLD,
                  min_profit: float = config.V12_MIN_PROFIT,
                  max_defer: int = 10) -> dict:
    """按 V1.2 规则判定卖出。

    daily: 含 date/raw_close/limit_rate，按日期升序，需覆盖买入日之后 hold_days+max_defer 个交易日。
    buy_price: 含滑点的实际买入价（raw_open * (1+slippage)）。
    返回 {exit_date, exit_price, reason, defer_days}；无数据时 reason=NO_DATA。
    """
    d = daily.copy()
    d["date"] = pd.to_datetime(d["date"])
    d = d[d["date"] >= pd.Timestamp(buy_date)].reset_index(drop=True)
    if d.empty or pd.Timestamp(d.at[0, "date"]) != pd.Timestamp(buy_date):
        return {"exit_date": None, "exit_price": np.nan, "reason": "NO_DATA", "defer_days": 0}

    closes = d["raw_close"].astype(float).to_numpy()
    rates = d["limit_rate"].astype(float).fillna(0.10).to_numpy()
    dates = d["date"].to_numpy()
    n = len(d)
    last = min(hold_days, n - 1)
    if last < 1:
        return {"exit_date": None, "exit_price": np.nan, "reason": "NO_DATA", "defer_days": 0}

    at_limit = [False] * n
    for i in range(1, n):
        at_limit[i] = _at(closes[i], _limit_price(closes[i - 1], rates[i]))

    def sellable_after(i: int) -> int | None:
        """i 日收盘跌停则顺延，返回第一个可卖日下标。"""
        k = i
        tries = 0
        while k < n and tries <= max_defer:
            if k > 0:
                ld = _limit_down_price(closes[k - 1], rates[k])
                if not _at(closes[k], ld):
                    return k
            else:
                return k
            k += 1
            tries += 1
        return None

    for i in range(1, last + 1):
        if not at_limit[i - 1] or at_limit[i]:
            continue
        if closes[i] / buy_price - 1.0 < min_profit:
            continue
        k = sellable_after(i)
        if k is None:
            continue
        return {"exit_date": pd.Timestamp(dates[k]), "exit_price": float(closes[k]),
                "reason": "LIMIT_BREAK_CLOSE" if k == i else "LIMIT_BREAK_DEFERRED",
                "defer_days": k - i}

    k = sellable_after(last)
    if k is None:
        return {"exit_date": None, "exit_price": np.nan, "reason": "NO_DATA", "defer_days": 0}
    return {"exit_date": pd.Timestamp(dates[k]), "exit_price": float(closes[k]),
            "reason": "TIME" if k == last else "TIME_DEFERRED", "defer_days": k - last}


def live_exit_for_position(symbol: str, buy_date, buy_price: float, as_of) -> dict:
    """给已有持仓判卖（读 PIT 数据）。"""
    start = pd.Timestamp(buy_date)
    end = pd.Timestamp(as_of) + pd.Timedelta(days=60)
    d = bars.load_bars(symbol, start.date(), end.date())
    return exit_decision(d, buy_date, buy_price)


# ---------------- 当日信号 ----------------

def load_signals(cal: list[pd.Timestamp] | None = None) -> list[dict]:
    cal = cal or calendar_utils.trade_calendar()
    out: list[dict] = []
    # 1) 最新 picks_v1_1.json
    if config.V11_PICKS.exists():
        try:
            payload = json.loads(config.V11_PICKS.read_text(encoding="utf-8"))
            as_of = pd.Timestamp(payload["as_of"])
            for combo in payload.get("combos", []):
                if combo.get("combo_id") != "O1+C3":
                    continue
                for p in combo.get("today_picks", []) or []:
                    buy = p.get("entry_date") or payload.get("next_entry_date")
                    if not buy:
                        continue
                    buy_ts = pd.Timestamp(buy)
                    sell = calendar_utils.shift(cal, buy_ts, config.V12_HOLD)
                    out.append({
                        "source": "V12",
                        "symbol": str(p.get("symbol", "")).zfill(6),
                        "name": p.get("name", ""),
                        "signal_date": as_of,
                        "buy_date": buy_ts,
                        "sell_date": pd.Timestamp(sell) if sell is not None else None,
                        "score": float(p.get("score") or 0.0),
                    })
        except Exception:
            pass
    # 2) 历史信号（补最近）
    if config.V11_HISTORY.exists():
        try:
            h = pd.read_parquet(config.V11_HISTORY)
            h["date"] = pd.to_datetime(h["date"])
            for r in h.tail(20).itertuples(index=False):
                buy = calendar_utils.shift(cal, r.date, config.BUY_DELAY["V12"])
                if buy is None:
                    continue
                sell = calendar_utils.shift(cal, buy, config.V12_HOLD)
                out.append({
                    "source": "V12",
                    "symbol": str(r.symbol).zfill(6),
                    "name": "",
                    "signal_date": pd.Timestamp(r.date),
                    "buy_date": pd.Timestamp(buy),
                    "sell_date": pd.Timestamp(sell) if sell is not None else None,
                    "score": float(getattr(r, "score", 0.0) or 0.0),
                })
        except Exception:
            pass
    # 去重（同 symbol+signal_date+source，优先 picks）
    seen = {}
    for s in out:
        key = (s["source"], s["symbol"], s["signal_date"])
        if key not in seen or (s.get("buy_date") and not seen[key].get("buy_date")):
            seen[key] = s
    return list(seen.values())


def latest_signal_date() -> pd.Timestamp | None:
    if config.V11_PICKS.exists():
        try:
            return pd.Timestamp(json.loads(config.V11_PICKS.read_text(encoding="utf-8"))["as_of"])
        except Exception:
            pass
    return None
