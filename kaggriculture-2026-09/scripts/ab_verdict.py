#!/usr/bin/env python
"""A/B verdict on two submissions from their public episodes.

The competition exposes no per-submission score, and both lines are still
undefeated, so raw win rate carries no information yet.  What does carry signal:

  * the *strength of the opponents* each line is matched against -- the ladder
    pairs by rating, so a line facing stronger opponents is itself rated higher;
  * the reward margin, compared inside the opponent-score band both lines share
    (a matched-band comparison avoids "A won by more because A met weaker bots").

Usage:
  python scripts/ab_verdict.py --a data/track-A_v42baseline.csv --b data/track-B_rgcs.csv
"""
import argparse
import csv
import random
import statistics
from pathlib import Path


def load(path):
    rows = []
    with open(path, newline="") as fh:
        for r in csv.DictReader(fh):
            if not r.get("me"):
                continue
            rows.append({"me": float(r["me"]), "opp": float(r["opp"]),
                         "opp_score": float(r["opp_score"]) if r.get("opp_score") not in (None, "", "None") else None,
                         "time": r.get("time")})
    return rows


def describe(name, rows):
    n = len(rows)
    w = sum(1 for r in rows if r["me"] > r["opp"])
    marg = [r["me"] - r["opp"] for r in rows]
    sc = [r["opp_score"] for r in rows if r["opp_score"]]
    print(f"{name}: games {n}  W-L {w}-{n - w}  win {100*w/max(1,n):.1f}%  "
          f"margin mean {statistics.mean(marg):+,.0f} median {statistics.median(marg):+,.0f}")
    if sc:
        print(f"    opponents: mean {statistics.mean(sc):.0f} median {statistics.median(sc):.0f} "
              f"min {min(sc):.0f} max {max(sc):.0f}")
    return {"n": n, "wins": w, "margin": statistics.mean(marg) if marg else 0,
            "opp_mean": statistics.mean(sc) if sc else None}


def matched_band(a, b):
    """Compare margins only where both lines met comparable opponents."""
    sa = [r["opp_score"] for r in a if r["opp_score"]]
    sb = [r["opp_score"] for r in b if r["opp_score"]]
    if not sa or not sb:
        return None
    lo = max(min(sa), min(sb))
    hi = min(max(sa), max(sb))
    if lo >= hi:
        lo, hi = min(min(sa), min(sb)), max(max(sa), max(sb))
    fa = [r for r in a if r["opp_score"] and lo <= r["opp_score"] <= hi]
    fb = [r for r in b if r["opp_score"] and lo <= r["opp_score"] <= hi]
    if not fa or not fb:
        return None
    ma = [r["me"] - r["opp"] for r in fa]
    mb = [r["me"] - r["opp"] for r in fb]
    return {"band": (lo, hi), "a_n": len(ma), "b_n": len(mb),
            "a_margin": statistics.mean(ma), "b_margin": statistics.mean(mb)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--a", default="data/track-A_v42baseline.csv")
    ap.add_argument("--b", default="data/track-B_rgcs.csv")
    args = ap.parse_args()
    pa, pb = Path(args.a), Path(args.b)
    if not (pa.exists() and pb.exists()):
        raise SystemExit("missing csv dumps; run track_submission.py --csv first")
    a, b = load(pa), load(pb)
    sa = describe("A (V42 baseline)", a)
    sb = describe("B (RG+CS)", b)
    mb = matched_band(a, b)
    print()
    if mb:
        lo, hi = mb["band"]
        print(f"matched opponent band [{lo:.0f},{hi:.0f}]: A n={mb['a_n']} margin {mb['a_margin']:+,.0f} | "
              f"B n={mb['b_n']} margin {mb['b_margin']:+,.0f}")
    else:
        print("no overlapping opponent band yet (one line has met only weak or only strong opponents)")
    print()
    if sa["opp_mean"] and sb["opp_mean"]:
        d = sb["opp_mean"] - sa["opp_mean"]
        print(f"opponent-strength gap B-A: {d:+,.0f} ladder points "
              f"({'B is being matched against stronger opponents -> B rates higher' if d > 0 else 'A rates higher'})")
    both_undefeated = sa["wins"] == sa["n"] and sb["wins"] == sb["n"]
    if both_undefeated:
        print("verdict: both undefeated -- win rate cannot separate them yet; "
              "use the opponent-strength signal and the local paired evidence")


if __name__ == "__main__":
    main()
