#!/usr/bin/env python
"""Fetch the full kaggriculture leaderboard (paginated, retried -> data/leaderboard.json)."""
import json
import time
from pathlib import Path

from kaggle.api.kaggle_api_extended import KaggleApi
from kagglesdk.competitions.types.competition_api_service import ApiGetLeaderboardRequest

ROOT = Path(__file__).resolve().parent.parent
COMP = "kaggriculture"
PAGE_SIZE = 200


def auth(api, tries=8):
    for i in range(1, tries + 1):
        try:
            api.authenticate()
            return
        except Exception as exc:  # noqa: BLE001
            print(f"auth retry {i}: {type(exc).__name__}", flush=True)
            time.sleep(3 * i)
    raise SystemExit("auth failed")


def call(fn, *a, tries=8, **kw):
    for i in range(1, tries + 1):
        try:
            return fn(*a, **kw)
        except Exception as exc:  # noqa: BLE001
            print(f"  retry {i}: {type(exc).__name__}", flush=True)
            time.sleep(3 * i)
    raise RuntimeError("call failed")


def main():
    api = KaggleApi()
    auth(api)
    out = []
    token = None
    with api.build_kaggle_client() as kaggle:
        for page in range(60):
            req = ApiGetLeaderboardRequest()
            req.competition_name = COMP
            req.page_size = PAGE_SIZE
            if token:
                req.page_token = token
            resp = call(kaggle.competitions.competition_api_client.get_leaderboard, req)
            subs = [s.to_dict() for s in (resp.submissions or []) if s]
            out += subs
            token = resp.next_page_token or None
            print(f"page {page}: +{len(subs)} (total {len(out)})", flush=True)
            if not token or not subs:
                break
    (ROOT / "data" / "leaderboard.json").write_text(json.dumps(out))
    print("total teams:", len(out))


if __name__ == "__main__":
    main()
