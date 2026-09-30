#!/usr/bin/env python
"""Opponent-substitution probe: is a top agent's plan opponent-conditioned?

The cleanest way to test "template vs opponent-conditioned policy" with replays
only -- no access to the agent's code -- is to keep the target's recorded action
stream and replace its *opponent* with a different agent on the same seed, then
watch which channel diverges.

  control  : both recorded streams            (reproduces the episode exactly)
  probe    : target stream unchanged, rival = our scripted agent
  probe-alt: target stream unchanged, rival = a recorded stream from another game

We then classify every divergent step into the two channels the community's x-ray
uses:
  FARM  channel: the target's own tiles/animals/money/hands
  MARKET channel: prices / market inventory

Reading:
  * farm diverges immediately  -> the target's *production* plan reacts to the rival
  * farm stays identical while only MARKET diverges -> the target is an own-state
    template; the rival only reaches it through prices (world read, not rival read)
  * nothing diverges -> the target is a pure open-loop tape

Usage:
  python scripts/substitute_opponent.py data/top/episode-109149804-replay.json
  python scripts/substitute_opponent.py 'data/top/episode-*.json' --ours data/tapeopt/rgcs/main.py
"""
import argparse
import glob
import json
from pathlib import Path

from kaggle_environments import make

MOVE = {"NORTH", "SOUTH", "EAST", "WEST"}


def seat_agent(actions, seat, shift=1):
    def agent(obs):
        st = obs.get("step")
        idx = (st if st is not None else len(actions) - 1) + shift
        if 0 <= idx < len(actions):
            a = actions[idx][seat]
            return a if isinstance(a, dict) else {}
        return {}

    return agent


def load_ours(path):
    ns = {"__name__": "opp_mod"}
    exec(compile(Path(path).read_text(), str(path), "exec"), ns)
    return ns["agent"]


def farm_key(obs, p):
    tiles = obs["farms"][p]["tiles"]
    flat = []
    for row in tiles:
        for cell in row:
            if not isinstance(cell, dict):
                flat.append(cell)
            elif cell.get("kind") == "PLANT":
                flat.append((cell["crop"], cell.get("yield_units"),
                             cell.get("watered_today"), cell.get("fertilized_until_day")))
            elif cell.get("animal"):
                flat.append((cell["animal"], cell.get("fed_today"), cell.get("cared_today")))
            else:
                flat.append(cell.get("kind"))
    return (round(float(obs["farms"][p]["money"])), tuple(flat),
            len(obs["farms"][p].get("hands") or []),
            tuple(sorted(obs["private"]["shed"].items())))


def market_key(obs):
    return (tuple(sorted(obs["market"]["prices"].items())),
            tuple(sorted(obs["market"]["inventory"].items())))


def run(replay, target_seat, rival, shift=1, steps=None):
    d = json.loads(Path(replay).read_text())
    n = len(d["steps"])
    actions = [[d["steps"][t][p].get("action") or {} for p in (0, 1)] for t in range(n)]
    cfg = dict(d.get("configuration") or {})
    cfg["seed"] = None
    if steps:
        cfg["episodeSteps"] = steps
    env = make("kaggriculture", configuration=cfg, debug=True)
    env.info["seed"] = d["info"]["seed"]
    agents = [None, None]
    agents[target_seat] = seat_agent(actions, target_seat, shift)
    q = 1 - target_seat
    if rival == "recorded":
        agents[q] = seat_agent(actions, q, shift)
    elif isinstance(rival, str) and rival.endswith(".py"):
        agents[q] = load_ours(rival)
    else:  # another replay's stream, same seat
        o = json.loads(Path(rival).read_text())
        oa = [[o["steps"][t][p].get("action") or {} for p in (0, 1)] for t in range(len(o["steps"]))]
        agents[q] = seat_agent(oa, q, shift)
    env.run(agents)
    return env, d, actions


