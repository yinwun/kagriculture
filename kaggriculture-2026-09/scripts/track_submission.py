#!/usr/bin/env python
"""Track a submission's real ladder performance from its public episodes.

The competition does not expose a per-submission score (`publicScore` is None) and
the leaderboard shows only the team's newest submission, so two submissions made
minutes apart cannot be compared by their displayed numbers.  What *is* available
per submission is its public episode list: every game it played, against whom, and
the rewards.  That gives a direct measure of how a version actually performs:

  games, wins/losses/ties, win rate, mean reward margin, and the mean ladder score
  of the opponents it was matched against (from data/leaderboard.json) -- plus the
  trend over time, which is what distinguishes "the version is good" from "the
  version was lucky early".

Usage:
  python scripts/track_submission.py --refs 56307879 56307906 --label night3
  python scripts/track_submission.py --refs 56307879 --csv
"""
import argparse
import csv
import json
import statistics
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STORE = ROOT / "data" / "submission_track.json"


def load_api():
    from kaggle.api.kaggle_api_extended import KaggleApi
    delay = 2
    for _ in range(10):
        try:
            api = KaggleApi()
            api.authenticate()
            return api
        except Exception:  # noqa: BLE001
            time.sleep(delay)
            delay = min(delay * 2, 30)
    raise SystemExit("auth failed")


def retry(fn, *a, **kw):
    delay = 2
    for i in range(6):
        try:
            return fn(*a, **kw)
        except Exception as exc:  # noqa: BLE001
            print(f"  retry {i}: {type(exc).__name__}", flush=True)
            time.sleep(delay)
            delay = min(delay * 2, 30)
    return None


def ratings():
    p = ROOT / "data" / "leaderboard.json"
    if not p.exists():
        return {}
    return {int(r["teamId"]): float(r["score"]) for r in json.loads(p.read_text())
            if r.get("score")}


def summarise(episodes, my_ref, lb):
    rows = []
    for ep in episodes:
        if ep.get("type") != "EPISODE_TYPE_PUBLIC":
            continue
        agents = ep.get("agents") or []
        if len(agents) != 2:
            continue
        mine = [a for a in agents if str(a.get("submissionId")) == str(my_ref)]
        if not mine:
            continue
        mine = mine[0]
        opp = [a for a in agents if a is not mine][0]
        if mine.get("reward") is None or opp.get("reward") is None:
            continue
        opp_score = lb.get(int(opp.get("teamId") or 0))
        rows.append({"time": ep.get("endTime"),
                     "me": float(mine["reward"]), "opp": float(opp["reward"]),
                     "opp_team": opp.get("teamName"), "opp_score": opp_score})
    return sorted(rows, key=lambda r: str(r["time"]))


def report(rows, label):
    n = len(rows)
    if not n:
        print(f"  {label}: no public episodes yet")
        return None
    w = sum(1 for r in rows if r["me"] > r["opp"])
    l = sum(1 for r in rows if r["me"] < r["opp"])
    t = n - w - l
    marg = [r["me"] - r["opp"] for r in rows]
    scores = [r["opp_score"] for r in rows if r["opp_score"]]
    out = {"games": n, "wins": w, "losses": l, "ties": t,
           "win_rate": w / n, "margin_mean": statistics.mean(marg),
           "margin_median": statistics.median(marg),
           "opp_mean_score": statistics.mean(scores) if scores else None,
           "first": rows[0]["time"], "last": rows[-1]["time"]}
    print(f"  {label}: {n} games  W/L/T {w}/{l}/{t}  win {100*out['win_rate']:.1f}%  "
          f"margin {out['margin_mean']:+,.0f} (median {out['margin_median']:+,.0f})  "
          f"opp mean score {out['opp_mean_score'] and round(out['opp_mean_score'])}")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--refs", nargs="+", required=True)
    ap.add_argument("--label", default="")
    ap.add_argument("--labels", nargs="*", default=None, help="one label per ref")
    ap.add_argument("--csv", action="store_true")
    args = ap.parse_args()

    api = load_api()
    lb = ratings()
    store = json.loads(STORE.read_text()) if STORE.exists() else {}
    snap = {"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "refs": {}}
    labels = args.labels or [f"{args.label}_{r}" if args.label else str(r) for r in args.refs]
    for ref, label in zip(args.refs, labels):
        eps = retry(api.competition_list_episodes, int(ref))
        if eps is None:
            print(f"  {label}: episode list failed")
            continue
        eps = [e.to_dict() if hasattr(e, "to_dict") else e for e in eps]
        rows = summarise(eps, ref, lb)
        stats = report(rows, label)
        if stats:
            snap["refs"][str(ref)] = {"label": label, **stats}
            store.setdefault(str(ref), {"label": label, "samples": []})
            store[str(ref)]["samples"].append({"at": snap["at"], **stats})
        if args.csv and rows:
            p = ROOT / "data" / f"track-{label}.csv"
            with open(p, "w", newline="") as fh:
                wtr = csv.DictWriter(fh, fieldnames=list(rows[0]))
                wtr.writeheader()
                wtr.writerows(rows)
            print(f"    wrote {p}")
    STORE.write_text(json.dumps(store, indent=1, default=str))
    print(f"snapshot stored in {STORE}")


if __name__ == "__main__":
    main()
