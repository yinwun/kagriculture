#!/usr/bin/env python
"""Fetch replays for every public episode of a submission ref (Task 42).

Reads `data/pi-episodes-<ref>.json` (produced by the episode-list fetch) and downloads
`episode-<eid>-replay.json` into `data/replays-<ref>/`, skipping files already cached.

Usage: .venv/bin/python scripts/pi_fetch_replays.py --ref 56642424
"""
import argparse
import json
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ref", default="56642424")
    ap.add_argument("--procs", type=int, default=4)
    args = ap.parse_args()
    out = ROOT / "data" / f"replays-{args.ref}"
    out.mkdir(parents=True, exist_ok=True)
    rows = json.loads((ROOT / "data" / f"pi-episodes-{args.ref}.json").read_text())
    todo = [int(r["eid"]) for r in rows]
    print(f"{len(todo)} episodes", flush=True)

    from concurrent.futures import ThreadPoolExecutor
    from kaggle.api.kaggle_api_extended import KaggleApi

    def one(eid):
        p = out / f"episode-{eid}-replay.json"
        if p.exists() and p.stat().st_size > 1000:
            return ("cached", eid)
        api = KaggleApi()
        api.authenticate()
        for attempt in range(5):
            try:
                api.competition_episode_replay(eid, path=str(out), quiet=True)
                break
            except Exception as exc:  # noqa: BLE001
                if attempt == 4:
                    return (f"FAILED {type(exc).__name__}", eid)
                time.sleep(min(3 * (attempt + 1), 15))
        return ("ok" if p.exists() and p.stat().st_size > 1000 else "MISSING", eid)

    got = cached = fail = 0
    with ThreadPoolExecutor(max_workers=args.procs) as ex:
        for i, (st, eid) in enumerate(ex.map(one, todo), 1):
            if st == "ok":
                got += 1
            elif st == "cached":
                cached += 1
            else:
                fail += 1
                print(f"  {st} {eid}", flush=True)
            if i % 10 == 0:
                print(f"  [{i}/{len(todo)}] fetched={got} cached={cached} failed={fail}", flush=True)
    print(f"done: fetched {got}, cached {cached}, failed {fail}", flush=True)


if __name__ == "__main__":
    main()
