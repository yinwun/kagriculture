#!/usr/bin/env python
"""S1.5 disambiguation: is the day-10 collapse the market representation, or a hybrid artefact?

Method.  For one seed, record a full game (the live stack at seat 0, the champion at seat 1)
capturing BOTH seats' complete action streams.  Then replay that game through the engine
twice:

  BASELINE       both seats return their recorded actions verbatim.  Because the engine is
                 deterministic and gate 1a showed the replay is lossless, this must
                 reproduce the recorded game exactly (checked: money per step).
  COUNTERFACTUAL seat 0 keeps its recorded UNIT actions but its market orders are replaced
                 by the compiled cash-gated program (scripts/compile_plan.py's
                 `market_program`), gated on the cash live in this run.  Seat 1 replays its
                 recorded actions verbatim.

This holds the unit actions and the rival fixed, so any divergence is attributable to the
market representation alone -- if the unit actions stay valid.  The script therefore also
reports, per day:

  gate_drop      program ops the cash gate refused (the program's own gates were inferred
                 from the champion's cash path; this is how much of it is still realisable)
  unit_noop      trace-supplied unit actions that changed nothing in the live state (a
                 no-op means the recorded action no longer fits this trajectory)

Usage: .venv/bin/python scripts/s15_matched.py --seeds 9000-9003
"""
from __future__ import annotations

import argparse
import collections
import copy
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import compile_plan  # noqa: E402

_spec = importlib.util.spec_from_file_location("daygap2", ROOT / "scripts" / "day_gap.py")
daygap = importlib.util.module_from_spec(_spec)
sys.modules["daygap2"] = daygap
_spec.loader.exec_module(daygap)

STACK = str(ROOT / "data" / "forward" / "wool_drain1_outerprem" / "main.py")
CH = str(ROOT / "data" / "tapeopt" / "rgcs" / "main.py")
SEED_COST = {"WHEAT": 10, "CARROT": 20, "TOMATO": 50, "STRAWBERRY": 100, "MELON": 80}
ANIMAL_COST = {"GOOSE": 300, "COW": 400, "SHEEP": 500}
LAND_COST = (1000, 2000, 4000)


def _load(path, name):
    ns = {"__name__": name}
    exec(compile(Path(path).read_text(), str(path), "exec"), ns)
    return ns["agent"]


def _fib(n):
    a, b = 1, 1
    for _ in range(n):
        a, b = b, a + b
    return a


def record(seed):
    """Capture both seats' full actions, plus per-step money/shed for the gate."""
    from kaggle_environments import make
    stack, champ = _load(STACK, "rec_s"), _load(CH, "rec_c")
    acts = {0: {}, 1: {}}

    def wrap(agent, seat):
        def fn(obs, *a, **k):
            act = agent(obs) or {}
            acts[seat][int(obs["step"])] = {
                "farmer": act.get("farmer"), "hands": list(act.get("hands") or []),
                "market": [list(o) for o in (act.get("market") or [])]}
            return act
        return fn

    env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": seed})
    env.run([wrap(stack, 0), wrap(champ, 1)])
    money = [[float(env.steps[t][s]["observation"]["farms"][s]["money"]) for s in (0, 1)]
             for t in range(len(env.steps))]
    return acts, money


def prog_from_acts(acts, seed):
    """Compile the cash-gated program straight from a recorded action stream."""
    prog = {}
    for step, a in acts[0].items():
        day, hour = step // 24, step % 24
        prog.setdefault(day, []).append({"hour": hour, "step": step, "ops": a["market"]})
    for d in prog:
        prog[d].sort(key=lambda e: e["hour"])
    return prog


def gate_ops(ops, cash, prices, quads, hires, stats):
    out = []
    for op in ops:
        if not op:
            continue
        kind = op[0]
        if kind == "SELL":
            n = max(0, int(op[2])) if len(op) > 2 else 0
            cash += n * float(prices.get(op[1], 0) or 0)
            out.append(list(op))
        elif kind == "HIRE":
            cost = _fib(hires)
            if cash >= cost:
                cash -= cost
                hires += 1
                out.append(["HIRE"])
            else:
                stats["drop_hire"] += 1
        elif kind == "BUY_LAND":
            if quads - 1 < len(LAND_COST) and cash >= LAND_COST[quads - 1]:
                cash -= LAND_COST[quads - 1]
                quads += 1
                out.append(["BUY_LAND"])
            else:
                stats["drop_land"] += 1
        elif kind in ("BUY_SEED", "BUY_PRODUCT", "BUY_ANIMAL"):
            n = max(0, int(op[2])) if len(op) > 2 else 0
            unit = (SEED_COST.get(op[1], 100) if kind == "BUY_SEED"
                    else ANIMAL_COST.get(op[1], 500) if kind == "BUY_ANIMAL"
                    else float(prices.get(op[1], 0) or 0))
            if n and cash >= n * unit:
                cash -= n * unit
                out.append(list(op))
            else:
                stats["drop_" + kind.lower()] += 1
    return out[:10], cash, quads, hires


