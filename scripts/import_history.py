"""One-off: build history.json (610 verified backtest trades) for the site page."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src import calendar_utils, config, names  # noqa: E402

SRC = Path(r"D:\GL\wave_patterns\out\report\verify265\executable_trades.csv")
OUT = config.ROOT / "data" / "wandering_plan" / "history.json"


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


def main() -> None:
    cal = calendar_utils.trade_calendar()
    df = pd.read_csv(SRC, dtype={"symbol": str})
    df["symbol"] = df["symbol"].astype(str).str.zfill(6)
    df["entry_date"] = pd.to_datetime(df["entry_date"])
    df["exit_date"] = pd.to_datetime(df["exit_date"])
    name_map = names.load_names()

    trades = []
    cum = 0.0
    for r in df.sort_values("exit_date").itertuples(index=False):
        cum += float(r.pnl)
        delay = config.BUY_DELAY.get(r.stream, 3)
        sig = signal_date_of(r.entry_date, delay, cal)
        ret = float(r.ret)
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
            "return_pct": round(ret * 100, 3),
            "net_profit": round(float(r.pnl), 2),
            "position_amount": round(float(r.size), 2),
            "capital_before_buy": round(float(r.equity_before), 2),
            "position_pct": round(float(r.size) / float(r.equity_before) * 100, 2) if r.equity_before else None,
            "exit_reason": "TIME" if int(getattr(r, "exit_delay", 0) or 0) == 0 else "DEFERRED",
            "hit_count": 1,
            "weight": 50.0,
            "buy_time": "09:30",
            "sell_time": "15:00",
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
    prev = year_end.shift(1).fillna(100000.0)
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
            "max_drawdown": round(float(((equity[equity.year == y]["equity"].cummax() - equity[equity.year == y]["equity"]) / equity[equity.year == y]["equity"].cummax()).min()), 6) if (equity.year == y).sum() > 1 else 0.0,
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
            "version": "1.0.0",
            "window": f"{start.date()} ~ {end.date()}",
            "initial_cash": 100000.0,
            "capital_mode_label": "2 仓 × 50% 复利",
            "sources": {"B1": int((tr.source == "B1").sum()), "QL2": int((tr.source == "QL2").sum()),
                        "V12": int((tr.source == "V12").sum())},
            "notes": "回测为已逐笔核验版本（复权价、开盘买/收盘卖、开盘涨停不买、收盘跌停顺延）。",
        },
        "overall": overall,
        "yearly": yearly,
        "stocks": stocks,
        "trades": trades,
        "curve": curve,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    print("saved", OUT, "trades", len(trades), "stocks", len(stocks), "years", len(yearly))
    print("overall:", json.dumps(overall, ensure_ascii=False))


if __name__ == "__main__":
    main()
