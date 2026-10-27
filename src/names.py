# -*- coding: utf-8 -*-
"""股票代码 → 名称（本地只读表）。"""
from __future__ import annotations

import pandas as pd

from . import config

_CACHE: dict[str, str] | None = None


def load_names() -> dict[str, str]:
    global _CACHE
    if _CACHE is not None:
        return _CACHE
    p = config.ROOT / "data" / "processed" / "stock_list.csv"
    out: dict[str, str] = {}
    try:
        df = pd.read_csv(p, dtype={"symbol": str})
        for r in df.itertuples(index=False):
            out[str(r.symbol).zfill(6)] = str(getattr(r, "name", "") or "").strip()
    except Exception:
        pass
    _CACHE = out
    return out


def name_of(symbol: str) -> str:
    return load_names().get(str(symbol).zfill(6), "")
