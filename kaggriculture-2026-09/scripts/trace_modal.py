#!/usr/bin/env python
"""How scripted is each top team, on full traces, and where does its plan fork?

Uses the official top-team stream corpus (data/top10streams/streams.parquet: every
turn of every episode, farmer action + a hash of the hands block + the market
orders).  Two measurements per team:

  scriptedness -- per turn, the share of that team's episodes playing the *modal*
                  action; averaged over turns.  1.0 means every episode plays the
                  same thing at every turn (a hardcoded tape); low means the team
                  re-decides per game.  Reported overall and per channel, with the
                  market channel restricted to turns where anyone acts.

  fork timeline -- the number of distinct action prefixes over turns, i.e. when the
                  fleet of that team's episodes stops agreeing.  Prints the first
                  split, the day it lands on, and how many distinct plans exist by
                  the end.

Usage:
  python scripts/trace_modal.py --dataset data/top10streams
  python scripts/trace_modal.py --dataset data/top10streams --team カワシギ --forks
"""
import argparse
import json
from pathlib import Path

import pandas as pd


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", default="data/top10streams")
    ap.add_argument("--team", default=None)
    ap.add_argument("--forks", action="store_true")
    ap.add_argument("--out", default="data/trace_modal.json")
    args = ap.parse_args()

    s = pd.read_parquet(Path(args.dataset) / "streams.parquet")
    s["submission"] = s["submission"].astype(str)
    s["episode_id"] = s["episode_id"].astype(str)
    ep = pd.read_csv(Path(args.dataset) / "episodes.csv")[["submission", "episode_id", "team"]]
    ep = ep.drop_duplicates(subset=["submission", "episode_id"])
    ep["submission"] = ep["submission"].astype(str)
    ep["episode_id"] = ep["episode_id"].astype(str)
    s = s.merge(ep, on=["submission", "episode_id"], how="left")
    s = s[s.team.notna()]
    if args.team:
        s = s[s.team == args.team]
    s["full"] = s.farmer + "|" + s.hands_h + "|" + s.market

    rows = []
    for team, g in s.groupby("team"):
        g = g.drop_duplicates(subset=["episode_id", "turn"])
        n_ep = g.episode_id.nunique()
        if n_ep < 5:
            continue
        out = {"team": team, "episodes": int(n_ep)}
        for ch in ("full", "farmer", "market", "hands_h"):
            cnt = g.groupby("turn")[ch].value_counts()
            top = cnt.groupby(level=0).max()
            tot = g.groupby("turn")[ch].size()
            share = (top / tot)
            out[ch] = float(share.mean())
            # restrict to turns where at least one episode acts
            if ch in ("market", "full", "farmer"):
                act = g[g[ch] != ("" if ch == "market" else "[\"PASS\"]")]
                if len(act):
                    c2 = act.groupby("turn")[ch].value_counts()
                    t2 = act.groupby("turn")[ch].size()
                    out[ch + "_active"] = float((c2.groupby(level=0).max() / t2).mean())
                    out[ch + "_n"] = int(len(act))
        rows.append(out)

    df = pd.DataFrame(rows).sort_values("full")
    cols = ["team", "episodes", "full", "farmer", "market", "market_active", "hands_h"]
    print(df[[c for c in cols if c in df]].to_string(index=False, float_format=lambda x: f"{x:.3f}"))
    print("\nscriptedness = mean share of episodes playing the modal action at a turn.")
    print("full = farmer+hands-hash+market.  market_active = only turns where someone trades.")
    Path(args.out).write_text(json.dumps(rows, indent=1, default=str))

    if args.forks:
        print("\n=== fork timeline ===")
        for team, g in s.groupby("team"):
            g = g.drop_duplicates(subset=["episode_id", "turn"])
            n_ep = g.episode_id.nunique()
            if n_ep < 5:
                continue
            # prefix-class growth
            piv = g.pivot_table(index="episode_id", columns="turn", values="full",
                                aggfunc="first")
            piv = piv.sort_index(axis=1)
            classes = []
            seen = {}
            for t in piv.columns:
                key = tuple(piv[t].fillna("?"))
                seen.setdefault(key, len(seen))
                classes.append(len(seen))
            first = next((i for i, c in enumerate(classes) if c > 1), None)
            day = (piv.columns[first] // 24) if first is not None else None
            print(f"{team:32s} eps={n_ep:4d} first split at turn "
                  f"{piv.columns[first] if first is not None else '-'} (day {day}), "
                  f"distinct plans by end: {classes[-1]}")
            # per-day distinct action counts (are days modules?)
            g2 = g.copy()
            g2["day"] = g2.turn // 24
            perday = g2.groupby("day")["full"].nunique() / n_ep
            print("     per-day distinct-action share:",
                  " ".join(f"{v:.2f}" for v in perday.values))
    print(f"\nwrote {args.out}")


if __name__ == "__main__":
    main()
