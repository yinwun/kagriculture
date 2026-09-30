#!/usr/bin/env python
"""S1.1 reference traces: input side, output side and derived quantities, per step.

For one agent on one seed this records, for the traced seat:

  input   step, money, market inventory/prices, town shops, shed, seeds, per-unit
          inventories, and a compact per-tile summary (kind/crop/animal/watered/
          unfeed/yield/placed_day/fertilised-until) of BOTH farms;
  output  the full action (farmer/hands/market) and the post-application state,
          obtained by replaying the action with the engine's own
          `_apply_unit_action` on a copy (the same instrument `race_trace.py` uses);
  derived per-unit positions and hand cargo; per-step executed market units and the
          net cash they produce, recomputed with `scripts/lockstep.py`.

Acceptance (S1.1): the lockstep recomputation of the market's cash must match the
engine's money for the traced seat within 1 coin per game.  Task 1 already showed this
replay is exact on real games (0 mismatches over 2,872 player-steps); this run changes
only the input source.

Usage:
  .venv/bin/python scripts/trace_ref.py --agent data/forward/wool_drain1_outerprem/main.py \
      --seeds 9000-9011 --procs 6
"""
from __future__ import annotations

import argparse
import copy
import json
import multiprocessing as mp
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import lockstep  # noqa: E402

CHAMPION = str(ROOT / "data" / "tapeopt" / "rgcs" / "main.py")
STACK = str(ROOT / "data" / "forward" / "wool_drain1_outerprem" / "main.py")
OUT = ROOT / "data" / "trace"


def _load(path):
    ns = {"__name__": "trace_mod"}
    exec(compile(Path(path).read_text(), str(path), "exec"), ns)
    return ns["agent"]


def _tiles(tiles):
    """Compact non-empty tiles: [x, y, kind, crop/animal, flagbits, yield, age]."""
    out = []
    for y, row in enumerate(tiles):
        for x, t in enumerate(row):
            if t is None:
                continue
            if t == "LOCKED":
                out.append([x, y, "L"])
                continue
            kind = t.get("kind")
            extra = t.get("crop") or t.get("animal") or ""
            flags = 0
            if t.get("watered_today"):
                flags |= 1
            if t.get("fed_today"):
                flags |= 2
            if t.get("cared_today"):
                flags |= 4
            if t.get("fertilizer_available"):
                flags |= 8
            out.append([x, y, kind, extra, flags, int(t.get("yield_units", 0) or 0),
                        int(t.get("placed_day", t.get("planted_day", -1)) or -1)])
    return out


