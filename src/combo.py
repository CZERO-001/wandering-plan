# -*- coding: utf-8 -*-
"""三路信号组合排程：2 槽、每槽 50%、优先级 B1 > QL2 > V12。"""
from __future__ import annotations

from datetime import datetime

import pandas as pd

from . import bars, calendar_utils, config, names


def _dedupe(signals: list[dict]) -> list[dict]:
    best: dict[tuple, dict] = {}
    for s in signals:
        if not s.get("symbol") or s.get("buy_date") is None:
            continue
        key = (s["symbol"], pd.Timestamp(s["buy_date"]).date())
        cur = best.get(key)
        if cur is None:
            best[key] = s
            continue
        # 同票同日多来源时保留优先级高的
        if config.PRIORITY.index(s["source"]) < config.PRIORITY.index(cur["source"]):
            best[key] = s
    return list(best.values())


def _recent_with_returns(signals: list[dict], data_date, n: int = 5) -> list[dict]:
    done = [s for s in signals if s.get("sell_date") is not None and pd.Timestamp(s["sell_date"]) <= pd.Timestamp(data_date)]
    done.sort(key=lambda s: pd.Timestamp(s["sell_date"]), reverse=True)
    done = done[:n]
    if not done:
        return []
    syms = sorted({s["symbol"] for s in done})
    px = bars.load_ohlc(syms, min(pd.Timestamp(s["buy_date"]) for s in done).date(),
                        pd.Timestamp(data_date).date())
    out = []
    for s in done:
        try:
            b = float(px[(px.symbol == s["symbol"]) & (px.date == pd.Timestamp(s["buy_date"]))]["raw_open"].iloc[0])
            c = float(px[(px.symbol == s["symbol"]) & (px.date == pd.Timestamp(s["sell_date"]))]["raw_close"].iloc[0])
            ret = c / b - 1 - config.COST
        except Exception:
            ret = float("nan")
        out.append({**s, "return_pct": round(ret * 100, 2) if pd.notna(ret) else None})
    return out


def build_plan(signals: list[dict], cal: list[pd.Timestamp], data_date, capital: float = config.INITIAL_CAPITAL) -> dict:
    """生成页面用计划。data_date = 数据最后一天（信号日）。"""
    data_date = pd.Timestamp(data_date)
    next_day = calendar_utils.next_trading_day(cal, data_date)
    sig = _dedupe(signals)

    buys = [s for s in sig if next_day is not None and pd.Timestamp(s["buy_date"]) == next_day]
    buys.sort(key=lambda s: config.PRIORITY.index(s["source"]))
    # 单路上限 + 总槽数
    per: dict[str, int] = {}
    chosen: list[dict] = []
    for s in buys:
        src = s["source"]
        if per.get(src, 0) >= config.MAX_PER_STREAM.get(src, 1):
            continue
        if len(chosen) >= config.SLOTS:
            break
        per[src] = per.get(src, 0) + 1
        chosen.append(s)

    for s in chosen:
        s["position_amount"] = round(capital * config.SLOT_WEIGHT)

    # 下一交易日到期卖出
    sells = [s for s in sig if s.get("sell_date") is not None and pd.Timestamp(s["sell_date"]) == next_day]
    sells.sort(key=lambda s: config.PRIORITY.index(s["source"]))

    for s in chosen + sells:
        if not s.get("name"):
            s["name"] = names.name_of(s["symbol"])

    status = "buy" if chosen else "no_signal"
    return {
        "status": status,
        "data_date": data_date.strftime("%Y-%m-%d"),
        "next_day": next_day.strftime("%Y-%m-%d") if next_day is not None else None,
        "updated_at": datetime.now().isoformat(timespec="seconds"),
        "capital": capital,
        "buys": chosen,
        "sells": sells,
        "recent": _recent_with_returns(sig, data_date, 5),
        "counts": {
            "B1": sum(1 for s in sig if s["source"] == "B1"),
            "QL2": sum(1 for s in sig if s["source"] == "QL2"),
            "V12": sum(1 for s in sig if s["source"] == "V12"),
        },
    }
