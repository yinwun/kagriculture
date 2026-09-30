#!/usr/bin/env python
"""Fetch top-team replays from the episode list we already have.

data/episodes/*.json is actually the competition's recent global episode list
(each entry carries both agents' teamId/teamName/submissionId), so top-5 teams
are directly reachable: pick episodes containing a target teamId and download the
replay.  Retries hard, because the Kaggle API resets connections often.

Usage:
  python scripts/fetch_top.py --team 16718819 --n 8
"""
import argparse
import glob
import json
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "top"


def load_api():
    from kaggle.api.kaggle_api_extended import KaggleApi
    delay = 2
    for i in range(10):
        try:
            api = KaggleApi()
            api.authenticate()
            return api
        except Exception as exc:  # noqa: BLE001
            print(f"  auth retry {i}: {type(exc).__name__}", flush=True)
            time.sleep(delay)
            delay = min(delay * 2, 30)
    raise SystemExit("could not authenticate")


def retry(fn, *a, tries=8, label=""):
    delay = 2
    for i in range(tries):
        try:
            return fn(*a)
        except Exception as exc:  # noqa: BLE001
            print(f"  {label} retry {i}: {type(exc).__name__}: {str(exc)[:60]}", flush=True)
            time.sleep(delay)
            delay = min(delay * 2, 30)
    return None


def candidates(team_ids):
    lb = {int(r["teamId"]): (r["teamName"], float(r["score"]))
          for r in json.load(open(ROOT / "data" / "leaderboard.json")) if r.get("score")}
    out = {}
    for f in glob.glob(str(ROOT / "data" / "episodes" / "*.json")):
        try:
            eps = json.load(open(f))
        except Exception:  # noqa: BLE001
            continue
        for e in eps:
            tids = [a.get("teamId") for a in (e.get("agents") or []) if a.get("teamId")]
            hit = [t for t in team_ids if t in tids]
            if not hit or len(tids) != 2:
                continue
            other = [t for t in tids if t not in team_ids]
            other = other[0] if other else tids[0]
            nm, sc = lb.get(other, ("?", 0.0))
            out.setdefault(hit[0], {})[e["id"]] = {
                "episode": e["id"], "time": e.get("createTime"), "vs": other,
                "vs_name": nm, "vs_score": sc,
                "rewards": {a.get("teamId"): a.get("reward") for a in e["agents"]},
            }
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--team", type=int, action="append", required=True)
    ap.add_argument("--n", type=int, default=6)
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    cand = candidates(args.team)
    for tid, eps in cand.items():
        rows = sorted(eps.values(), key=lambda r: -(r["vs_score"] or 0))
        print(f"team {tid}: {len(rows)} episodes cached in the list", flush=True)
        for r in rows[:3]:
            print(f"   vs {r['vs_name']} ({r['vs_score']:.0f}) ep {r['episode']}", flush=True)
        (OUT / f"candidates-{tid}.json").write_text(json.dumps(rows))
    api = load_api()
    n = 0
    for tid, eps in cand.items():
        rows = sorted(eps.values(), key=lambda r: -(r["vs_score"] or 0))
        picks = rows[: max(1, args.n // 2)] + rows[-max(1, args.n // 2):]
        for r in picks:
            eid = r["episode"]
            p = OUT / f"episode-{eid}-replay.json"
            if p.exists() and p.stat().st_size > 10:
                print(f"  cached {eid}", flush=True)
                continue
            rep = retry(api.competition_episode_replay, eid, label=str(eid))
            if rep is None:
                print(f"  FAILED {eid}", flush=True)
                continue
            txt = rep if isinstance(rep, str) else json.dumps(rep)
            p.write_text(txt)
            n += 1
            print(f"  saved {eid} vs {r['vs_name']} ({len(txt):,} bytes)", flush=True)
            time.sleep(1)
    print(f"done: {n} new replays in {OUT}")


if __name__ == "__main__":
    main()
