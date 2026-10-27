# -*- coding: utf-8 -*-
"""QL2 冠军信号：读取 champion_<date>.csv，取 candidate_score 第 1。"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from . import calendar_utils, config


def _champion_files(limit: int = 30) -> list[Path]:
    fs = sorted(config.WORK_DIR.glob(config.QL2_CHAMPION_GLOB))
    return fs[-limit:]


def load_signals(cal: list[pd.Timestamp] | None = None, limit: int = 30) -> list[dict]:
    cal = cal or calendar_utils.trade_calendar()
    out = []
    for f in _champion_files(limit):
        try:
            df = pd.read_csv(f, dtype={"symbol": str})
        except Exception:
            continue
        if df.empty or "candidate_score" not in df.columns:
            continue
        day = str(df["day"].iloc[0])
        sig_date = pd.to_datetime(day)
        top = df.sort_values("candidate_score", ascending=False).iloc[0]
        buy = calendar_utils.shift(cal, sig_date, config.BUY_DELAY["QL2"])
        sell = calendar_utils.shift(cal, buy, config.SELL_DELAY["QL2"]) if buy is not None else None
        if buy is None:
            continue
        out.append({
            "source": "QL2",
            "symbol": str(top["symbol"]).zfill(6),
            "name": "",
            "signal_date": sig_date,
            "buy_date": pd.Timestamp(buy),
            "sell_date": pd.Timestamp(sell) if sell is not None else None,
            "score": float(top["candidate_score"]),
        })
    return out


def latest_signal_date() -> pd.Timestamp | None:
    fs = _champion_files(1)
    if not fs:
        return None
    try:
        df = pd.read_csv(fs[-1], dtype={"symbol": str})
        return pd.to_datetime(str(df["day"].iloc[0])) if not df.empty else None
    except Exception:
        return None
