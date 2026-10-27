# -*- coding: utf-8 -*-
"""全部常量与路径。只放规则与路径，不放数据。"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(r"D:\AStockWorker")
PY = ROOT / ".venv" / "Scripts" / "python.exe"
WORK_DIR = Path(r"D:\CodexData\CodexSupervisor\work")
SELECTOR_ROOT = ROOT / "double_wave_selector_dev"
CZERO_WEB = ROOT / "czero_web"

# ---- 数据路径 ----
PIT_DATASET = ROOT / "data" / "processed" / "dataset_h20_20y_pit_with_st_latest.parquet"
B1_JSON = ROOT / "output" / "b1_daily" / "b1_latest.json"
QL2_CHAMPION_GLOB = "champion_*.csv"
V11_PICKS = SELECTOR_ROOT / "site" / "data" / "picks_v1_1.json"
V11_HISTORY = SELECTOR_ROOT / "output" / "history" / "selected_signals_v1_1.parquet"
SITE_OUT = CZERO_WEB / "site" / "wandering-plan"
LOG_DIR = ROOT / "output" / "logs" / "wandering_plan"

# ---- 组合规则 ----
INITIAL_CAPITAL = 100_000.0
SLOTS = 2
SLOT_WEIGHT = 0.5
PRIORITY = ("B1", "QL2", "V12")
MAX_PER_STREAM = {"B1": 2, "QL2": 1, "V12": 2}

# ---- 执行规则 ----
COST = 0.0021
SLIPPAGE = 0.0005
LIMIT_TOL = 0.011
BUY_DELAY = {"B1": 3, "QL2": 2, "V12": 4}      # T+k 开盘买
SELL_DELAY = {"B1": 1, "QL2": 1}                # 买入后第 k 个交易日收盘卖
V12_HOLD = 22                                    # 买入后第 22 个交易日收盘卖
V12_MIN_PROFIT = 0.20

# ---- 因子阈值（与回测一致，勿改） ----
B1_TH = {"ret1": -0.04767376259, "r60": 0.6283795595, "rcomp": 0.7142856181,
         "pma60": 0.01210050743, "a10": 0.1321854406631303, "sd": 0.08752969938741215}
QL2_TH = {"t_count": 22991.0, "O3": 0.6538615822792053, "C2": 0.6181763410568237,
          "C4": 0.6434561610221863, "N05": 0.05257522314786911}

# ---- 部署（ZPC） ----
ZPC_HOST = "CZERO@192.168.1.72"
SSH_KEY = Path(r"D:\CodexData\CodexSupervisor\keys\zpc_codex_ed25519_20260923")
SSH_KNOWN_HOSTS = Path(r"D:\CodexData\CodexSupervisor\keys\zpc_known_hosts")
ZPC_SITE_DIR = r"C:\AStockWorker\czero_web\site\wandering-plan"
ZPC_LOCAL_URL = "http://192.168.1.72:8901"
