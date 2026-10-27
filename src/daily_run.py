# -*- coding: utf-8 -*-
"""日更入口：数据检查 → 三路信号 → 组合排程 → 页面 → 部署 → 通知。"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

import pandas as pd

from . import b1_signal, bars, calendar_utils, combo, config, freshness, ql2_signal, site_data, site_page, v12_signal

PY = str(config.PY)


def _log(msg: str) -> None:
    print(f"[wandering-plan] {msg}", flush=True)


def _notify(msg: str) -> None:
    """复用 czero_web 的微信通道；失败不影响主流程。"""
    cfg_path = config.CZERO_WEB / "config" / "auth.json"
    if not cfg_path.exists():
        return
    try:
        cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
        wx = cfg.get("wechat") or {}
        target = wx.get("target")
        if not target:
            return
        cmd = ["openclaw", "message", "send", "--channel", str(wx.get("channel", "wechat")),
               "--target", str(target), "--message", msg]
        if wx.get("account"):
            cmd += ["--account", str(wx["account"])]
        subprocess.run(cmd, capture_output=True, timeout=60)
    except Exception as exc:
        _log(f"notify failed: {exc}")


def _deploy(html_path: Path) -> tuple[bool, str]:
    """scp 页面 + 站点数据 JSON 到 ZPC 并校验。"""
    ssh = r"C:\Users\astock.LAPTOP-U66OF3K2\MinGit\usr\bin\ssh.exe"
    scp = r"C:\Program Files\OpenSSH\OpenSSH-Win64\scp.exe"
    key = str(config.SSH_KEY)
    kh = str(config.SSH_KNOWN_HOSTS)
    remote_dir = config.ZPC_SITE_DIR.replace("\\", "/")
    remote_file = remote_dir + "/index.html"
    remote_data_dir = config.ZPC_DATA_DIR.replace("\\", "/")
    remote_data_file = remote_data_dir + "/wandering_plan.json"
    try:
        subprocess.run([ssh, "-i", key, "-o", "StrictHostKeyChecking=no", "-o", f"UserKnownHostsFile={kh}",
                        config.ZPC_HOST, f'powershell -NoProfile -Command New-Item -ItemType Directory -Force -Path "{config.ZPC_SITE_DIR}" | Out-Null; New-Item -ItemType Directory -Force -Path "{config.ZPC_DATA_DIR}" | Out-Null'],
                       capture_output=True, timeout=60)
        p = subprocess.run([scp, "-q", "-i", key, "-o", "StrictHostKeyChecking=no", "-o", f"UserKnownHostsFile={kh}",
                            str(html_path), f"{config.ZPC_HOST}:{remote_file}"],
                           capture_output=True, timeout=120, text=True)
        if p.returncode != 0:
            return False, f"scp rc={p.returncode} {p.stderr[:200]}"
        j = subprocess.run([scp, "-q", "-i", key, "-o", "StrictHostKeyChecking=no", "-o", f"UserKnownHostsFile={kh}",
                            str(config.SITE_DATA_OUT), f"{config.ZPC_HOST}:{remote_data_file}"],
                           capture_output=True, timeout=120, text=True)
        if j.returncode != 0:
            return False, f"scp json rc={j.returncode} {j.stderr[:200]}"
        q = subprocess.run([ssh, "-i", key, "-o", "StrictHostKeyChecking=no", "-o", f"UserKnownHostsFile={kh}",
                            config.ZPC_HOST,
                            'powershell -NoProfile -Command "(Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8901/wandering-plan/ -TimeoutSec 10).StatusCode"'],
                           capture_output=True, timeout=60, text=True)
        ok = "200" in (q.stdout or "")
        return ok, (q.stdout or q.stderr or "")[:200]
    except Exception as exc:
        return False, str(exc)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="流浪计划日更")
    ap.add_argument("--as-of", default=None, help="信号日（默认自动取最新）")
    ap.add_argument("--capital", type=float, default=config.INITIAL_CAPITAL)
    ap.add_argument("--no-deploy", action="store_true")
    ap.add_argument("--skip-backfill", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)

    cal = calendar_utils.trade_calendar()
    st = freshness.status(cal)
    _log(f"freshness: {json.dumps(st, ensure_ascii=False)}")

    backfill_result = None
    if not st["ok"] and not a.skip_backfill and not a.dry_run and not a.as_of:
        _log("检测到数据缺口，开始补数据…")
        backfill_result = freshness.backfill(st, allow=True)
        st = freshness.status(cal)
        _log(f"补数据后 freshness: {json.dumps(st, ensure_ascii=False)}")
    freshness.save(st, backfill_result)

    data_date = pd.Timestamp(a.as_of) if a.as_of else None
    if data_date is None:
        candidates = [d for d in (st.get("pit"), st.get("b1"), st.get("ql2"), st.get("v11")) if d]
        data_date = max(pd.Timestamp(d) for d in candidates) if candidates else pd.Timestamp.today().normalize()

    signals = b1_signal.load_signals() + ql2_signal.load_signals(cal) + v12_signal.load_signals(cal)
    _log(f"signals: B1={sum(1 for s in signals if s['source']=='B1')} "
         f"QL2={sum(1 for s in signals if s['source']=='QL2')} "
         f"V12={sum(1 for s in signals if s['source']=='V12')}")

    plan = combo.build_plan(signals, cal, data_date, capital=a.capital)
    expected = st.get("expected")
    # 以「已发布的基准数据日」为最新可得日：与之持平即视为最新（数据管道滞后时不再误报）
    try:
        from .site_data import _bench_series
        bench_last = _bench_series().index.max()
    except Exception:
        bench_last = None
    if bench_last is not None:
        stale = pd.Timestamp(data_date) < pd.Timestamp(bench_last)
        reason = (f"数据只到 {data_date.date()}，最新可得 {pd.Timestamp(bench_last).date()}"
                  if stale else "")
    else:
        stale = bool(expected and str(data_date)[:10] < expected)
        reason = f"数据只到 {data_date.date()}，最近交易日是 {expected}" if stale else ""

    out = config.LOG_DIR
    out.mkdir(parents=True, exist_ok=True)
    (out / "plan.json").write_text(json.dumps(plan, ensure_ascii=False, indent=2, default=str), encoding="utf-8")

    # 站点同格式数据（与 bp2_3.json 对齐，供 app.js 渲染）
    site_payload = site_data.build(plan, signals, cal, data_date, expected, stale)
    site_path = site_data.write(site_payload)
    _log(f"site data written: {site_path}")

    # 与现有策略页同壳的页面（从 BP2.3 模板生成）
    page_path, missing = site_page.build_page()
    _log(f"page written: {page_path} missing={missing}")

    summary = "今日无买入信号" if plan["status"] == "no_signal" else \
        "买入：" + "、".join(f"{s['symbol']} {s.get('name','')}" for s in plan["buys"])
    _log(summary)

    if a.dry_run:
        _log("dry-run：跳过部署与通知")
        return 0

    ok = True
    if not a.no_deploy:
        ok, detail = _deploy(config.SITE_OUT / "index.html")
        _log(f"deploy: {ok} {detail}")
    _notify(f"流浪计划 {pd.Timestamp(data_date).date()}\n{summary}\n页面：{config.ZPC_LOCAL_URL}/wandering-plan/")
    if stale:
        _notify(f"流浪计划警告：{reason}")
        return 1
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
