#!/usr/bin/env python
"""Download replays for the episodes selected by scripts/replay_manifest.py.

`KaggleApi.competition_episode_replay(eid, path=...)` DOWNLOADS a file named
`episode-<eid>-replay.json` and returns None (passing no path drops it in cwd and
still returns None -- measured: a bare call yields `null`).
"""
import argparse
import json
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "replays"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", default=str(ROOT / "data" / "replay-manifest.json"))
    ap.add_argument("--refs", nargs="*", default=None)
    ap.add_argument("--out", default=str(OUT))
    args = ap.parse_args()
    from kaggle.api.kaggle_api_extended import KaggleApi
    api = KaggleApi()
    api.authenticate()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    man = json.loads(Path(args.manifest).read_text())
    todo = []
    for ref, d in man.items():
        if args.refs and ref not in args.refs:
            continue
        for r in d["selected"]:
            todo.append((ref, int(r["episode"]), r["margin"]))
    print(f"{len(todo)} replays to fetch", flush=True)
    got = skipped = failed = 0
    for ref, eid, marg in todo:
        p = out / f"episode-{eid}-replay.json"
        if p.exists() and p.stat().st_size > 1000:
            skipped += 1
            continue
        for attempt in range(6):
            try:
                api.competition_episode_replay(eid, path=str(out), quiet=True)
                break
            except Exception as exc:  # noqa: BLE001
                if attempt == 5:
                    print(f"  FAILED {eid}: {type(exc).__name__}", flush=True)
                    failed += 1
                    break
                time.sleep(min(2 * (attempt + 1), 12))
        if p.exists() and p.stat().st_size > 1000:
            got += 1
            if got % 10 == 0:
                print(f"  {got} fetched (last {eid} margin {marg:+,.0f})", flush=True)
        else:
            failed += 1
        time.sleep(0.4)
    print(f"done: fetched {got}, cached {skipped}, failed {failed}", flush=True)


if __name__ == "__main__":
    main()
