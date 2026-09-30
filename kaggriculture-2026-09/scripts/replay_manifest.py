#!/usr/bin/env python
"""Classify a submission's public episodes by reward margin and emit a replay
download manifest (losses / near-losses + a rating-matched win control).

Usage:
  python scripts/replay_manifest.py --refs 56422944 56409633 --near 2000
"""
import argparse
import collections
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def load(ref):
    return json.loads((ROOT / "data" / f"episodes-{ref}-raw.json").read_text())


def rows(eps, ref, lb):
    out = []
    for ep in eps:
        if ep.get("type") != "EPISODE_TYPE_PUBLIC":
            continue
        ag = ep.get("agents") or []
        if len(ag) != 2:
            continue
        me = [a for a in ag if str(a.get("submissionId")) == str(ref)]
        if not me:
            continue
        me = me[0]
        opp = [a for a in ag if a is not me][0]
        if me.get("reward") is None or opp.get("reward") is None:
            continue
        out.append({"episode": ep.get("id"), "end": str(ep.get("endTime")),
                    "me": float(me["reward"]), "opp": float(opp["reward"]),
                    "margin": float(me["reward"]) - float(opp["reward"]),
                    "opp_team": opp.get("teamName"), "opp_score": lb.get(int(opp.get("teamId") or 0)),
                    "opp_sub": str(opp.get("submissionId"))})
    return sorted(out, key=lambda r: r["end"])


def band(s):
    if s is None:
        return "unknown"
    for lo, hi in ((0, 1500), (1500, 1800), (1800, 2100), (2100, 2400), (2400, 2700), (2700, 10 ** 9)):
        if lo <= s < hi:
            return f"{lo}-{hi if hi < 10**9 else '+'}"
    return "?"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--refs", nargs="+", required=True)
    ap.add_argument("--near", type=float, default=2000.0)
    ap.add_argument("--since", default=None, help="only games ending strictly after this ISO time")
    ap.add_argument("--out", default=str(ROOT / "data" / "replay-manifest.json"))
    args = ap.parse_args()
    lb = {int(r["teamId"]): float(r["score"]) for r in json.loads(
        (ROOT / "data" / "leaderboard.json").read_text()) if r.get("score")}
    man = {}
    for ref in args.refs:
        rs = rows(load(ref), ref, lb)
        if args.since:
            rs = [r for r in rs if str(r["end"]) > args.since]
        all_margins = [r["margin"] for r in rs]
        losses = [r for r in rs if r["margin"] < 0]
        near = [r for r in rs if 0 <= r["margin"] <= args.near]
        wins = [r for r in rs if r["margin"] > args.near]
        # rating-matched win control: for each selected loss/near-loss take one win from
        # the same opponent-rating band (closest margin, unused)
        pick = losses + near
        want = collections.Counter(band(r["opp_score"]) for r in pick)
        ctrl, used = [], set()
        for b, k in want.items():
            pool = sorted([w for w in wins if band(w["opp_score"]) == b and w["episode"] not in used],
                          key=lambda w: w["margin"])
            for w in pool[:k]:
                used.add(w["episode"])
                ctrl.append(w)
        sel = pick + ctrl
        print(f"\nref {ref}: {len(rs)} games{' since ' + args.since if args.since else ''} "
              f"| losses {len(losses)} | near(0..{args.near:.0f}) {len(near)} "
              f"| wins >{args.near:.0f} {len(wins)} | control {len(ctrl)}")
        if all_margins:
            print(f"  margin: min {min(all_margins):+,.0f} median "
                  f"{sorted(all_margins)[len(all_margins)//2]:+,.0f} max {max(all_margins):+,.0f}")
        print(f"  selected {len(sel)} replays: " +
              ", ".join(f"{'L' if r['margin']<0 else ('N' if r['margin']<=args.near else 'W')}{r['margin']:+,.0f}"
                        for r in sorted(sel, key=lambda r: r["margin"])))
        man[str(ref)] = {"n_games": len(rs), "losses": len(losses), "near": len(near),
                         "wins": len(wins), "selected": sel}
    Path(args.out).write_text(json.dumps(man, indent=1))
    print(f"\nwrote {args.out}")


if __name__ == "__main__":
    main()
