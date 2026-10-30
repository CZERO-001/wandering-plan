# -*- coding: utf-8 -*-
"""QL2 修复回放：修正 N05/市值/科创板股票池后，对比修复前后 10 月信号。"""
from __future__ import annotations

import json
import glob
import os
import urllib.request
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

ROOT = Path(r"D:\AStockWorker")
PIT = ROOT / "data/processed/dataset_h20_20y_pit_with_st_latest.parquet"
DAILY = Path(r"D:\CodexData\CodexSupervisor\work\oct_daily\daily_factors_oct.parquet")
OCT = Path(r"D:\CodexData\CodexSupervisor\work\oct_factors")
CHAMP = Path(r"D:\CodexData\CodexSupervisor\work")
PANEL = Path(r"D:\CodexData\CodexSupervisor\work\wave\roll_t1\data\factor_panel_raw_2022_2026.parquet")
INDEX_CSV = ROOT / "data/index/sh000300.csv"
TH = dict(t_count=22991.0, O3=0.6538615822792053, C2=0.6181763410568237,
          C4=0.6434561610221863, N05=0.05257522314786911)
BOARDS = ("000", "001", "002", "003", "300", "301", "600", "601", "603", "605", "688", "689")


def load_aux() -> pd.DataFrame:
    con = duckdb.connect()
    df = con.execute(
        """SELECT CAST(date AS DATE) AS d, symbol, raw_open, raw_high, raw_low, raw_close
           FROM read_parquet(?)
           WHERE CAST(date AS DATE) BETWEEN DATE '2026-08-20' AND DATE '2026-10-29'""",
        [str(PIT)],
    ).df()
    df["symbol"] = df.symbol.astype(str).str.zfill(6)
    df = df.sort_values(["symbol", "d"])
    g = df.groupby("symbol", sort=False)
    df["prev_close"] = g["raw_close"].shift(1)
    df["amp"] = (df.raw_high - df.raw_low) / df.prev_close.replace(0, np.nan)
    df["w_amp_first10"] = df.groupby("symbol", sort=False)["amp"].transform(
        lambda s: s.shift(5).rolling(5).mean()
    )
    # 历史面板里的市值/收盘价反推总股本；用最近可得值作为静态股本代理
    p = con.execute(
        """SELECT symbol, raw_close, market_cap_proxy_b
           FROM read_parquet(?)
           WHERE day = '20260930'""",
        [str(PANEL)],
    ).df()
    p["symbol"] = p.symbol.astype(str).str.zfill(6)
    p["shares"] = p.market_cap_proxy_b / p.raw_close.replace(0, np.nan)
    shares = p.groupby("symbol")["shares"].median()
    df["shares_proxy"] = df.symbol.map(shares)
    df["mcap_proxy"] = df.raw_close * df.shares_proxy
    return df


def comp(df: pd.DataFrame, parts: list[tuple[str, int]]) -> np.ndarray:
    vals = []
    for col, sign in parts:
        x = pd.to_numeric(df[col], errors="coerce")
        r = x.groupby(df.day).rank(pct=True, method="average")
        if sign < 0:
            r = 1 - r
        vals.append(r)
    return pd.concat(vals, axis=1).mean(axis=1, skipna=True).to_numpy()


def build_fixed(aux: pd.DataFrame) -> dict[str, list[str]]:
    daily = pd.read_parquet(DAILY)
    daily["day"] = daily.date.astype(str)
    daily["symbol"] = daily.symbol.astype(str).str.zfill(6)
    out = {}
    for day in sorted(daily.day.unique()):
        if not day.startswith("202610"):
            continue
        l2f = OCT / f"{day}.parquet"
        if not l2f.exists():
            continue
        l2 = pd.read_parquet(l2f)
        l2["symbol"] = l2.ticker.astype(str).str.zfill(6)
        d = daily[daily.day == day].copy()
        d = d[d.symbol.str.startswith(BOARDS)]
        d["range_compression_20_60_b"] = d.range_20_b / d.range_60_b.replace(0, np.nan)
        a = aux[aux.d == pd.Timestamp(day)]
        if a.empty:
            out[day] = []
            continue
        d = d.merge(a[["symbol", "raw_close", "w_amp_first10", "mcap_proxy"]], on="symbol", how="left")
        m = d.merge(l2[["symbol", "t_count", "m_volatility", "m_max_runup", "intraday_return", "amp_first10"]],
                    on="symbol", how="inner")
        if len(m) < 10:
            out[day] = []
            continue
        m["market_cap_proxy_b"] = m.mcap_proxy
        m["O3"] = comp(m, [("ret_1", -1), ("ret_3", -1), ("range_20_b", 1), ("market_cap_proxy_b", -1)])
        m["C2"] = comp(m, [("intraday_return", -1), ("m_volatility", 1), ("ret_5", -1),
                           ("market_cap_proxy_b", -1), ("range_compression_20_60_b", 1)])
        m["C4"] = comp(m, [("intraday_return", -1), ("atr_pct_14", 1), ("m_max_runup", 1)])
        m["N05"] = m.w_amp_first10
        hit = ((m.t_count >= TH["t_count"]) & (m.O3 >= TH["O3"]) & (m.C2 >= TH["C2"])
               & (m.C4 >= TH["C4"]) & (m.N05 >= TH["N05"]))
        m["candidate_score"] = (m.O3 + m.C2 + m.C4
                                + m.t_count.rank(pct=True) + m.N05.rank(pct=True)) / 5.0
        sel = m[hit].sort_values("candidate_score", ascending=False).head(20)
        out[day] = sel.symbol.tolist()
    return out


