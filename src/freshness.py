# -*- coding: utf-8 -*-
"""数据新鲜度检查与缺数据自动补。"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

import pandas as pd

from . import b1_signal, bars, calendar_utils, config, ql2_signal, v12_signal

PY = str(config.PY)
LOG_DIR = config.LOG_DIR


def _run(cmd: list[str], timeout: int, log_name: str) -> tuple[int, str]:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log = LOG_DIR / f"{log_name}.log"
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                           encoding="utf-8", errors="replace")
        with log.open("a", encoding="utf-8") as f:
            f.write(f"\n[{time.strftime('%Y-%m-%d %H:%M:%S')}] {' '.join(cmd)}\n")
            f.write((p.stdout or "")[-4000:] + "\n" + (p.stderr or "")[-2000:] + f"\nrc={p.returncode}\n")
        return p.returncode, (p.stdout or "")[-500:]
    except Exception as exc:
        with log.open("a", encoding="utf-8") as f:
            f.write(f"\n[{time.strftime('%Y-%m-%d %H:%M:%S')}] {' '.join(cmd)} EXC {exc}\n")
        return 1, str(exc)


def status(cal: list[pd.Timestamp] | None = None) -> dict:
    cal = cal or calendar_utils.trade_calendar()
    expected = calendar_utils.last_trading_day(cal)
    pit = bars.latest_dataset_date()
    ql2 = ql2_signal.latest_signal_date()
    v11 = v12_signal.latest_signal_date()
    b1 = b1_signal.latest_signal_date()

    def stale(d):
        return expected is not None and (d is None or pd.Timestamp(d) < pd.Timestamp(expected))

    items = {
        "expected": expected.strftime("%Y-%m-%d") if expected is not None else None,
        "pit": pit.strftime("%Y-%m-%d") if pit is not None else None,
        "b1": b1.strftime("%Y-%m-%d") if b1 is not None else None,
        "ql2": ql2.strftime("%Y-%m-%d") if ql2 is not None else None,
        "v11": v11.strftime("%Y-%m-%d") if v11 is not None else None,
    }
    items["stale"] = [k for k, d in (("pit", pit), ("b1", b1), ("ql2", ql2), ("v11", v11)) if stale(d)]
    items["ok"] = not items["stale"]
    return items


def _missing_oct_dates(expected: str | None, ql2_date: str | None) -> list[str]:
    """列出 oct_factors 目录里缺失的交易日（只返回 existings 之后、expected 之前的）。"""
    if not expected:
        return []
    cal = calendar_utils.trade_calendar()
    exp = pd.Timestamp(expected)
    start = pd.Timestamp(ql2_date) if ql2_date else exp - pd.Timedelta(days=10)
    dates = [d for d in cal if start < d <= exp]
    out = []
    for d in dates:
        f = config.WORK_DIR / "oct_factors" / (d.strftime("%Y%m%d") + ".parquet")
        if not f.exists():
            out.append(d.strftime("%Y%m%d"))
    return out


def backfill(st: dict, allow: bool = True) -> dict:
    """按缺失项触发补数据。返回每步结果。"""
    result: dict[str, dict] = {}
    if not allow:
        return {"skipped": {"ok": True, "detail": "backfill disabled"}}
    stale = set(st.get("stale", []))

    if "pit" in stale:
        ps = r"D:\AStockWorker\scripts\run_daily_factor_pit_refresh.ps1"
        rc, tail = _run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", ps],
                        3600, "backfill_pit")
        result["pit"] = {"rc": rc, "tail": tail}

    if "ql2" in stale:
        # L2 数据缺口：按缺失交易日下载 + 因子 + 日线因子 + 冠军选股
        missing = _missing_oct_dates(st.get("expected"), st.get("ql2"))
        steps = []
        for script, timeout, extra in [
            ("dl_oct.py", 3600, ["--dates", ",".join(missing)]),
            ("compute_oct.py", 3600, ["--dates", ",".join(missing)]),
            ("tdx_daily_factors.py", 1800, ["--start", "20260601",
                                             "--end", (st.get("expected") or "").replace("-", ""),
                                             "--ref", missing[-1] if missing else ""]),
            ("champion_daily.py", 1800, []),
        ]:
            path = config.WORK_DIR / script
            if not path.exists():
                steps.append({"script": script, "rc": -1, "tail": "missing"})
                continue
            rc, tail = _run([PY, str(path)] + extra, timeout, f"backfill_{script.replace('.py','')}")
            steps.append({"script": script, "rc": rc, "tail": tail})
        result["ql2"] = {"steps": steps, "missing": missing}

    if "v11" in stale:
        root = config.SELECTOR_ROOT
        rc, tail = _run([PY, str(root / "scripts" / "run_daily_select.py")], 1800, "backfill_v11")
        result["v11"] = {"rc": rc, "tail": tail}

    if "b1" in stale:
        script = config.ROOT / "BP1.0" / "src" / "bp1_0_daily_run.py"
        if script.exists():
            rc, tail = _run([PY, str(script)], 1200, "backfill_b1")
            result["b1"] = {"rc": rc, "tail": tail}
        else:
            result["b1"] = {"rc": -1, "tail": "bp1_0_daily_run.py missing"}

    return result


def save(st: dict, backfill_result: dict | None = None) -> Path:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    p = LOG_DIR / "freshness.json"
    p.write_text(json.dumps({"status": st, "backfill": backfill_result}, ensure_ascii=False,
                            indent=2, default=str), encoding="utf-8")
    return p
