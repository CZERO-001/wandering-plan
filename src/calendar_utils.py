# -*- coding: utf-8 -*-
"""交易日历与日期偏移。"""
from __future__ import annotations

import sys
from datetime import timedelta

import pandas as pd

from . import config


def trade_calendar() -> list[pd.Timestamp]:
    """优先用项目的 A 股日历；失败则退化为工作日。"""
    try:
        sys.path.insert(0, str(config.SELECTOR_ROOT))
        from selector.calendar import get_trade_calendar  # type: ignore
        cal = get_trade_calendar()
        return [pd.Timestamp(d) for d in cal]
    except Exception:
        today = pd.Timestamp.today().normalize()
        start = today - pd.Timedelta(days=400)
        return [d for d in pd.bdate_range(start, today + pd.Timedelta(days=400))]


def shift(cal: list[pd.Timestamp], date, k: int, allow_future: bool = True):
    """把 date 后移 k 个交易日；越界返回 None（allow_future=True 时先外推）。"""
    d = pd.Timestamp(date)
    dates = cal
    if allow_future and dates and d > dates[-1]:
        dates = dates + [x for x in pd.bdate_range(dates[-1] + pd.Timedelta(days=1), d + pd.Timedelta(days=120))]
    idx = {x: i for i, x in enumerate(dates)}
    if d not in idx:
        later = [x for x in dates if x >= d]
        if not later:
            return None
        d = later[0]
    j = idx[d] + k
    return dates[j] if 0 <= j < len(dates) else None


def next_trading_day(cal: list[pd.Timestamp], date) -> pd.Timestamp | None:
    d = pd.Timestamp(date)
    later = [x for x in cal if x > d]
    return later[0] if later else None


def last_trading_day(cal: list[pd.Timestamp], today=None) -> pd.Timestamp | None:
    t = pd.Timestamp(today or pd.Timestamp.today().normalize())
    past = [x for x in cal if x <= t]
    return past[-1] if past else None


def trading_days_between(cal: list[pd.Timestamp], a, b) -> int:
    a, b = pd.Timestamp(a), pd.Timestamp(b)
    return sum(1 for x in cal if a < x <= b)
