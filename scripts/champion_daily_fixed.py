# -*- coding: utf-8 -*-
"""现冠军每日选股（修复版）：N05 用 w_amp_first10，O3/C2 补市值，股票池含科创板。"""
import os, glob
import duckdb
import numpy as np
import pandas as pd

TH_O3 = 0.6538615822792053
TH_C2 = 0.6181763410568237
TH_C4 = 0.6434561610221863
TH_TC = 22991.0
TH_N05 = 0.05257522314786911
OCT = r"D:\CodexData\CodexSupervisor\work\oct_factors"
DAILY = r"D:\CodexData\CodexSupervisor\work\oct_daily\daily_factors_oct.parquet"
PIT = r"D:\AStockWorker\data\processed\dataset_h20_20y_pit_with_st_latest.parquet"
PANEL = r"D:\CodexData\CodexSupervisor\work\wave\roll_t1\data\factor_panel_raw_2022_2026.parquet"
OUT = os.environ.get("CHAMP_OUT", r"D:\CodexData\CodexSupervisor\work")
BOARDS = ("000", "001", "002", "003", "300", "301", "600", "601", "603", "605", "688", "689")


def load_aux():
    con = duckdb.connect()
    df = con.execute(
        """SELECT CAST(date AS DATE) AS d, symbol, raw_close, raw_high, raw_low
           FROM read_parquet(?)
           WHERE CAST(date AS DATE) >= DATE '2026-08-20'""",
        [PIT],
    ).df()
    df["symbol"] = df.symbol.astype(str).str.zfill(6)
    df = df.sort_values(["symbol", "d"])
    g = df.groupby("symbol", sort=False)
    df["prev_close"] = g["raw_close"].shift(1)
    df["amp"] = (df.raw_high - df.raw_low) / df.prev_close.replace(0, np.nan)
    df["w_amp_first10"] = g["amp"].transform(lambda s: s.shift(5).rolling(5).mean())
    try:
        p = con.execute(
            """SELECT symbol, raw_close, market_cap_proxy_b
               FROM read_parquet(?)
               WHERE day = '20260930'""",
            [PANEL],
        ).df()
        p["symbol"] = p.symbol.astype(str).str.zfill(6)
        p["shares"] = p.market_cap_proxy_b / p.raw_close.replace(0, np.nan)
        shares = p.groupby("symbol")["shares"].median()
        df["shares_proxy"] = df.symbol.map(shares)
        df["mcap_proxy"] = df.raw_close * df.shares_proxy
        if df["mcap_proxy"].isna().any():
            med = float(shares.median()) if len(shares) else np.nan
            df["mcap_proxy"] = df.mcap_proxy.fillna(df.raw_close * med)
    except Exception as exc:
        print("market cap fallback:", exc)
        df["mcap_proxy"] = np.nan
    con.close()
    return df


def comp(df, parts):
    vals = []
    for col, sign in parts:
        x = pd.to_numeric(df[col], errors="coerce")
        r = x.groupby(df.day).rank(pct=True, method="average")
        if sign < 0:
            r = 1 - r
        vals.append(r)
    return pd.concat(vals, axis=1).mean(axis=1, skipna=True).to_numpy()


d = pd.read_parquet(DAILY)
d["day"] = d.date.astype(str)
d["symbol"] = d.symbol.astype(str).str.zfill(6)
d["range_compression_20_60_b"] = d.range_20_b / d.range_60_b.replace(0, np.nan)
aux = load_aux()
aux = aux.rename(columns={"d": "aux_date"})
aux["day"] = aux.aux_date.dt.strftime("%Y%m%d")

rows = []
for date in sorted(d.day.unique()):
    outfile = os.path.join(OUT, f"champion_{date}.csv")
    if os.path.exists(outfile) and os.environ.get("CHAMP_FORCE") != "1":
        rows.append({"date": date, "cand": 0, "hits": 0, "topn": 0, "note": "exists"})
        continue
    l2f = os.path.join(OCT, date + ".parquet")
    if not os.path.exists(l2f):
        rows.append({"date": date, "cand": 0, "hits": 0, "topn": 0, "note": "no_l2"})
        continue
    l2 = pd.read_parquet(l2f)
    l2["symbol"] = l2.ticker.astype(str).str.zfill(6)
    m = d[d.day == date].copy()
    m = m[m.symbol.str.startswith(BOARDS)]
    m = m.merge(aux[aux.day == date][["symbol", "raw_close", "w_amp_first10", "mcap_proxy"]],
                on="symbol", how="left")
    m = m.merge(l2[["symbol", "t_count", "m_volatility", "m_max_runup", "intraday_return"]],
                on="symbol", how="inner")
    if len(m) < 10:
        rows.append({"date": date, "cand": len(m), "hits": 0, "topn": 0, "note": "small"})
        continue
    m["market_cap_proxy_b"] = m.mcap_proxy
    m["O3"] = comp(m, [("ret_1", -1), ("ret_3", -1), ("range_20_b", 1), ("market_cap_proxy_b", -1)])
    m["C2"] = comp(m, [("intraday_return", -1), ("m_volatility", 1), ("ret_5", -1),
                       ("market_cap_proxy_b", -1), ("range_compression_20_60_b", 1)])
    m["C4"] = comp(m, [("intraday_return", -1), ("atr_pct_14", 1), ("m_max_runup", 1)])
    m["N05"] = m.w_amp_first10
    m["t_count_score"] = m.t_count.rank(pct=True, method="average")
    m["N05_score"] = m.N05.rank(pct=True, method="average")
    m["candidate_score"] = (m.O3 + m.C2 + m.C4 + m.t_count_score + m.N05_score) / 5.0
    hit = ((m.t_count >= TH_TC) & (m.O3 >= TH_O3) & (m.C2 >= TH_C2)
           & (m.C4 >= TH_C4) & (m.N05 >= TH_N05))
    c = m[hit].sort_values("candidate_score", ascending=False).head(20)
    rows.append({"date": date, "cand": len(m), "hits": int(hit.sum()), "topn": len(c), "note": ""})
    if len(c):
        c[["day", "symbol", "O3", "C2", "C4", "t_count", "N05", "candidate_score"]].to_csv(
            outfile, index=False, encoding="utf-8-sig")
print(pd.DataFrame(rows).to_string(index=False))