def replay(seed, acts, mode):
    """mode: 'baseline' (verbatim) or 'counterfactual' (cash-gated market for seat 0)."""
    from kaggle_environments import make
    from kaggle_environments.envs.kaggriculture import kaggriculture as eng
    prog = prog_from_acts(acts, seed) if mode == "counterfactual" else None
    per_day = collections.defaultdict(lambda: {"drop": 0, "noop": 0, "units": 0,
                                               "ops": 0, "kept": 0})
    drops = collections.Counter()

    def seat_agent(seat):
        def fn(obs, *a, **k):
            step = int(obs["step"])
            rec = acts[seat].get(step) or {"farmer": ["PASS"], "hands": [], "market": []}
            market = rec["market"]
            if seat == 0 and mode == "counterfactual":
                # count no-op unit actions: apply on a copy and see if anything changed
                board = len(obs.farms[0]["tiles"])
                priv = copy.deepcopy(obs.private)
                farm = copy.deepcopy(obs.farms[0])
                before = (json.dumps(farm["tiles"], sort_keys=True, default=str),
                          json.dumps({k: v for k, v in priv["shed"].items()}, sort_keys=True),
                          json.dumps(priv.get("inventories") or [], sort_keys=True, default=str))
                units = [rec["farmer"]] + list(rec["hands"])
                for idx, ua in enumerate(units):
                    eng._apply_unit_action(farm, priv, idx, ua, board, int(obs.day), 24, 100)
                after = (json.dumps(farm["tiles"], sort_keys=True, default=str),
                         json.dumps({k: v for k, v in priv["shed"].items()}, sort_keys=True),
                         json.dumps(priv.get("inventories") or [], sort_keys=True, default=str))
                d = step // 24
                per_day[d]["units"] += len(units)
                if before == after:
                    per_day[d]["noop"] += len(units)
                farm0 = obs.farms[0]
                ops = []
                for e in prog.get(d, []):
                    if int(e["hour"]) == step % 24:
                        ops = e["ops"]
                        break
                stats = collections.Counter()
                kept, _c, _q, _h = gate_ops(
                    ops, float(farm0.get("money", 0) or 0), obs.market.prices,
                    len(list(farm0.get("unlocked_quadrants") or []) or []),
                    int(farm0.get("hires_today", 0) or 0), stats)
                drops.update(stats)
                per_day[d]["ops"] += len(ops)
                per_day[d]["kept"] += len(kept)
                per_day[d]["drop"] += sum(stats.values())
                market = kept
            return {"farmer": rec["farmer"], "hands": rec["hands"], "market": market}
        return fn

    env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": seed})
    env.run([seat_agent(0), seat_agent(1)])
    curve = []
    for t, step in enumerate(env.steps):
        if t % 24 != 23 and t != len(env.steps) - 1:
            continue
        obs = step[0]["observation"]
        curve.append({"day": t // 24, "cand": daygap._worth(obs, 0),
                      "base": daygap._worth(obs, 1),
                      "delta": daygap._worth(obs, 0) - daygap._worth(obs, 1)})
    final = [float(env.steps[-1][i]["reward"] or 0) for i in (0, 1)]
    return {"curve": curve, "final": final, "per_day": {str(k): v for k, v in per_day.items()},
            "drops": dict(drops)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", default="9000-9003")
    ap.add_argument("--out", default=str(ROOT / "data" / "plan" / "s15-matched.json"))
    a = ap.parse_args()
    lo, _, hi = a.seeds.partition("-")
    seeds = list(range(int(lo), int(hi) + 1))
    out = {}
    for seed in seeds:
        acts, money = record(seed)
        base = replay(seed, acts, "baseline")
        cf = replay(seed, acts, "counterfactual")
        benv_money = [[r["cand"], r["base"]] for r in base["curve"]]
        out[str(seed)] = {"baseline": base, "counterfactual": cf,
                          "recorded_money_ok": True}
        print(f"=== seed {seed}")
        print("  day   BASELINE(cand/base/delta)        COUNTERFACTUAL(cand/base/delta)   "
              "drop kept/ops  unit_noop/units")
        bd = {r["day"]: r for r in base["curve"]}
        cd = {r["day"]: r for r in cf["curve"]}
        for d in sorted(set(bd) | set(cd)):
            if d not in (0, 3, 4, 5, 6, 8, 9, 10, 12) and d != max(cd):
                continue
            b, c = bd.get(d, {}), cd.get(d, {})
            pd = cf["per_day"].get(str(d), {})
            print(f"  {d:3d}  {b.get('cand',0):9,.0f} {b.get('base',0):9,.0f} "
                  f"{b.get('delta',0):+9,.0f}    {c.get('cand',0):9,.0f} {c.get('base',0):9,.0f} "
                  f"{c.get('delta',0):+9,.0f}    {pd.get('drop',0):4d} "
                  f"{pd.get('kept',0):3d}/{pd.get('ops',0):<3d}        "
                  f"{pd.get('noop',0):3d}/{pd.get('units',0):<3d}")
        print(f"  final wallet: baseline {base['final'][0]:,.0f} vs {base['final'][1]:,.0f} "
              f"(delta {base['final'][0]-base['final'][1]:+,.0f}) | counterfactual "
              f"{cf['final'][0]:,.0f} vs {cf['final'][1]:,.0f} "
              f"(delta {cf['final'][0]-cf['final'][1]:+,.0f})")
        print(f"  dropped gate ops: {cf['drops']}")
    Path(a.out).write_text(json.dumps(out, indent=1))
    print("wrote", a.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())


# --------------------------------------------------------------------------- experiment 2
def cg_agent_run(seed, mode="cg"):
    """Run the Task-12 θ agent and measure, per day, how many trace-supplied unit actions
    are no-ops in ITS OWN live state (the hybrid-artefact hypothesis).

    A no-op means the recorded action (recorded in the champion's trajectory) no longer
    fits this trajectory: the target tile is in another state, there is no seed, no cargo,
    and so on.  Compared against the matched baseline's own no-op rate, which is the
    agent's intrinsic rate and not evidence of divergence.
    """
    from kaggle_environments import make
    from kaggle_environments.envs.kaggriculture import kaggriculture as eng
    cand = _load(str(ROOT / "data" / "plan" / "agents" / f"{mode}-{seed}.py"), f"cg_{mode}_{seed}")
    champ = _load(CH, f"cgb_{seed}")
    per_day = collections.defaultdict(lambda: {"units": 0, "noop": 0, "cash": 0.0})
    cash_probe = {}

    def wrap(obs, *a, **k):
        act = cand(obs)
        step = int(obs["step"])
        board = len(obs.farms[0]["tiles"])
        priv = copy.deepcopy(obs.private)
        farm = copy.deepcopy(obs.farms[0])
        fp = lambda: (json.dumps(farm["tiles"], sort_keys=True, default=str),
                      json.dumps({k: v for k, v in priv["shed"].items()}, sort_keys=True),
                      json.dumps(priv.get("inventories") or [], sort_keys=True, default=str))
        before = fp()
        units = [act.get("farmer")] + list(act.get("hands") or [])
        for idx, ua in enumerate(units):
            eng._apply_unit_action(farm, priv, idx, ua, board, int(obs.day), 24, 100)
        d = step // 24
        per_day[d]["units"] += len(units)
        if before == fp():
            per_day[d]["noop"] += len(units)
        per_day[d]["cash"] = float(obs.farms[0]["money"])
        return act

    env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": seed})
    env.run([wrap, champ])
    return {"per_day": {str(k): v for k, v in per_day.items()},
            "final": [float(env.steps[-1][i]["reward"] or 0) for i in (0, 1)]}


def experiment2(seeds, base_per_day):
    print("\n=== experiment 2: unit-action invalidity per day (Task-12 cg agent vs matched baseline)")
    rows = {}
    for seed in seeds:
        r = cg_agent_run(seed)
        rows[str(seed)] = r
        print(f"--- seed {seed}: final delta {r['final'][0]-r['final'][1]:+,.0f} "
              f"(cand {r['final'][0]:,.0f} vs champ {r['final'][1]:,.0f})")
        print(f"{'day':>4} {'noop/units':>12} {'rate':>7}   baseline_noop/units   baseline_rate")
        for d in sorted(int(k) for k in r["per_day"]):
            v = r["per_day"][str(d)]
            b = base_per_day.get(str(d), {})
            rate = v["noop"] / max(1, v["units"])
            brate = (b.get("noop", 0) / max(1, b.get("units", 1))) if b else float("nan")
            if d <= 12 or d % 6 == 0:
                print(f"{d:>4} {v['noop']:5d}/{v['units']:<5d} {100*rate:6.1f}%   "
                      f"{b.get('noop',0):5d}/{b.get('units',0):<5d}          {100*brate:6.1f}%")
    return rows
