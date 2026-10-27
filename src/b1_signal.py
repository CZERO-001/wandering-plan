# -*- coding: utf-8 -*-
"""B1 爆破信号：读取 BP1.0 日更结果并标准化。"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from . import config


def load_signals(path: Path | None = None) -> list[dict]:
    p = Path(path or config.B1_JSON)
    if not p.exists():
        return []
    data = json.loads(p.read_text(encoding="utf-8"))
    rows = data.get("rows", [])
    out = []
    for r in rows:
        if not r.get("signal_date") or not r.get("buy_date"):
            continue
        out.append({
            "source": "B1",
            "symbol": str(r["symbol"]).zfill(6),
            "name": r.get("name", ""),
            "signal_date": pd.Timestamp(r["signal_date"]),
            "buy_date": pd.Timestamp(r["buy_date"]),
            "sell_date": pd.Timestamp(r["sell_date"]) if r.get("sell_date") else None,
        })
    return out


def latest_signal_date(path: Path | None = None) -> pd.Timestamp | None:
    sig = load_signals(path)
    return max((s["signal_date"] for s in sig), default=None)
