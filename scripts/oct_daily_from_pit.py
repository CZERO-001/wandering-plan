"""Append missing trading days to oct_daily/daily_factors_oct.parquet using the PIT daily dataset.

Why: TDX local daily data may miss a session (e.g. 2026-10-26), while PIT (built from sina/tencent unadjusted)
is authoritative for the single-name daily bars. This script recomputes the same columns that
tdx_daily_factors.py produces for the missing dates and appends them.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

PIT = Path(r"D:\AStockWorker\data\processed\dataset_h20_20y_pit_with_st_latest.parquet")
OCT_DAILY = Path(r"D:\CodexData\CodexSupervisor\work\oct_daily\daily_factors_oct.parquet")
CAL = Path(r"D:\GL\wave_patterns\data\calendar.parquet")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dates", required=True, help="comma separated YYYYMMDD")
    ap.add_argument("--lookback", type=int, default=90)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--out", default=str(OCT_DAILY))
    a = ap.parse_args()
    targets = [d.strip() for d in a.dates.split(",") if d.strip()]

    existing = pd.read_parquet(OCT_DAILY)
    existing["date"] = existing["date"].astype(str)
    max_date = existing["date"].max()

    cal = pd.read_parquet(CAL)["date"]
    cal = pd.to_datetime(cal).sort_values().tolist()
    tgt_idx = [i for i, d in enumerate(cal) if d.strftime("%Y%m%d") in targets]
    if not tgt_idx:
        print("target dates not in calendar:", targets)
        return
    start = cal[max(0, min(tgt_idx) - a.lookback)].strftime("%Y-%m-%d")
    end = cal[max(tgt_idx)].strftime("%Y-%m-%d")

    p = str(PIT).replace("\\", "/")
    con = duckdb.connect()
    df = con.execute(
        f"""SELECT CAST(date AS DATE) AS date, symbol,
                   CAST(raw_open AS DOUBLE) o, CAST(raw_high AS DOUBLE) h,
                   CAST(raw_low AS DOUBLE) l, CAST(raw_close AS DOUBLE) c
            FROM read_parquet('{p}')
            WHERE CAST(date AS DATE) BETWEEN DATE '{start}' AND DATE '{end}'
              AND regexp_matches(symbol, '^[0-9]{{6}}$')
            ORDER BY symbol, date"""
    ).fetchdf()
    con.close()
    df["date"] = pd.to_datetime(df["date"])
    rows = []
    for sym, g in df.groupby("symbol", sort=False):
        if len(g) < 61:
            continue
        g = g.sort_values("date")
        c, h, l, o = g["c"].to_numpy(), g["h"].to_numpy(), g["l"].to_numpy(), g["o"].to_numpy()
        dates = g["date"].to_numpy()
        prev_c = np.concatenate([[np.nan], c[:-1]])
        r1 = c / prev_c - 1
        r3 = np.concatenate([[np.nan] * 3, c[3:] / c[:-3] - 1])
        r5 = np.concatenate([[np.nan] * 5, c[5:] / c[:-5] - 1])
        tr = np.maximum(h - np.maximum(l, prev_c), np.maximum(h, prev_c) - l)
        atr14 = pd.Series(tr).rolling(14).mean().to_numpy() / c
        s = pd.Series(h)
        range20 = (s.rolling(20).max().to_numpy() - pd.Series(l).rolling(20).min().to_numpy()) / pd.Series(l).rolling(20).min().to_numpy()
        s60h = pd.Series(h).rolling(60).max().to_numpy()
        s60l = pd.Series(l).rolling(60).min().to_numpy()
        range60 = (s60h - s60l) / s60l
        for i, d in enumerate(dates):
            ds = pd.Timestamp(d).strftime("%Y%m%d")
            if ds not in targets:
                continue
            rows.append({
                "symbol": sym, "date": ds,
                "ret_1": r1[i], "ret_3": r3[i], "ret_5": r5[i],
                "range_20_b": range20[i], "range_60_b": range60[i], "atr_pct_14": atr14[i],
                "close_px": c[i], "open_px": o[i], "high_px": h[i], "low_px": l[i],
            })
    new = pd.DataFrame(rows)
    print("new rows", len(new), "dates", sorted(new["date"].unique().tolist()) if len(new) else [])
    if a.dry_run or new.empty:
        return
    out = pd.concat([existing, new], ignore_index=True)
    out = out.drop_duplicates(["symbol", "date"], keep="last").sort_values(["date", "symbol"])
    outp = Path(a.out)
    outp.parent.mkdir(parents=True, exist_ok=True)
    out.to_parquet(outp, index=False)
    print("saved", outp, "rows", len(out), "max date", out["date"].max())


if __name__ == "__main__":
    main()
