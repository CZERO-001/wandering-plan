# -*- coding: utf-8 -*-
"""QL2 卖出日 -9% 止损规则（v1.1）。"""
from __future__ import annotations

from . import config


def stop_loss_exit(buy_price, open_px, low_px, prev_close, limit_rate, close_px):
    """返回 (卖出价, 退出原因)。

    规则：卖出日盘中最低价不高于 买入价×(1-9%) 时止损卖出；
    成交价 = min(当日开盘价, 0.91×买入价)；
    若成交价已到跌停（无法卖出），回退收盘价并按 TIME 处理。
    """
    try:
        buy = float(buy_price)
        close = float(close_px)
    except (TypeError, ValueError):
        return close_px, "TIME"
    if buy <= 0:
        return close_px, "TIME"
    if open_px is None or low_px is None:
        return close_px, "TIME"
    try:
        op = float(open_px)
        low = float(low_px)
    except (TypeError, ValueError):
        return close_px, "TIME"
    threshold = buy * (1.0 - config.QL2_STOP)
    if low > threshold:
        return close_px, "TIME"
    fill = min(op, threshold)
    try:
        if prev_close is not None and limit_rate is not None:
            limit_down = round(float(prev_close) * (1.0 - float(limit_rate)), 2)
            if fill <= limit_down + config.LIMIT_TOL:
                return close_px, "TIME"
    except (TypeError, ValueError):
        pass
    return fill, "STOP"


def limit_rate_of(symbol: str) -> float:
    s = str(symbol).zfill(6)
    if s.startswith(("300", "301")):
        return 0.20
    return 0.10
