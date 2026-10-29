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
    return df.sort_values("date").reset_index(drop=True)


@lru_cache(maxsize=1)
def _extra() -> dict[tuple[str, pd.Timestamp], dict]:
    """最新快照（含 open/high/low/close/prev_close，兼容旧文件）。"""
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
    out: dict[tuple[str, pd.Timestamp], dict] = {}
    for r in df.itertuples(index=False):
        try:
            out[(r.symbol, pd.Timestamp(r.date))] = {
                "open": float(getattr(r, "open")),
                "high": float(getattr(r, "high", float("nan"))),
                "low": float(getattr(r, "low", float("nan"))),
                "close": float(getattr(r, "close")),
                "prev_close": float(getattr(r, "prev_close", float("nan"))),
            }
        except Exception:
            continue
    return out


def bar_on(symbol: str, date) -> dict | None:
    """返回某日 OHLC + 前收（raw 不复权口径）。"""
    sym = str(symbol).zfill(6)
    d = pd.Timestamp(date)
    ex = _extra()
    if (sym, d) in ex:
        return dict(ex[(sym, d)])
    df = _daily(sym)
    if df.empty:
        return None
    r = df[df["date"] == d]
    if r.empty:
        return None
    row = r.iloc[-1]
    prev_close = float("nan")
    earlier = df[df["date"] < d]
    if len(earlier):
        prev_close = float(earlier.iloc[-1]["close"])
    return {"open": float(row["open"]), "high": float(row["high"]),
            "low": float(row["low"]), "close": float(row["close"]),
            "prev_close": prev_close}


def ohlc(symbol: str, date) -> tuple[float, float] | None:
    b = bar_on(symbol, date)
    if not b:
        return None
    return b["open"], b["close"]


def open_on(symbol: str, date) -> float | None:
    b = bar_on(symbol, date)
    return b["open"] if b else None


def close_on(symbol: str, date) -> float | None:
    b = bar_on(symbol, date)
    return b["close"] if b else None


def low_on(symbol: str, date) -> float | None:
    b = bar_on(symbol, date)
    return b["low"] if b else None


def prev_close_on(symbol: str, date) -> float | None:
    b = bar_on(symbol, date)
    if not b:
        return None
    v = b.get("prev_close")
    return v if v is not None and pd.notna(v) else None


def close_on_or_before(symbol: str, date) -> tuple[pd.Timestamp | None, float | None]:
    sym = str(symbol).zfill(6)
    d = pd.Timestamp(date)
    best_d, best_c = None, None
    ex = _extra()
    for (s, dd), bar in ex.items():
        if s == sym and dd <= d and (best_d is None or dd > best_d):
            best_d, best_c = dd, float(bar["close"])
    df = _daily(sym)
    if not df.empty:
        sub = df[df["date"] <= d]
        if len(sub):
            row = sub.iloc[-1]
            if best_d is None or pd.Timestamp(row["date"]) > best_d:
                best_d, best_c = pd.Timestamp(row["date"]), float(row["close"])
    return best_d, best_c