def record(agent_path, seed, opponent=CHAMPION, seat=0):
    from kaggle_environments import make
    from kaggle_environments.envs.kaggriculture import kaggriculture as eng

    agent = _load(agent_path)
    opp = _load(opponent)
    steps = []
    money0 = {"v": None}
    rival = {}

    def wrap_opp(obs, *a, **k):
        """Record the rival's action too: the lockstep replay needs BOTH market lists,
        because paired units raise the inventory (and so cut the price) twice as fast.
        Replaying our side alone over-prices the sales by ~2-4k per game (measured).
        """
        act = opp(obs) or {}
        board = len(obs.farms[1 - seat]["tiles"])
        priv = copy.deepcopy(obs.private)
        farm = copy.deepcopy(obs.farms[1 - seat])
        units = [act.get("farmer") or ["PASS"]] + list(act.get("hands") or [])
        for idx, ua in enumerate(units):
            eng._apply_unit_action(farm, priv, idx, ua, board, int(obs.day), 24, 100)
        rival[int(obs["step"])] = {
            "market": [list(o) for o in (act.get("market") or [])],
            "shed_mkt": {k: int(v) for k, v in dict(priv["shed"]).items()},
        }
        return act

    def wrap(obs, *a, **k):
        act = agent(obs) or {}
        s = int(obs["step"])
        board = len(obs.farms[seat]["tiles"])
        day = int(obs.day)
        priv_in = copy.deepcopy(obs.private)
        farm_in = copy.deepcopy(obs.farms[seat])
        if money0["v"] is None:
            money0["v"] = float(obs.farms[seat]["money"])
        # replay the unit actions to obtain the market-time shed and the post state
        units = [act.get("farmer") or ["PASS"]] + list(act.get("hands") or [])
        for idx, ua in enumerate(units):
            eng._apply_unit_action(farm_in, priv_in, idx, ua, board, day, 24, 100)
        shed_mkt = {k: int(v) for k, v in dict(priv_in["shed"]).items()}
        inv = {k: int(v) for k, v in dict(obs.market.inventory).items()}
        market = [list(o) for o in (act.get("market") or [])]
        steps.append({
            "step": s, "day": day, "hour": s % 24,
            "money": float(obs.farms[seat]["money"]),
            "inv": inv, "prices": {k: int(v) for k, v in dict(obs.market.prices).items()},
            "shops": list(obs.town["unlocked_shops"]),
            "shed": {k: int(v) for k, v in dict(obs.private.shed).items()},
            "seeds": {k: int(v) for k, v in dict(obs.private.seeds).items()},
            "invs": [{k: int(v) for k, v in dict(i2 or {}).items()}
                     for i2 in (obs.private.get("inventories") or [])],
            "mine_tiles": _tiles(obs.farms[seat]["tiles"]),
            "rival_tiles": _tiles(obs.farms[1 - seat]["tiles"]),
            "hires_today": int(obs.farms[seat].get("hires_today", 0)),
            "quadrants": len(list(obs.farms[seat].get("unlocked_quadrants") or [])),
            "farmer": list(obs.farms[seat]["farmer"]),
            "hands": [list(p2) for p2 in (obs.farms[seat].get("hands") or [])],
            "action": {"farmer": act.get("farmer"), "hands": list(act.get("hands") or []),
                       "market": market},
            "shed_mkt": shed_mkt,
            "post_shed": {k: int(v) for k, v in dict(priv_in["shed"]).items()},
            "post_invs": [{k: int(v) for k, v in dict(i2 or {}).items()}
                          for i2 in (priv_in.get("inventories") or [])],
        })
        return act

    env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": seed})
    env.run([wrap, wrap_opp] if seat == 0 else [wrap_opp, wrap])
    final_money = float(env.steps[-1][seat]["reward"] or 0)
    # The opponent is called after us in each step, so the two-sided lockstep replay has
    # to run AFTER the game, once every step's rival action is known.  Replaying our side
    # alone (or before the rival's list exists) over-prices the sales by ~2-4k a game.
    for rec in steps:
        st = rec["step"]
        other = rival.get(st, {"market": [], "shed_mkt": {}})
        res = lockstep.clear(
            rec["action"]["market"], other["market"], rec["inv"],
            (rec["shed_mkt"], other["shed_mkt"]),
            money=(rec["money"], 10 ** 9),
            hires_today=(int(rec.get("hires_today", 0)), 0),
            quadrants=(int(rec.get("quadrants", 1)), 1))
        rec["cash_step"] = res["rev"][0]
        rec["exec_units"] = {k: int(v) for k, v in res["shed"][0].items()}
        rec["rival_market"] = other["market"]
        rec["rival_shed_mkt"] = other["shed_mkt"]
    total_cash = sum(s["cash_step"] for s in steps)
    drift = final_money - float(money0["v"]) - total_cash
    d = OUT / f"{Path(agent_path).parent.name}-{seed}"
    d.mkdir(parents=True, exist_ok=True)
    (d / "trace.jsonl").write_text("\n".join(json.dumps(s) for s in steps))
    summary = {"agent": str(agent_path), "seed": seed, "seat": seat, "steps": len(steps),
               "money_start": money0["v"], "money_end": final_money,
               "lockstep_cash": total_cash, "drift": drift,
               "acceptance_ok": abs(drift) <= 1.0}
    (d / "summary.json").write_text(json.dumps(summary, indent=1))
    return summary


def _job(arg):
    path, opponent, seeds = arg
    return [record(path, s, opponent) for s in seeds]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--agent", default=STACK)
    ap.add_argument("--opponent", default=CHAMPION)
    ap.add_argument("--seeds", default="9000-9011")
    ap.add_argument("--procs", type=int, default=6)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    seeds = []
    for part in a.seeds.split(","):
        lo, _, hi = part.partition("-")
        seeds.extend(range(int(lo), int(hi) + 1) if hi else [int(lo)])
    chunks = [seeds[i::a.procs] for i in range(a.procs)]
    with mp.Pool(a.procs) as pool:
        res = pool.map(_job, [(a.agent, a.opponent, c) for c in chunks if c])
    rows = sorted((r for sub in res for r in sub), key=lambda r: r["seed"])
    ok = sum(1 for r in rows if r["acceptance_ok"])
    print(f"{a.agent}: {len(rows)} seeds traced, acceptance (|drift| <= 1 coin) "
          f"{ok}/{len(rows)}")
    for r in rows:
        print(f"   seed {r['seed']}: steps {r['steps']} money {r['money_start']:,.0f} -> "
              f"{r['money_end']:,.0f} lockstep {r['lockstep_cash']:,.0f} drift {r['drift']:+.2f}")
    if a.out:
        Path(a.out).write_text(json.dumps(rows, indent=1))
    return 0 if ok == len(rows) else 1


if __name__ == "__main__":
    sys.exit(main())
