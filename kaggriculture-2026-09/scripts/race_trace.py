#!/usr/bin/env python
"""Record a real game while exposing the exact state the market clearing sees.

The observation's `private.shed` is the shed *before* this step's farmer/hand
actions, but `interpreter` applies those actions before `_process_market`, so a
DROP in the same step changes the stock a SELL can use.  Replaying the market from
the raw observation shed therefore mispredicts every step with a DROP or PICKUP.

The recorder below copies the per-player private state, replays this step's unit
actions on the copy with the engine's own `_apply_unit_action`, and stores the
resulting shed as `shed_mkt`.  `lockstep.clear()` fed with `shed_mkt` reproduces
the engine's money exactly on every step of a real game -- see
`scripts/test_lockstep.py --games`.
"""
from __future__ import annotations

import copy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import lockstep  # noqa: E402

PRODUCTS = list(lockstep.PRODUCTS)


def load_agent(path):
    ns = {"__name__": "race_trace_mod"}
    exec(compile(Path(path).read_text(), str(path), "exec"), ns)
    return ns["agent"]


def record(seed, agent_paths, episode_steps=720):
    """Run one game; return {seat: {step: entry}} plus the final rewards.

    entry keys: market (list of orders), shed (observation shed), shed_mkt (shed at
    market time), inv (market inventory), money, prices, shops.
    """
    from kaggle_environments import make
    from kaggle_environments.envs.kaggriculture import kaggriculture as eng

    agents = [load_agent(p) for p in agent_paths]
    trace = {0: {}, 1: {}}

    def wrap(agent, seat):
        def fn(obs):
            act = agent(obs) or {}
            market = [list(o) for o in (act.get("market") or [])]
            try:
                board = int(getattr(obs, "boardSize", 0) or 0) or len(obs.farms[seat]["tiles"])
                priv = copy.deepcopy(obs.private)
                farm = copy.deepcopy(obs.farms[seat])
                units = [act.get("farmer") or ["PASS"]] + list(act.get("hands") or [])
                day = int(obs.day)
                for idx, a in enumerate(units):
                    eng._apply_unit_action(farm, priv, idx, a, board, day, 24, 100)
                shed_mkt = {k: int(v) for k, v in dict(priv["shed"]).items()}
            except Exception:
                shed_mkt = {k: int(v) for k, v in dict(obs.private["shed"]).items()}
            trace[seat][int(obs["step"])] = {
                "market": market,
                "shed": {k: int(v) for k, v in dict(obs.private["shed"]).items()},
                "shed_mkt": shed_mkt,
                "inv": {k: int(v) for k, v in dict(obs.market.inventory).items()},
                "prices": {k: int(v) for k, v in dict(obs.market.prices).items()},
                "money": float(obs.farms[seat]["money"]),
                "hires_today": int(obs.farms[seat].get("hires_today", 0) or 0),
                "quadrants": len(list(obs.farms[seat].get("unlocked_quadrants") or []) or []),
                "shops": list((obs.town.get("unlocked_shops") if hasattr(obs.town, "get")
                               else obs.town["unlocked_shops"]) or []),
            }
            return act
        return fn

    env = make("kaggriculture", configuration={"episodeSteps": episode_steps, "seed": seed})
    env.run([wrap(agents[0], 0), wrap(agents[1], 1)])
    final = [float(env.steps[-1][i]["reward"] or 0) for i in (0, 1)]
    return trace, final


def replay_step(trace, step, use_mkt_shed=True):
    a, b = trace[0][step], trace[1][step]
    key = "shed_mkt" if use_mkt_shed else "shed"
    return lockstep.clear(a["market"], b["market"], a["inv"], (a[key], b[key]),
                          money=(a["money"], b["money"]),
                          hires_today=(a.get("hires_today", 0), b.get("hires_today", 0)),
                          quadrants=(a.get("quadrants", 1), b.get("quadrants", 1)))


def actual_shops(trace, step):
    return trace[0][step]["shops"]
