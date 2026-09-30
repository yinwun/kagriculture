#!/usr/bin/env python
"""Estimate the true strength of the opponents in our ladder games.

The leaderboard `score` is the rating of the team's currently tracked submission, which
is often a *newer* submission than the one we faced (and therefore immature).  This
fetches, for each opponent submission we actually faced, that submission's own episode
list and computes its own record: games, wins, losses, mean/median reward, mean opponent
reward.  That is a rating-free strength estimate computed from the same games that
produced the rating.

Usage: .venv/bin/python scripts/pi_opp_strength.py --ref 56642424
"""
import argparse
import json
import statistics as st
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ref", default="56642424")
    args = ap.parse_args()
    rows = json.loads((ROOT / "data" / f"pi-episodes-{args.ref}.json").read_text())
    subs = {}
    for r in rows:
        subs.setdefault(str(r["opp_sub"]), []).append(r)
    out_path = ROOT / "data" / f"pi-opp-strength-{args.ref}.json"
    res = json.loads(out_path.read_text()) if out_path.exists() else {}
    from kaggle.api.kaggle_api_extended import KaggleApi
    api = KaggleApi()
    api.authenticate()
    print(f"{len(subs)} distinct opponent submissions", flush=True)
    for i, (sid, mine) in enumerate(sorted(subs.items()), 1):
        if sid in res:
            continue
        eps = None
        for attempt in range(5):
            try:
                eps = api.competition_list_episodes(int(sid))
                break
            except Exception as exc:  # noqa: BLE001
                print(f"  {sid} retry {attempt}: {type(exc).__name__}", flush=True)
                time.sleep(3 * (attempt + 1))
        if eps is None:
            continue
        games = []
        for e in eps:
            d = e.to_dict() if hasattr(e, "to_dict") else dict(e)
            if d.get("type") != "EPISODE_TYPE_PUBLIC":
                continue
            ag = d.get("agents") or []
            me = [a for a in ag if str(a.get("submissionId")) == sid]
            if not me or len(ag) != 2:
                continue
            me = me[0]
            op = [a for a in ag if a is not me][0]
            games.append({"my": float(me.get("reward") or 0),
                          "op": float(op.get("reward") or 0)})
        if not games:
            res[sid] = {"games": 0}
            continue
        mg = [g["my"] - g["op"] for g in games]
        res[sid] = {"games": len(games),
                    "wins": sum(1 for m in mg if m > 0),
                    "losses": sum(1 for m in mg if m <= 0),
                    "mean_reward": st.mean(g["my"] for g in games),
                    "median_reward": st.median(g["my"] for g in games),
                    "mean_margin": st.mean(mg),
                    "mean_opp_reward": st.mean(g["op"] for g in games),
                    "faced_us_margin": [r["margin"] for r in mine],
                    "team": mine[0]["opp_team"], "lb_score": mine[0]["opp_score"]}
        r = res[sid]
        print(f"  [{i}/{len(subs)}] sub {sid} {r['team'][:20]:20s} games {r['games']:3d} "
              f"W-L {r['wins']}-{r['losses']:3d} mean reward {r['mean_reward']:9,.0f} "
              f"vs us {mine[0]['margin']:+,.0f} lb {mine[0]['opp_score']}", flush=True)
        out_path.write_text(json.dumps(res, indent=1))
        time.sleep(0.3)
    out_path.write_text(json.dumps(res, indent=1))
    print(f"wrote {out_path}", flush=True)


if __name__ == "__main__":
    main()
