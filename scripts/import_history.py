"""One-off: build history.json for the site page.

v1.0: 610 verified backtest trades, unchanged.
v1.1: add QL2 sell-day -9% stop-loss (--ql2-stop 0.09), re-simulate account.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import duckdb
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src import calendar_utils, config, names, ql2_exit  # noqa: E402

SRC = Path(r"D:\GL\wave_patterns\out\report\verify265\executable_trades.csv")
PIT = config.PIT_DATASET
OUT = config.HISTORY_JSON


def board_of(symbol: str) -> str:
    s = str(symbol).zfill(6)
    if s.startswith(("300", "301")):
        return "创业板"
    if s.startswith(("600", "601", "603", "605")):
        return "主板"
    if s.startswith(("000", "001", "002", "003")):
        return "主板"
    return "其他"


def signal_date_of(buy: pd.Timestamp, delay: int, cal) -> pd.Timestamp:
    return calendar_utils.shift(cal, buy, -delay) or buy


def _year_mdd(equity: pd.DataFrame, year: int, start_eq: float) -> float:
    vals = [float(start_eq)] + [float(v) for v in equity[equity["year"] == year]["equity"]]
    s = pd.Series(vals)
    return float((s / s.cummax() - 1.0).min())


def _apply_ql2_stop(df: pd.DataFrame, stop: float) -> tuple[dict, list[dict]]:
    """返回 idx -> (sell_px, ret, sell_time) 与触发明细。"""
    con = duckdb.connect()
    out: dict = {}
    triggers = []
    try:
        for idx, r in df[df["stream"] == "QL2"].iterrows():
            rows = con.execute(
                f"""SELECT CAST(date AS DATE) d, open, high, low, close, limit_rate
                    FROM read_parquet('{str(PIT).replace(chr(92), '/')}')
                    WHERE symbol = ? AND CAST(date AS DATE) <= CAST(? AS DATE)
                    ORDER BY date DESC LIMIT 2""",
                [r.symbol, str(r.exit_date.date())],
            ).fetchdf()
            if len(rows) < 2:
                continue
            rows = rows.iloc[::-1].reset_index(drop=True)
            prev_close = float(rows["close"].iloc[0])
            op = float(rows["open"].iloc[1])
            low = float(rows["low"].iloc[1])
            close = float(rows["close"].iloc[1])
            limit_rate = float(rows["limit_rate"].iloc[1])
            fill, reason = ql2_exit.stop_loss_exit(r.buy_px, op, low, prev_close, limit_rate, close)
            if reason == "STOP":
                sell_time = "09:30" if abs(float(fill) - op) <= 1e-9 else "盘中"
                out[idx] = (round(float(fill), 4), float(fill) / float(r.buy_px) - 1.0 - config.COST, sell_time)
                triggers.append({"symbol": r.symbol, "buy_date": str(r.entry_date.date()),
                                 "sell_date": str(r.exit_date.date()), "fill": round(float(fill), 4),
                                 "open": op, "low": low})
    finally:
        con.close()
    return out, triggers


def _resimulate(df: pd.DataFrame) -> dict:
    """按 2 仓 x 50% 重放，返回 idx -> (size, equity_before, pnl)。"""
    order = df.sort_values(["entry_date", "exit_date", "symbol"]).index.tolist()
    entries: dict = {}
    dates = set()
    for idx in order:
        r = df.loc[idx]
        entries.setdefault(pd.Timestamp(r.entry_date), []).append(idx)
        dates.add(pd.Timestamp(r.entry_date))
        dates.add(pd.Timestamp(r.exit_date))
    cash = config.INITIAL_CAPITAL
    pos = []  # [size, ret, exit_date]
    result = {}
    for d in sorted(dates):
        if pos:
            keep = []
            for size, ret, ed in pos:
                if ed <= d:
                    cash += size * (1.0 + ret)
                else:
                    keep.append((size, ret, ed))
            pos = keep
        for idx in entries.get(d, []):
            r = df.loc[idx]
            equity = cash + sum(s for s, _, _ in pos)
            size = min(config.SLOT_WEIGHT * equity, cash)
            if size <= 1e-9:
                continue
            cash -= size
            pos.append((size, float(r.ret2), pd.Timestamp(r.exit_date)))
            result[idx] = {"size": size, "equity_before": equity, "pnl": size * float(r.ret2)}
    return result


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ql2-stop", type=float, default=None, help="如 0.09；启用 QL2 卖出日止损")
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()

    cal = calendar_utils.trade_calendar()
    df = pd.read_csv(SRC, dtype={"symbol": str})
    df["symbol"] = df["symbol"].astype(str).str.zfill(6)
    df["entry_date"] = pd.to_datetime(df["entry_date"])
    df["exit_date"] = pd.to_datetime(df["exit_date"])
    df["ret2"] = df["ret"].astype(float)
    name_map = names.load_names()

    stop = a.ql2_stop
    triggers = []
    df["exit_reason2"] = "TIME"
    df["sell_time2"] = "15:00"
    if stop:
        overrides, triggers = _apply_ql2_stop(df, stop)
        for idx, (sell_px, ret, sell_time) in overrides.items():
            df.at[idx, "sell_px"] = sell_px
            df.at[idx, "ret2"] = ret
            df.at[idx, "exit_reason2"] = "STOP"
            df.at[idx, "sell_time2"] = sell_time
        sim = _resimulate(df)
        print(f"QL2 stop triggers: {len(triggers)}")
        for t in triggers:
            print("  ", t["symbol"], t["buy_date"], "->", t["sell_date"], "@", t["fill"])
    else:
        sim = None

    # 账单顺序沿用原 exit_date 排序；v1.1 使用重放后的 size/pnl
    work = df.sort_values("exit_date").reset_index()
    work["idx0"] = work["index"]

    trades = []
    cum = 0.0
    for r in work.itertuples(index=False):
        delay = config.BUY_DELAY.get(r.stream, 3)
        sig = signal_date_of(r.entry_date, delay, cal)
        if sim is not None:
            s = sim[r.idx0]
            size, eq_before, pnl = s["size"], s["equity_before"], s["pnl"]
            reason = getattr(r, "exit_reason2", "TIME")
            sell_time = getattr(r, "sell_time2", "15:00")
        else:
            size, eq_before, pnl = float(r.size), float(r.equity_before), float(r.pnl)
            reason = "TIME" if int(getattr(r, "exit_delay", 0) or 0) == 0 else "DEFERRED"
            sell_time = "15:00"
        cum += pnl
        trades.append({
            "symbol": r.symbol,
            "name": name_map.get(r.symbol, ""),
            "board": board_of(r.symbol),
            "source": r.stream,
            "year": int(r.year),
            "signal_date": sig.strftime("%Y-%m-%d"),
            "buy_date": r.entry_date.strftime("%Y-%m-%d"),
            "sell_date": r.exit_date.strftime("%Y-%m-%d"),
            "buy_price": round(float(r.buy_px), 4),
            "sell_price": round(float(r.sell_px), 4),
            "return_pct": round(float(r.ret2) * 100, 3),
            "net_profit": round(float(pnl), 2),
            "position_amount": round(float(size), 2),
            "capital_before_buy": round(float(eq_before), 2),
            "position_pct": round(float(size) / float(eq_before) * 100, 2) if eq_before else None,
            "exit_reason": reason,
            "hit_count": 1,
            "weight": 50.0,
            "buy_time": "09:30",
            "sell_time": sell_time,
            "balance_after": round(100000.0 + cum, 2),
        })
    tr = pd.DataFrame(trades)

    # equity by exit date -> yearly + drawdown
    by_exit = tr.sort_values("sell_date")
    eq = pd.DataFrame({"date": pd.to_datetime(by_exit["sell_date"]),
                       "pnl": by_exit["net_profit"].to_numpy()}).groupby("date")["pnl"].sum().sort_index()
    equity = (100000.0 + eq.cumsum()).rename("equity").reset_index()
    equity["year"] = equity["date"].dt.year
    year_end = equity.groupby("year")["equity"].last()
    yearly = []
    for y in sorted(tr["year"].unique()):
        sub = tr[tr["year"] == y]
        start_eq = float(year_end.shift(1).get(y, 100000.0)) if y in year_end.index else 100000.0
        if pd.isna(start_eq):
            start_eq = 100000.0
        end_eq = float(year_end.get(y, start_eq))
        first_buy = pd.Timestamp(sub["buy_date"].min())
        last_sell = pd.Timestamp(sub["sell_date"].max())
        ystart = pd.Timestamp(f"{int(y)}-01-01")
        n_days = len([d for d in cal if ystart <= pd.Timestamp(d) <= last_sell])
        yr_ret = end_eq / start_eq - 1
        ann = (1.0 + yr_ret) ** (252.0 / max(n_days, 1)) - 1
        yearly.append({
            "year": int(y),
            "trading_days": int(n_days),
            "year_return": round(yr_ret, 6),
            "annualized_return": round(ann, 6),
            "max_drawdown": round(_year_mdd(equity, y, start_eq), 6),
            "first_buy": sub["buy_date"].min(),
            "last_sell": sub["sell_date"].max(),
            "trades": int(len(sub)),
            "win_rate": round(float((sub["return_pct"] > 0).mean()) * 100, 2),
            "avg_trade_return": round(float(sub["return_pct"].mean()), 3),
            "net_profit": round(float(sub["net_profit"].sum()), 2),
            "partial": int(y) == int(tr["year"].max()),
        })

    stocks = []
    for sym, sub in tr.groupby("symbol"):
        stocks.append({
            "symbol": sym,
            "name": sub["name"].iloc[0],
            "board": sub["board"].iloc[0],
            "trades": int(len(sub)),
            "win_rate": round(float((sub["return_pct"] > 0).mean()) * 100, 2),
            "avg_return": round(float(sub["return_pct"].mean()), 3),
            "net_profit": round(float(sub["net_profit"].sum()), 2),
            "best_return": round(float(sub["return_pct"].max()), 3),
            "worst_return": round(float(sub["return_pct"].min()), 3),
            "first_buy": sub["buy_date"].min(),
            "last_sell": sub["sell_date"].max(),
        })
    stocks.sort(key=lambda x: x["net_profit"], reverse=True)

    curve = [{"date": pd.Timestamp(d).strftime("%Y-%m-%d"),
              "equity": round(float(e), 2),
              "return_pct": round((float(e) / 100000.0 - 1) * 100, 2)}
             for d, e in zip(equity["date"], equity["equity"])]
    curve.insert(0, {"date": str(tr["buy_date"].min()), "equity": 100000.0, "return_pct": 0.0})

    final_eq = float(equity["equity"].iloc[-1])
    start = pd.Timestamp(tr["buy_date"].min())
    end = pd.Timestamp(tr["sell_date"].max())
    years = max((end - start).days / 365.25, 1e-9)
    cagr = (final_eq / 100000.0) ** (1 / years) - 1
    peak = equity["equity"].cummax()
    mdd = float(((equity["equity"] - peak) / peak).min())
    rets = tr["return_pct"] / 100.0
    sharpe = float(rets.mean() / rets.std() * (len(tr) / years) ** 0.5) if rets.std() else 0.0
    overall = {
        "annualized_return": round(cagr, 6),
        "max_drawdown": round(mdd, 6),
        "calmar": round(cagr / abs(mdd), 4) if mdd else None,
        "sharpe": round(sharpe, 4),
        "closed_trades": int(len(tr)),
        "total_return": round(final_eq / 100000.0 - 1, 6),
        "total_profit": round(final_eq - 100000.0, 2),
    }

    payload = {
        "meta": {
            "model": "流浪计划",
            "version": "1.1.0" if stop else "1.0.0",
            "window": f"{start.date()} ~ {end.date()}",
            "initial_cash": 100000.0,
            "capital_mode_label": "2 仓 × 50% 复利",
            "sources": {"B1": int((tr.source == "B1").sum()), "QL2": int((tr.source == "QL2").sum()),
                        "V12": int((tr.source == "V12").sum())},
            "notes": ("回测为已逐笔核验版本（复权价、开盘买/收盘卖、开盘涨停不买、收盘跌停顺延）；"
                      "v1.1 增加 QL2 卖出日 -9% 止损（成交价 min(开盘, 0.91×买入价)，跌停不卖）。" if stop else
                      "回测为已逐笔核验版本（复权价、开盘买/收盘卖、开盘涨停不买、收盘跌停顺延）。"),
        },
        "overall": overall,
        "yearly": yearly,
        "stocks": stocks,
        "trades": trades,
        "curve": curve,
    }
    print(f"stop={stop} triggers={len(triggers)} trades={len(tr)} final={final_eq:,.2f} "
          f"total_return={overall['total_return']:.4f} mdd={mdd:.4f}")
    if a.check:
        return
    outp = Path(a.out)
    outp.parent.mkdir(parents=True, exist_ok=True)
    outp.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    print("saved", outp)


if __name__ == "__main__":
    main()
