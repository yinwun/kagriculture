#!/usr/bin/env python
"""Re-simulate a recorded episode from its seed and both action streams.

Replay bookkeeping note: on engine 1.32.7 the entry at index t holds the state the
agent saw at step t and the action applied at step t was recorded at index t+1
(verified: shift=1 reproduces recorded rewards exactly, shift=0/-1 do not).

This is the "bank-reproduction gate" the community uses before any counterfactual
work: feed the recorded actions back into the official engine and check that the
game reproduces.  If the final banks match to the dollar and the observations
match step by step, then we hold a trustworthy *reconstruction* of every state
and of what each agent saw -- which is the prerequisite for every other probe
(opponent substitution, fork attribution, DAgger labelling).

Usage:
  python scripts/replay_reproduce.py data/top/episode-109149804-replay.json
  python scripts/replay_reproduce.py data/top/episode-*.json --quiet

Output per episode: seat names, recorded vs reproduced final money, the first step
where any tracked observation field diverges, and the number of divergent steps.
"""
import argparse
import glob
import json
import sys
from pathlib import Path

from kaggle_environments import make

TRACK = ("day", "step")


def seat_agent(actions, seat, shift=0):
    """Return the recorded action for this seat, indexed by observation['step'].

    `shift` absorbs the one-step offset between a replay entry's state and the
    action stored next to it.  Measured on 1.32.7 replays: the recorded action at
    index t+1 is the one the engine applies to the state recorded at index t, so
    shift=1 reproduces the final banks to the dollar; 0 and -1 do not.
    """

    def agent(obs):
        st = obs.get("step")
        if st is None:
            st = len(actions) - 1
        st = st + shift
        if 0 <= st < len(actions):
            a = actions[st][seat]
            return a if isinstance(a, dict) else {}
        return {}

    return agent


def summarise(obs, p):
    """Compact state fingerprint used to detect the first divergence."""
    farm = obs["farms"][p]
    return (
        obs.get("day"), round(float(farm.get("money", 0))),
        tuple(sorted((k, v) for k, v in obs["market"]["prices"].items() if v)),
        len(farm.get("hands") or []),
        round(float(obs["market"]["inventory"].get("WHEAT", 0))),
    )


def reproduce(path, verbose=True, shift=1):
    d = json.loads(Path(path).read_text())
    steps = d["steps"]
    names = d.get("info", {}).get("TeamNames", ["p0", "p1"])
    seeds = []
    seed = d.get("info", {}).get("seed")
    cfg = dict(d.get("configuration") or {})
    cfg["seed"] = None  # engine reads env.info['seed']; keep config scrubbed

    actions = [[steps[t][p].get("action") or {} for p in (0, 1)] for t in range(len(steps))]

    env = make("kaggriculture", configuration=cfg, debug=True)
    env.info["seed"] = seed
    env.run([seat_agent(actions, 0, shift), seat_agent(actions, 1, shift)])

    out = {"path": Path(path).name, "seed": seed, "teams": names,
           "recorded": [round(float(r)) for r in d["rewards"]],
           "reproduced": [round(float(env.steps[-1][p]["reward"] or 0)) for p in (0, 1)],
           "first_divergence": None, "divergent_steps": 0, "status": list(env.state)}
    for t in range(min(len(steps), len(env.steps))):
        for p in (0, 1):
            ro = steps[t][p].get("observation")
            eo = env.steps[t][p].get("observation")
            if not ro or not eo:
                continue
            if summarise(ro, p) != summarise(eo, p):
                out["divergent_steps"] += 1
                if out["first_divergence"] is None:
                    out["first_divergence"] = (t, p, summarise(ro, p), summarise(eo, p))
    out["money_match"] = out["recorded"] == out["reproduced"]
    if verbose:
        ok = "OK " if out["money_match"] and not out["divergent_steps"] else "DIFF"
        print(f"[{ok}] {out['path']} seed={seed}")
        print(f"      teams      : {names}")
        print(f"      recorded   : {out['recorded']}")
        print(f"      reproduced : {out['reproduced']}")
        print(f"      first divergence at step {out['first_divergence'][0] if out['first_divergence'] else '-'}"
              f"  (divergent steps: {out['divergent_steps']})")
        if out["first_divergence"]:
            t, p, a, b = out["first_divergence"]
            print(f"        seat {p} step {t}\n          replay: {a}\n          engine: {b}")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("paths", nargs="+")
    ap.add_argument("--quiet", action="store_true")
    ap.add_argument("--shift", type=int, default=1)
    args = ap.parse_args()
    paths = []
    for p in args.paths:
        paths.extend(sorted(glob.glob(p)))
    results = [reproduce(p, verbose=not args.quiet, shift=args.shift) for p in paths]
    ok = sum(1 for r in results if r["money_match"] and not r["divergent_steps"])
    print(f"\n{ok}/{len(results)} episodes reproduced exactly")
    for r in results:
        if not (r["money_match"] and not r["divergent_steps"]):
            print(f"   mismatch: {r['path']} rec={r['recorded']} rep={r['reproduced']} "
                  f"first_div={r['first_divergence'][0] if r['first_divergence'] else '-'}")
    return 0 if ok == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