def effect_profile(env, target_seat, actions, shift=1):
    """How long does a recorded stream keep 'landing' once the world moves?

    For every step whose recorded action contained a non-move command, check whether
    the target's own private state changed at all.  The first step where a non-move
    command changes nothing is the point where the stream has gone stale (it asked
    for a plant/water/harvest the engine refused), and the overall rate measures how
    state-coupled the underlying policy is.
    """
    zero_steps = []
    live = 0
    total = 0
    prev = None
    for t in range(len(env.steps)):
        o = env.steps[t][target_seat].get("observation")
        if not o:
            continue
        cur = farm_key(o, target_seat)
        act = actions[min(t + shift, len(actions) - 1)][target_seat]
        cmds = [act.get("farmer") or []] + list(act.get("hands") or [])
        nonmove = any(isinstance(c, list) and c and c[0] not in MOVE for c in cmds)
        if prev is not None and nonmove:
            total += 1
            if cur != prev:
                live += 1
            else:
                zero_steps.append(t)
        prev = cur
    return {"nonmove_steps": total, "live_steps": live,
            "live_rate": live / total if total else None,
            "first_zero_effect": zero_steps[0] if zero_steps else None,
            "zero_effect": len(zero_steps)}


def compare(base_env, probe_env, target_seat, n):
    farm_div = market_div = both = 0
    first_farm = first_market = None
    for t in range(min(n, len(base_env.steps), len(probe_env.steps))):
        b = base_env.steps[t][target_seat].get("observation")
        p = probe_env.steps[t][target_seat].get("observation")
        if not b or not p:
            continue
        fd = farm_key(b, target_seat) != farm_key(p, target_seat)
        md = market_key(b) != market_key(p)
        if fd:
            farm_div += 1
            if first_farm is None:
                first_farm = t
        if md:
            market_div += 1
            if first_market is None:
                first_market = t
        if fd and md:
            both += 1
    return {"farm_div": farm_div, "market_div": market_div, "both": both,
            "first_farm": first_farm, "first_market": first_market}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("paths", nargs="+")
    ap.add_argument("--ours", default="data/tapeopt/rgcs/main.py")
    ap.add_argument("--seat-team", default=None, help="only probe replays where this team is present")
    args = ap.parse_args()
    paths = []
    for p in args.paths:
        paths.extend(sorted(glob.glob(p)))

    print(f"{'episode':10s} {'target':16s} {'probe rival':22s} {'1stFARM':>8s} {'1stMKT':>7s} "
          f"{'farmDiv':>8s} {'mktDiv':>7s}  money base->probe")
    for path in paths:
        d0 = json.loads(Path(path).read_text())
        teams = d0["info"]["TeamNames"]
        for seat in (0, 1):
            if args.seat_team and teams[seat] != args.seat_team:
                continue
            base, d, acts = run(path, seat, "recorded")
            n = len(d["steps"])
            exact = [round(float(base.steps[-1][p]["reward"] or 0)) for p in (0, 1)]
            rec = [round(float(r)) for r in d["rewards"]]
            assert exact == rec, f"control run failed for {path} seat {seat}: {exact} != {rec}"
            for label, rival in (("ours:" + Path(args.ours).parent.name, args.ours),):
                probe, _, _ = run(path, seat, rival)
                c = compare(base, probe, seat, n)
                pm = round(float(probe.steps[-1][seat]["reward"] or 0))
                bm = round(float(base.steps[-1][seat]["reward"] or 0))
                e = effect_profile(probe, seat, acts)
                print(f"{d['info']['EpisodeId']:10d} {teams[seat]:16s} {label:22s} "
                      f"{str(c['first_farm']):>8s} {str(c['first_market']):>7s} "
                      f"{c['farm_div']:8d} {c['market_div']:7d}  {bm} -> {pm}   "
                      f"stream lands {e['live_rate']*100 if e['live_rate'] is not None else float('nan'):.1f}% "
                      f"(first dead step {e['first_zero_effect']})")
    print("\nlegend: 'stream lands' = share of steps with a non-move command that still changed"
          "\n        farmDiv counts steps of FARM-channel divergence out of 720.")


if __name__ == "__main__":
    main()