def load_pre() -> dict[str, list[str]]:
    out = {}
    for f in glob.glob(str(CHAMP / "champion_202610*.csv")):
        d = pd.read_csv(f, encoding="utf-8-sig")
        out[os.path.basename(f).split("_")[1].split(".")[0]] = d.symbol.astype(str).str.zfill(6).tolist()
    return out


def load_header() -> tuple[pd.DataFrame, pd.DataFrame]:
    # 用新浪拉一段沪深300日线，保证 10-23 之后不是陈旧数据
    try:
        url = ("https://money.finance.sina.com.cn/quotes_service/api/json_v2.php/"
               "CN_MarketData.getKLineData?symbol=sh000300&scale=240&ma=no&datalen=90")
        raw = urllib.request.urlopen(urllib.request.Request(
            url, headers={"User-Agent": "Mozilla/5.0", "Referer": "https://finance.sina.com.cn"}),
            timeout=20).read().decode("gbk", "replace")
        idx = pd.DataFrame(json.loads(raw))
        idx["d"] = pd.to_datetime(idx.day)
        idx["close"] = pd.to_numeric(idx.close)
        idx = idx.set_index("d").sort_index()
    except Exception:
        idx = pd.read_csv(INDEX_CSV)
        idx["d"] = pd.to_datetime(idx.date); idx["close"] = pd.to_numeric(idx.close)
        idx = idx.set_index("d").sort_index()
    return idx


def simulate(sets: dict[str, list[str]], idx: pd.DataFrame) -> pd.DataFrame:
    import sys
    sys.path.insert(0, str(ROOT / "wandering_plan"))
    from src import prices
    rows = []
    for day, syms in sets.items():
        sd = pd.Timestamp(day)
        # 简化：信号日 T，T+2 开盘买，T+3 收盘卖；按交易日历取
        # 用价格数据自身最近的后续交易日近似（信号日都是交易日）
        for sym in syms:
            # 取信号日后第 2/3 个交易日
            bd = None; xd = None
            try:
                import sys as _s
                _s.path.insert(0, str(ROOT / "wandering_plan"))
                from src import calendar_utils
                cal = calendar_utils.trade_calendar()
                future = [d for d in cal if d > sd]
                if len(future) >= 3:
                    bd, xd = future[1], future[2]
            except Exception:
                pass
            if bd is None or xd is None:
                continue
            bb = prices.bar_on(sym, bd); sb = prices.bar_on(sym, xd)
            if not bb or not sb or not bb.get("open"):
                continue
            entry = float(bb["open"]); stop = entry * 0.91
            if float(sb.get("low", 1e9)) <= stop:
                fill = min(float(sb["open"]), stop); ret = (fill / entry - 1) * 100
            else:
                ret = (float(sb["close"]) / entry - 1) * 100
            try:
                ir = (idx.loc[:xd].iloc[-1].close / idx.loc[:bd].iloc[-1].close - 1) * 100
            except Exception:
                ir = np.nan
            rows.append({"day": day, "symbol": sym, "ret": ret, "index": ir, "excess": ret - ir})
    return pd.DataFrame(rows)


def main():
    aux = load_aux()
    fixed = build_fixed(aux)
    pre = load_pre()
    days = sorted(set(pre) | set(fixed))
    print("date pre_n fixed_n overlap jaccard")
    all_pre, all_fix = set(), set()
    for d in days:
        a, b = set(pre.get(d, [])), set(fixed.get(d, []))
        all_pre |= {(d, x) for x in a}; all_fix |= {(d, x) for x in b}
        print(d, len(a), len(b), len(a & b), round(len(a & b) / max(1, len(a | b)), 3))
    print("overall pre", len(all_pre), "fixed", len(all_fix), "overlap", len(all_pre & all_fix),
          "jaccard", round(len(all_pre & all_fix) / max(1, len(all_pre | all_fix)), 3))
    idx = load_header()
    rp = simulate(pre, idx).dropna(subset=["excess"])
    rf = simulate(fixed, idx).dropna(subset=["excess"])
    for name, r in (("pre", rp), ("fixed", rf)):
        print(name, "signals", len(r), "avg_ret", round(r.ret.mean(), 2), "avg_index", round(r["index"].mean(), 2),
              "avg_excess", round(r.excess.mean(), 2), "win", int((r.ret > 0).sum()),
              "beat", int((r.excess > 0).sum()))
    # per-date avg
    print("\nper-date avg ret:")
    for d in days:
        a=rp[rp.day==d].ret.mean() if (rp.day==d).any() else np.nan
        b=rf[rf.day==d].ret.mean() if (rf.day==d).any() else np.nan
        print(d, round(a,2) if pd.notna(a) else None, round(b,2) if pd.notna(b) else None)


if __name__ == "__main__":
    main()
