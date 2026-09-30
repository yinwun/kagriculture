#!/usr/bin/env python
"""Submit a build to the ladder, with retries, and report the tracked pair.

Usage:
  python scripts/submit.py data/submits/submission-router2.tar.gz "router2: ..."
  python scripts/submit.py --list
"""
import argparse
import csv
import json
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
COMP = "kaggriculture"


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
    raise SystemExit("authenticate failed")


def retry(fn, *a, tries=8, **kw):
    delay = 2
    for i in range(tries):
        try:
            return fn(*a, **kw)
        except Exception as exc:  # noqa: BLE001
            print(f"  retry {i}: {type(exc).__name__}: {str(exc)[:70]}", flush=True)
            time.sleep(delay)
            delay = min(delay * 2, 30)
    raise SystemExit("call failed")


def show(subs, n=8):
    subs = sorted(subs, key=lambda s: str(getattr(s, "date", "")), reverse=True)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    used = sum(1 for s in subs if str(getattr(s, "date", "")).startswith(today))
    print(f"submissions today: {used} (quota 5)")
    print(f"{'ref':>10} {'date':24} {'status':22} {'public':>9}  description")
    for s in subs[:n]:
        print(f"{getattr(s,'ref',0):>10} {str(getattr(s,'date',''))[:19]:24} "
              f"{str(getattr(s,'status',''))[:21]:22} {str(getattr(s,'publicScore','')):>9}  "
              f"{getattr(s,'description','') or ''}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("file", nargs="?")
    ap.add_argument("message", nargs="?", default="")
    ap.add_argument("--list", action="store_true")
    args = ap.parse_args()
    api = load_api()
    if args.list or not args.file:
        show(retry(api.competition_submissions, COMP, tries=4))
        return
    path = Path(args.file)
    print(f"submitting {path} ({path.stat().st_size:,} bytes) ...", flush=True)
    retry(api.competition_submit, str(path), args.message, COMP, tries=4)
    print("upload accepted", flush=True)
    time.sleep(20)
    subs = retry(api.competition_submissions, COMP, tries=4)
    show(subs, n=4)
    with open(ROOT / "data" / "submissions.csv", "a", newline="") as fh:
        w = csv.writer(fh)
        w.writerow([getattr(subs[0], "ref", ""), path.name,
                    datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
                    args.message, getattr(subs[0], "status", ""),
                    getattr(subs[0], "publicScore", ""), ""])


if __name__ == "__main__":
    main()
