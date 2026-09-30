#!/usr/bin/env python
"""Fetch every episode played by nickyl's kaggriculture submissions.

Caches one JSON file per submission id under data/episodes/.
Retries on the flaky network resets seen from the Kaggle API.
"""
import csv
import json
import os
import sys
import time
from pathlib import Path

from kaggle.api.kaggle_api_extended import KaggleApi

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "episodes"
OUT.mkdir(parents=True, exist_ok=True)

TEAM = os.environ.get("KG_TEAM", "nickyl")


def with_retry(fn, *args, tries=6):
    delay = 2
    for attempt in range(1, tries + 1):
        try:
            return fn(*args)
        except Exception as exc:  # noqa: BLE001 - network flakiness only
            if attempt == tries:
                raise
            print(f"    retry {attempt}: {type(exc).__name__}: {exc}", flush=True)
            time.sleep(delay)
            delay = min(delay * 2, 30)


def main() -> int:
    api = KaggleApi()
    with_retry(api.authenticate, tries=10)
    print("authenticated", flush=True)

    rows = list(csv.DictReader(open(ROOT / "data" / "submissions.csv")))
    complete = [r for r in rows if r["status"].endswith("COMPLETE")]
    print(f"{len(rows)} submissions, {len(complete)} complete", flush=True)

    failed = []
    for i, row in enumerate(complete, 1):
        sid = int(row["ref"])
        path = OUT / f"{sid}.json"
        if path.exists() and path.stat().st_size > 2:
            print(f"[{i}/{len(complete)}] {sid} cached", flush=True)
            continue
        print(f"[{i}/{len(complete)}] {sid} {row['fileName']}", flush=True)
        try:
            eps = with_retry(api.competition_list_episodes, sid, tries=8)
        except Exception as exc:  # noqa: BLE001
            print(f"    FAILED {sid}: {exc}", flush=True)
            failed.append(sid)
            continue
        data = [e.to_dict() if hasattr(e, "to_dict") else dict(e) for e in eps]
        path.write_text(json.dumps(data))
        time.sleep(0.5)

    print(f"done, failed={failed}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
