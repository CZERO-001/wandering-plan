# -*- coding: utf-8 -*-
"""持仓/卖出所需的个股价格：raw_sina 历史 + 最新快照（daily_extra/*.csv）。"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import pandas as pd

RAW = Path(r"D:\AStockWorker\data\raw_sina")
EXTRA_DIR = Path(r"D:\AStockWorker\data\daily_extra")


@lru_cache(maxsize=4096)
def _daily(symbol: str) -> pd.DataFrame:
    p = RAW / f"{str(symbol).zfill(6)}.csv"
    if not p.exists():
        return pd.DataFrame()
    df = pd.read_csv(p)
    df["date"] = pd.to_datetime(df["date"])
    return df.sort_values("date")


@lru_cache(maxsize=1)
def _extra() -> dict[tuple[str, pd.Timestamp], tuple[float, float]]:
    if not EXTRA_DIR.exists():
        return {}
    fs = sorted(EXTRA_DIR.glob("*.csv"))
    if not fs:
        return {}
    df = pd.read_csv(fs[-1], dtype={"symbol": str})
    if "symbol" not in df.columns:
        return {}
    df["symbol"] = df["symbol"].str.zfill(6)
    df["date"] = pd.to_datetime(df["date"])
    out = {}
    for r in df.itertuples(index=False):
        try:
            out[(r.symbol, pd.Timestamp(r.date))] = (float(r.open), float(r.close))
        except Exception:
            continue
    return out


def ohlc(symbol: str, date) -> tuple[float, float] | None:
    sym = str(symbol).zfill(6)
    d = pd.Timestamp(date)
    ex = _extra()
    if (sym, d) in ex:
        return ex[(sym, d)]
    df = _daily(sym)
    if df.empty:
        return None
    r = df[df["date"] == d]
    if r.empty:
        return None
    r = r.iloc[-1]
    return float(r["open"]), float(r["close"])


def open_on(symbol: str, date) -> float | None:
    v = ohlc(symbol, date)
    return v[0] if v else None


def close_on(symbol: str, date) -> float | None:
    v = ohlc(symbol, date)
    return v[1] if v else None


def close_on_or_before(symbol: str, date) -> tuple[pd.Timestamp | None, float | None]:
    sym = str(symbol).zfill(6)
    d = pd.Timestamp(date)
    best_d, best_c = None, None
    ex = _extra()
    for (s, dd), (_o, c) in ex.items():
        if s == sym and dd <= d and (best_d is None or dd > best_d):
            best_d, best_c = dd, c
    df = _daily(sym)
    if not df.empty:
        sub = df[df["date"] <= d]
        if len(sub):
            row = sub.iloc[-1]
            if best_d is None or pd.Timestamp(row["date"]) > best_d:
                best_d, best_c = pd.Timestamp(row["date"]), float(row["close"])
    return best_d, best_c
