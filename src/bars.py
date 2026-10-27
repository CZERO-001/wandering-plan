# -*- coding: utf-8 -*-
"""从 PIT 数据集读取个股日线（原始价 + 涨跌停）。"""
from __future__ import annotations

from pathlib import Path

import duckdb
import pandas as pd

from . import config


def load_bars(symbol: str, start, end) -> pd.DataFrame:
    p = str(config.PIT_DATASET).replace("\\", "/")
    con = duckdb.connect()
    try:
        df = con.execute(
            f"""SELECT CAST(date AS DATE) AS date, symbol,
                       CAST(raw_open AS DOUBLE)  AS raw_open,
                       CAST(raw_close AS DOUBLE) AS raw_close,
                       CAST(limit_rate AS DOUBLE) AS limit_rate
                FROM read_parquet('{p}')
                WHERE symbol = ? AND CAST(date AS DATE) BETWEEN CAST(? AS DATE) AND CAST(? AS DATE)
                ORDER BY date""",
            [str(symbol).zfill(6), str(start), str(end)],
        ).fetchdf()
    finally:
        con.close()
    df["date"] = pd.to_datetime(df["date"])
    return df


def load_ohlc(symbols: list[str], start, end) -> pd.DataFrame:
    if not symbols:
        return pd.DataFrame(columns=["date", "symbol", "raw_open", "raw_close", "limit_rate"])
    p = str(config.PIT_DATASET).replace("\\", "/")
    con = duckdb.connect()
    try:
        df = con.execute(
            f"""SELECT CAST(date AS DATE) AS date, symbol,
                       CAST(raw_open AS DOUBLE)  AS raw_open,
                       CAST(raw_close AS DOUBLE) AS raw_close,
                       CAST(limit_rate AS DOUBLE) AS limit_rate
                FROM read_parquet('{p}')
                WHERE symbol IN ({",".join(["?"] * len(symbols))})
                  AND CAST(date AS DATE) BETWEEN CAST(? AS DATE) AND CAST(? AS DATE)
                ORDER BY date""",
            [str(s).zfill(6) for s in symbols] + [str(start), str(end)],
        ).fetchdf()
    finally:
        con.close()
    df["date"] = pd.to_datetime(df["date"])
    return df


def latest_dataset_date() -> pd.Timestamp | None:
    if not config.PIT_DATASET.exists():
        return None
    p = str(config.PIT_DATASET).replace("\\", "/")
    con = duckdb.connect()
    try:
        v = con.execute(f"SELECT MAX(CAST(date AS DATE)) FROM read_parquet('{p}')").fetchone()[0]
        return pd.Timestamp(v) if v is not None else None
    finally:
        con.close()
