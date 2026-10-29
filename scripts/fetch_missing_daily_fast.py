# -*- coding: utf-8 -*-
"""快速补齐 raw_sina 缺失日线（腾讯 kline 接口，多线程）。"""
from __future__ import annotations

import argparse
import json
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(r"D:\AStockWorker")
RAW = ROOT / "data" / "raw_sina"
HEADER = "date,open,high,low,close,volume,amount,outstanding_share,turnover,symbol,source"


def tx_code(symbol: str) -> str:
    s = str(symbol).zfill(6)
    return ("sh" if s.startswith(("5", "6", "9")) else "sz") + s


def last_date(path: Path) -> str:
    try:
        with path.open("rb") as f:
            f.seek(0, 2)
            size = f.tell()
            f.seek(max(0, size - 200))
            tail = f.read().decode("utf-8", "replace").strip().splitlines()
        for line in reversed(tail):
            if not line or line.startswith("date,"):
                continue
            return line.split(",")[0].strip()
    except Exception:
        return ""
    return ""


def fetch(symbol: str, start: str, end: str) -> list[str]:
    url = (f"https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?"
           f"param={tx_code(symbol)},day,{start},{end},800,qfq")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    raw = urllib.request.urlopen(req, timeout=20).read().decode("utf-8", "replace")
    payload = json.loads(raw)
    data = payload.get("data") if isinstance(payload, dict) else None
    node = data.get(tx_code(symbol), {}) if isinstance(data, dict) else {}
    if not isinstance(node, dict):
        node = {}
    rows = node.get("qfqday") or node.get("day") or []
    out = []
    for r in rows:
        if len(r) < 6:
            continue
        d, op, cl, hi, lo, vol = r[0], r[1], r[2], r[3], r[4], float(r[5])
        if d.replace("-", "") <= start.replace("-", ""):
            continue
        # 腾讯 qfqday 的成交量是“手”；创业板/科创板历史 raw_sina 用“股”，需 ×100
        if symbol.startswith(("300", "301", "688")):
            vol = vol * 100.0
        out.append(f"{d},{op},{hi},{lo},{cl},{vol:.0f},,,,{symbol},tencent_unadjusted")
    return out


def update_one(path: Path, end: str) -> dict:
    sym = path.stem.zfill(6)
    last = last_date(path)
    if not last or last >= end:
        return {"symbol": sym, "status": "skipped", "last": last}
    start = last
    rows = fetch(sym, start, end)
    if not rows:
        return {"symbol": sym, "status": "no_new", "last": last}
    # 简单追加；下一轮通过 last_date 去重
    text = "\n".join(rows) + "\n"
    with path.open("ab") as f:
        f.write(text.encode("utf-8"))
    return {"symbol": sym, "status": "updated", "rows": len(rows), "last": last}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--end", required=True)
    ap.add_argument("--workers", type=int, default=32)
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()
    paths = sorted(RAW.glob("*.csv"))
    if a.limit:
        paths = paths[:a.limit]
    ok = bad = skip = 0
    failures = []
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=max(1, a.workers)) as pool:
        futs = {pool.submit(update_one, p, a.end): p for p in paths}
        for i, fut in enumerate(as_completed(futs), 1):
            p = futs[fut]
            try:
                r = fut.result()
                if r["status"] == "updated":
                    ok += 1
                elif r["status"] == "skipped":
                    skip += 1
                else:
                    bad += 1
            except Exception as exc:  # noqa: BLE001
                failures.append({"symbol": p.stem, "error": str(exc)[:200]})
            if i % 500 == 0:
                print(f"[{i}/{len(paths)}] updated={ok} skipped={skip} failed={len(failures)} elapsed={time.time()-t0:.0f}s", flush=True)
    print(json.dumps({"requested": len(paths), "updated": ok, "skipped": skip, "failed": len(failures),
                      "elapsed_s": round(time.time() - t0, 1)}, ensure_ascii=False))
    if failures:
        (ROOT / "data" / "processed" / "fast_fetch_failures.json").write_text(
            json.dumps(failures, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
