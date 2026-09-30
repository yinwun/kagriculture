#!/usr/bin/env python
"""Ladder A/B readout: compare the two tracked submissions side by side.

Fetches the newest submissions, their episodes, and reports per-arm W/L/T,
win rate, opponent quality and margins -- the instrument for deciding which arm
of a fresh-submission A/B is actually stronger on the live ladder.

Usage:
  python scripts/ab_monitor.py [--arms 2] [--chunk 25] [--refresh]
"""
import argparse
import collections
import csv
import io
import json
import statistics
import time
from pathlib import Path

from kaggle.api.kaggle_api_extended import KaggleApi

ROOT = Path(__file__).resolve().parent.parent
LB = ROOT / "data" / "leaderboard.json"


def api_with_retry(tries=8):
    api = KaggleApi()
    for i in range(1, tries + 1):
        try:
            api.authenticate()
            return api
        except Exception as exc:  # noqa: BLE001
            print(f"  auth retry {i}: {type(exc).__name__}", flush=True)
            time.sleep(3 * i)
    raise SystemExit("auth failed")


def call(fn, *a, tries=6, **kw):
    for i in range(1, tries + 1):
        try:
            return fn(*a, **kw)
        except Exception as exc:  # noqa: BLE001
            print(f"  retry {i}: {type(exc).__name__}", flush=True)
            time.sleep(3 * i)
    raise RuntimeError("call failed")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--arms", type=int, default=2)
    ap.add_argument("--chunk", type=int, default=25)
    ap.add_argument("--refresh", action="store_true", help="re-download episodes")
    args = ap.parse_args()

    api = api_with_retry()
    raw = api.competitions_submissions_list("kaggriculture", csv_display=True, quiet=True) \
        if hasattr(api, "competitions_submissions_list") else None
    # simplest reliable path: reuse the CLI-equivalent call
    subs = call(api.competition_submissions, "kaggriculture")
    rows = [s.to_dict() if hasattr(s, "to_dict") else dict(s) for s in subs]
    rows.sort(key=lambda r: str(r.get("date")), reverse=True)
    arms = rows[: args.arms]

    lb = {}
    if LB.exists():
        lb = {e["teamId"]: (e["teamName"], float(e["score"])) for e in json.loads(LB.read_text())}

    print(f"{'submission':>10} {'status':<26} {'score':>9}  {'submitted':<17} description")
    for r in arms:
        st = str(r.get("status", "")).split(".")[-1]
        score = r.get("publicScore") or "-"
        print(f"{r['ref']:>10} {st:<26} {score:>9}  {str(r.get('date'))[:16]:<17} {r.get('description') or ''}")

    cache = ROOT / "data" / "ab_episodes"
    cache.mkdir(parents=True, exist_ok=True)
    print()
    for r in arms:
        sid = int(r["ref"])
        p = cache / f"{sid}.json"
        if args.refresh or not p.exists():
            eps = call(api.competition_list_episodes, sid)
            p.write_text(json.dumps([e.to_dict() if hasattr(e, "to_dict") else dict(e) for e in eps]))
            time.sleep(0.5)
        eps = json.loads(p.read_text())
        pub = [e for e in eps if e.get("type") == "EPISODE_TYPE_PUBLIC" and e.get("endTime")]
        rows2 = []
        for ep in pub:
            ags = ep.get("agents") or []
            mine = [a for a in ags if a.get("submissionId") == sid]
            if not mine or len(ags) != 2:
                continue
            me = mine[0]
            opp = [a for a in ags if a is not me][0]
            if me.get("reward") is None or opp.get("reward") is None:
                continue
            res = "win" if me["reward"] > opp["reward"] else "loss" if me["reward"] < opp["reward"] else "tie"
            rows2.append((ep["endTime"], res, lb.get(opp.get("teamId"), (None, None))[1],
                          me["reward"] - opp["reward"]))
        rows2.sort()
        n = len(rows2)
        w = sum(1 for x in rows2 if x[1] == "win")
        l = sum(1 for x in rows2 if x[1] == "loss")
        t = n - w - l
        wr = w / n * 100 if n else 0
        opps = [x[2] for x in rows2 if x[2]]
        print(f"[{sid}] {r.get('description') or ''}")
        print(f"    games={n}  W={w} L={l} T={t}  winrate={wr:.1f}%  "
              f"mean opponent rating={statistics.mean(opps) if opps else 0:,.0f}")
        for i in range(0, n, args.chunk):
            ch = rows2[i:i + args.chunk]
            cw = sum(1 for x in ch if x[1] == "win")
            clo = [x[2] for x in ch if x[2]]
            print(f"      {i + 1:>4}-{i + len(ch):<4} WR={cw / len(ch) * 100:>5.1f}%  "
                  f"opp={statistics.mean(clo) if clo else 0:>7,.0f}  "
                  f"margin={statistics.mean([x[3] for x in ch]):>+9,.0f}  "
                  f"({ch[0][0][:16]} → {ch[-1][0][:16]})")
        print()


if __name__ == "__main__":
    main()
