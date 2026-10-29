# -*- coding: utf-8 -*-
"""用 PIT 日线补 QL2 oct_daily 因子（不依赖通达信客户端）。"""
from __future__ import annotations

import argparse
from pathlib import Path

import duckdb
import pandas as pd

PIT = r"D:/AStockWorker/data/processed/dataset_h20_20y_pit_with_st_latest.parquet"
OCT = Path(r"D:/CodexData/CodexSupervisor/work/oct_factors")
DAILY = Path(r"D:/CodexData/CodexSupervisor/work/oct_daily/daily_factors_oct.parquet")


def one_date(con: duckdb.DuckDBPyConnection, date: str) -> int:
    ref = OCT / f"{date}.parquet"
    if not ref.exists():
        print(date, "skip: oct_factors missing")
        return 0
    syms = sorted(pd.read_parquet(ref)["ticker"].astype(str).str.zfill(6).unique().tolist())
    target = pd.Timestamp(f"{date[:4]}-{date[4:6]}-{date[6:8]}")
    df = con.execute(
        """SELECT symbol, date, high, low, raw_open, raw_high, raw_low, raw_close,
                  ret_1, ret_3, ret_5, atr_pct_14
           FROM read_parquet(?)
           WHERE CAST(date AS DATE) BETWEEN DATE '2026-06-01' AND CAST(? AS DATE)
             AND symbol IN (SELECT * FROM UNNEST(?))""",
        [PIT, target.strftime("%Y-%m-%d"), syms],
    ).df()
    if df.empty:
        print(date, "skip: no PIT rows")
        return 0
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values(["symbol", "date"])
    g = df.groupby("symbol", sort=False)
    for n in (20, 60):
        df[f"_hi{n}"] = g["high"].transform(lambda s: s.rolling(n).max())
        df[f"_lo{n}"] = g["low"].transform(lambda s: s.rolling(n).min())
    last = df[df["date"] == target].copy()
    out = pd.DataFrame({
        "symbol": last["symbol"].astype(str).str.zfill(6),
        "date": last["date"].dt.strftime("%Y%m%d"),
        "ret_1": last["ret_1"], "ret_3": last["ret_3"], "ret_5": last["ret_5"],
        "range_20_b": (last["_hi20"] - last["_lo20"]) / last["_lo20"],
        "range_60_b": (last["_hi60"] - last["_lo60"]) / last["_lo60"],
        "atr_pct_14": last["atr_pct_14"],
        "close_px": last["raw_close"], "open_px": last["raw_open"],
        "high_px": last["raw_high"], "low_px": last["raw_low"],
    })
    old = pd.read_parquet(DAILY) if DAILY.exists() else pd.DataFrame(columns=out.columns)
    old = old[old["date"].astype(str) != date]
    pd.concat([old, out], ignore_index=True).to_parquet(DAILY, index=False)
    print(date, "appended", len(out), "rows; total", len(old) + len(out))
    return len(out)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dates", required=True, help="YYYYMMDD, comma separated")
    a = ap.parse_args()
    con = duckdb.connect()
    for d in [x.strip() for x in a.dates.split(",") if x.strip()]:
        one_date(con, d)


if __name__ == "__main__":
    main()
