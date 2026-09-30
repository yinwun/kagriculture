#!/usr/bin/env python
"""Turn a real ladder replay into a "recorded opponent" agent.

A kaggriculture replay stores the exact 720-step action sequence of both seats.
Replaying one seat's actions verbatim gives an open-loop opponent that is as
strong as that ladder bot was in that game -- useful for building an elite local
panel when the bot's code is private.

IMPORTANT: a recorded action plan is only coherent in the world it was recorded
in, so it must be played with the same `seed` as the replay.

Usage:
  python scripts/make_recorded_opponent.py <replay.json> <seat 0|1> <outdir>
"""
import argparse
import json
import os
from pathlib import Path

TEMPLATE = '''"""Recorded opponent: {team} (seat {seat}) from ladder episode {episode}.

Open-loop replay of the actions this bot actually issued in that game.
Play only with seed={seed} so the world (town shops, market) matches.
"""
_PLAN = {plan!r}


def agent(observation, configuration=None):
    step = int(observation["step"])
    if 0 <= step < len(_PLAN):
        a = _PLAN[step]
        if a:
            return a
    return {{"farmer": ["PASS"], "hands": [], "market": []}}
'''


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("replay")
    ap.add_argument("seat", type=int, choices=[0, 1])
    ap.add_argument("outdir")
    args = ap.parse_args()

    d = json.loads(Path(args.replay).read_text())
    info = d["info"]
    team = info["TeamNames"][args.seat]
    plan = [st[args.seat].get("action") for st in d["steps"]]
    out = Path(args.outdir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "main.py").write_text(TEMPLATE.format(
        team=team, seat=args.seat, episode=info.get("EpisodeId"),
        seed=d.get("configuration", {}).get("seed"), plan=plan))
    meta = {
        "team": team,
        "seat": args.seat,
        "episode": info.get("EpisodeId"),
        "seed": d.get("configuration", {}).get("seed"),
        "both_teams": info["TeamNames"],
        "steps": len(plan),
        "path": str(out / "main.py"),
    }
    (out / "recorded-opponent.json").write_text(json.dumps(meta, indent=1))
    print(json.dumps(meta, indent=1))


if __name__ == "__main__":
    main()
