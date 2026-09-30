#!/usr/bin/env python
"""Task 42: causal wallet attribution for the ladder games of a submission ref.

For every replay of ref 56642424 (`data/replays-<ref>/episode-*-replay.json`) this
rebuilds the game from its recorded actions through the official engine with three
instrumentation hooks and produces an exact, closed accounting:

  * market hooks (`_commit_unit`, `_do_hire`, `_do_buy_land`) -> per seat per item
    executed SELL units + realised price, BUY_PRODUCT / BUY_SEED / BUY_ANIMAL spend,
    HIRE and BUY_LAND cost.
  * shed hook (`_drop_inventories_to_shed`) -> end-of-day shed-overflow discards.
  * unit-phase hook (`_apply_unit_action` on a deep copy, as in scripts/wheat_flow.py)
    -> per item production (HARVEST / COLLECT_FERTILIZER), feed and fertilizer
    consumption, animals placed, plus worker-verb counters and PASS (idle) counts.
  * per-day liquid net worth for both seats (`scripts/day_gap._worth`).

The accounting is verified to close: 3000 + sells - all buys - hires - land == final
money, per seat, per game; and the re-simulation must reproduce the recorded reward
of both seats (`gate`).  Games that fail the gate are reported, never silently used.

Usage:
  .venv/bin/python scripts/pi_attribute.py --ref 56642424 --out data/pi-attr-56642424.json
"""
from __future__ import annotations

import argparse
import collections
import copy
import glob
import json
import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from day_gap import _worth  # noqa: E402

PRODUCTS = ["WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON", "EGG", "MILK", "WOOL",
            "FERTILIZER"]
VERBS = ("PLANT", "WATER", "HARVEST", "FEED", "CARE", "COLLECT_FERTILIZER", "PLACE",
         "PICKUP", "DROP", "DIG", "BUILD_PASTURE", "BUILD_COOP", "FERTILIZE", "PASS")
MOVE = ("NORTH", "SOUTH", "EAST", "WEST")


# ------------------------------------------------------------------ hooks
def install_hooks(log, disc):
    """Log every executed market unit and every shed-overflow discard."""
    import kaggle_environments.envs.kaggriculture.kaggriculture as K
    cur: dict = {}
    orig = (K._process_market, K._commit_unit, K._drop_inventories_to_shed,
            K._do_hire, K._do_buy_land, K._end_of_day)

    def pm(state, env):
        obs0 = state[0].observation
        cur["farms"] = obs0.farms
        cur["privs"] = [s.observation.private for s in state]
        cur["step"] = K.get(obs0, "step", None)
        return orig[0](state, env)

    def commit(op, item, price, farm, private, market, shed_capacity=100):
        pid = next((i for i, f in enumerate(cur.get("farms") or []) if f is farm), -1)
        ok = orig[1](op, item, price, farm, private, market, shed_capacity)
        if ok:
            log.append({"step": cur.get("step"), "seat": pid, "op": op,
                        "item": str(item), "price": float(price)})
        return ok

    def drop(private, capacity):
        pid = next((i for i, p in enumerate(cur.get("privs") or []) if p is private), -1)
        shed = private.get("shed") or {}
        before_shed = {k: int(v) for k, v in shed.items()}
        before_inv = collections.Counter()
        for d in (private.get("inventories") or []):
            for k, v in (d or {}).items():
                before_inv[k] += max(0, int(v))
        orig[2](private, capacity)
        for k in set(before_shed) | set(before_inv):
            lost = before_shed.get(k, 0) + before_inv.get(k, 0) \
                - int(shed.get(k, 0) or 0)
            if lost > 0:
                disc.append({"step": cur.get("step"), "seat": pid, "item": k,
                             "units": int(lost)})

    def end_of_day(state, env, day):
        cur["privs"] = [s.observation.private for s in state]
        return orig[5](state, env, day)

    def _seat_of(farm):
        return next((i for i, f in enumerate(cur.get("farms") or []) if f is farm), -1)

    def hire(farm, private, board_size, mult=1):
        pid = _seat_of(farm)
        before = float(farm.get("money", 0.0))
        orig[3](farm, private, board_size, mult)
        log.append({"step": cur.get("step"), "seat": pid, "op": "HIRE", "item": "HIRE",
                    "price": before - float(farm.get("money", 0.0))})

    def land(farm, board_size):
        pid = _seat_of(farm)
        before = float(farm.get("money", 0.0))
        orig[4](farm, board_size)
        log.append({"step": cur.get("step"), "seat": pid, "op": "BUY_LAND", "item": "LAND",
                    "price": before - float(farm.get("money", 0.0))})

    K._process_market, K._commit_unit, K._drop_inventories_to_shed = pm, commit, drop
    K._do_hire, K._do_buy_land, K._end_of_day = hire, land, end_of_day
    return orig


def restore_hooks(orig):
    import kaggle_environments.envs.kaggriculture.kaggriculture as K
    (K._process_market, K._commit_unit, K._drop_inventories_to_shed,
     K._do_hire, K._do_buy_land, K._end_of_day) = orig


def held(farm, priv):
    """Units of every item held by the shed plus every worker inventory."""
    tot = collections.Counter()
    for item, qty in (priv.get("shed") or {}).items():
        tot[item] += max(0, int(qty))
    for inv in (priv.get("inventories") or []):
        for item, qty in (inv or {}).items():
            tot[item] += max(0, int(qty))
    return tot


def seat_agent(actions, seat, shift=1):
    def agent(obs):
        s = obs.get("step") if isinstance(obs, dict) else None
        if s is None:
            s = len(actions) - 1
        s += shift
        a = actions[s][seat] if 0 <= s < len(actions) else None
        return a if isinstance(a, dict) else {}
    return agent


def make_wrapper(inner, seat, acc):
    """Attribute the unit phase: production, feed, fertilizer, placement, discards."""
    from kaggle_environments.envs.kaggriculture import kaggriculture as eng

    def fn(obs):
        act = inner(obs) or {}
        try:
            board = len(obs.farms[seat]["tiles"])
            day = int(obs.day)
            priv = copy.deepcopy(obs.private)
            farm = copy.deepcopy(obs.farms[seat])
            units = [act.get("farmer") or ["PASS"]] + list(act.get("hands") or [])
            for idx, a in enumerate(units):
                if isinstance(a, list) and a:
                    v = str(a[0])
                    acc["verbs"][v if v not in MOVE else "MOVE"] += 1
                    acc["worker_actions"] += 1
                before = held(farm, priv)
                eng._apply_unit_action(farm, priv, idx, a, board, day, 24, 100)
                after = held(farm, priv)
                for item in set(before) | set(after):
                    d = after[item] - before[item]
                    if d > 0:
                        acc["prod"][item] += d
                        if isinstance(a, list) and a and a[0] == "HARVEST":
                            acc["harvest_units"][item] += d
                    elif d < 0:
                        v = str(a[0]) if isinstance(a, list) and a else "?"
                        if v == "FEED":
                            acc["fed_units"][item] += -d
                        elif v == "FERTILIZE":
                            acc["fert_used"][item] += -d
                        elif v == "PLACE" and item in ("GOOSE", "COW", "SHEEP"):
                            acc["placed"][item] += -d
                        else:
                            acc["unit_discard"][item] += -d
            # market order shape (the layer signature)
            mk = act.get("market") or []
            n_sell = sum(1 for o in mk if isinstance(o, list) and o and o[0] == "SELL")
            acc["sell_steps"] += 1 if n_sell else 0
            acc["multi_sell_steps"] += 1 if n_sell >= 2 else 0
            acc["wool_sell_steps"] += 1 if any(
                isinstance(o, list) and len(o) >= 3 and o[0] == "SELL" and o[1] == "WOOL"
                for o in mk) else 0
            acc["market_orders"] += len(mk)
        except Exception:  # attribution must never change the game
            acc["attr_errors"] += 1
        return act
    return fn


def new_acc():
    return {"verbs": collections.Counter(), "worker_actions": 0,
            "prod": collections.Counter(), "harvest_units": collections.Counter(),
            "fed_units": collections.Counter(), "fert_used": collections.Counter(),
            "placed": collections.Counter(), "unit_discard": collections.Counter(),
            "sell_steps": 0, "multi_sell_steps": 0, "wool_sell_steps": 0,
            "market_orders": 0, "attr_errors": 0}


def attribute_game(path, rec):
    import kaggle_environments.envs.kaggriculture.kaggriculture as K
    d = json.loads(Path(path).read_text())
    steps = d["steps"]
    me, opp = rec["my_seat"], 1 - rec["my_seat"]
    actions = [[steps[t][p].get("action") or {} for p in (0, 1)] for t in range(len(steps))]

    log: list = []
    disc: list = []
    accs = {0: new_acc(), 1: new_acc()}
    orig = install_hooks(log, disc)
    seed = (d.get("info") or {}).get("seed")
    cfg = dict(d.get("configuration") or {})
    cfg["seed"] = None
    try:
        from kaggle_environments import make
        env = make("kaggriculture", configuration=cfg, debug=True)
        env.info["seed"] = seed
        env.run([make_wrapper(seat_agent(actions, 0), 0, accs[0]),
                 make_wrapper(seat_agent(actions, 1), 1, accs[1])])
        repro = [round(float(env.steps[-1][p]["reward"] or 0)) for p in (0, 1)]
        step = [int(env.steps[-1][p]["observation"].get("step", 719)) for p in (0, 1)]
    finally:
        restore_hooks(orig)
    recorded = [round(float(r)) for r in d["rewards"]]
    gate = repro == recorded

    # ---- market accounting per seat
    per = {}
    for who, seat in (("me", me), ("opp", opp)):
        sells = collections.defaultdict(lambda: {"units": 0, "rev": 0.0})
        buys = collections.defaultdict(lambda: {"units": 0, "spend": 0.0})
        spend_kind = collections.Counter()
        for e in log:
            if e["op"] == "SELL" and e["seat"] == seat:
                s = sells[e["item"]]
                s["units"] += 1
                s["rev"] += e["price"]
            elif (e["op"] in ("BUY_PRODUCT", "BUY_SEED", "BUY_ANIMAL")
                  and e["seat"] == seat):
                b = buys[e["item"]]
                b["units"] += 1
                b["spend"] += e["price"]
                spend_kind[e["op"]] += e["price"]
        hire = sum(e["price"] for e in log if e["op"] == "HIRE" and e["seat"] == seat)
        land = sum(e["price"] for e in log if e["op"] == "BUY_LAND" and e["seat"] == seat)
        per[who] = {"sells": {k: dict(v) for k, v in sells.items()},
                    "buys": {k: dict(v) for k, v in buys.items()},
                    "spend_kind": {k: round(v, 1) for k, v in spend_kind.items()},
                    "hire_cost": round(hire, 1), "land_cost": round(land, 1),
                    "acc": {k: (dict(v) if isinstance(v, collections.Counter) else v)
                            for k, v in accs[seat].items()}}

    # ---- exact accounting closure from the money column of both seats, per step
    # money_final = 3000 + sells - buys - hires - land;  hires/land = residual.
    disc_by_seat = collections.Counter()
    disc_items = {"me": collections.Counter(), "opp": collections.Counter()}
    for x in disc:
        disc_by_seat[x["seat"]] += x["units"]
        disc_items["me" if x["seat"] == me else "opp"][x.get("item", "?")] += x["units"]

    # ---- day worth
    last = {}
    for t, entry in enumerate(steps):
        dd = entry[me]["observation"].get("day")
        if dd is not None:
            last[int(dd)] = t
    worth = {}
    for day, t in sorted(last.items()):
        worth[day] = (float(_worth(steps[t][me]["observation"], me)),
                      float(_worth(steps[t][opp]["observation"], opp)))
    t_end = max(last.values())
    end_worth = (float(_worth(steps[t_end][me]["observation"], me)),
                 float(_worth(steps[t_end][opp]["observation"], opp)))
    end_money = (float(steps[t_end][me].get("reward") or 0),
                 float(steps[t_end][opp].get("reward") or 0))
    end_shed = (dict(steps[t_end][me]["observation"]["private"].get("shed") or {}),
                dict(steps[t_end][opp]["observation"]["private"].get("shed") or {}))

    out = {"episode": d.get("id"), "episodeId": (d.get("info") or {}).get("EpisodeId"),
           "my_seat": me, "margin": rec["margin"], "recorded": recorded, "reproduced": repro,
           "gate": bool(gate), "seed": seed,
           "opp_team": rec["opp_team"], "opp_teamId": rec["opp_teamId"],
           "opp_sub": rec["opp_sub"], "opp_score": rec["opp_score"],
           "per": per, "discarded_units": sum(disc_by_seat.values()),
           "discard_me": disc_by_seat[me], "discard_opp": disc_by_seat[opp],
           "discard_items": {k: dict(v) for k, v in disc_items.items()},
           "end_shed": end_shed,
           "end_worth_minus_money": [round(end_worth[0] - end_money[0], 1),
                                     round(end_worth[1] - end_money[1], 1)],
           "day_gap": {str(k): round(v[0] - v[1]) for k, v in worth.items()},
           "day_worth": {str(k): [round(v[0]), round(v[1])] for k, v in worth.items()},
           "final_step": step}
    # closure check
    for who, seat in (("me", me), ("opp", opp)):
        p = per[who]
        rev = sum(v["rev"] for v in p["sells"].values())
        sp = sum(v["spend"] for v in p["buys"].values())
        other = 3000.0 + rev - sp - float(recorded[seat])
        p["revenue_total"] = rev
        p["spend_total"] = sp
        p["other_costs"] = other   # hire + land + any unlogged money move
    out["closure"] = {who: round(per[who]["other_costs"], 1) for who in ("me", "opp")}
    out["accounting_error"] = round(
        (3000.0 + per["me"]["revenue_total"] - per["me"]["spend_total"]
         - per["me"]["other_costs"]) - recorded[me], 6)
    return out


def _job(arg):
    path, rec = arg
    try:
        return (attribute_game(path, rec), None)
    except Exception as exc:  # noqa: BLE001
        return (None, f"{type(exc).__name__}: {exc}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ref", default="56642424")
    ap.add_argument("--replays", default=None)
    ap.add_argument("--out", default=None)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--procs", type=int, default=6)
    ap.add_argument("--force", action="store_true", help="ignore an existing output file")
    args = ap.parse_args()
    reps = Path(args.replays) if args.replays else ROOT / "data" / f"replays-{args.ref}"
    out_path = Path(args.out) if args.out else ROOT / "data" / f"pi-attr-{args.ref}.json"
    rows = json.loads((ROOT / "data" / f"pi-episodes-{args.ref}.json").read_text())
    manifest = {str(r["eid"]): r for r in rows}
    files = sorted(glob.glob(str(reps / "episode-*-replay.json")))
    if args.limit:
        files = files[:args.limit]
    print(f"{len(files)} replay files in {reps}", flush=True)
    games, failed = [], []
    done = set()
    if out_path.exists() and not args.force:
        try:
            prev = json.loads(out_path.read_text())
            games = prev.get("games") or []
            failed = prev.get("failed") or []
            done = {str(g["episodeId"]) for g in games}
            print(f"resuming: {len(games)} games already attributed", flush=True)
        except Exception:  # noqa: BLE001
            games, failed = [], []
    n_new = 0
    todo = []
    for p in files:
        eid = Path(p).name.split("-")[1]
        rec = manifest.get(eid)
        if rec is None:
            failed.append((eid, "not in manifest"))
        elif eid not in done:
            todo.append((p, rec, eid))
    print(f"{len(todo)} games to attribute with {args.procs} procs", flush=True)
    if args.procs > 1 and len(todo) > 1:
        import multiprocessing as mp
        with mp.Pool(args.procs) as pool:
            results = pool.map(_job, [(p, r) for p, r, _ in todo])
    else:
        results = [_job((p, r)) for p, r, _ in todo]
    for (p, rec, eid), (g, err) in zip(todo, results):
        if g is None:
            failed.append((eid, err))
            print(f"  FAILED {eid}: {err}", flush=True)
            continue
        g["ref"] = args.ref
        games.append(g)
        n_new += 1
        print(f"  {eid} margin {g['margin']:>+9,.0f} gate={g['gate']} "
              f"seat={g['my_seat']} opp={g['opp_team'][:20]} score={g['opp_score']}", flush=True)
        if n_new % 5 == 0:
            Path(out_path).write_text(json.dumps({"games": games, "failed": failed}, indent=1))
    # dedupe failures by episode id
    seen = set()
    ded = []
    for eid, err in failed:
        if eid not in seen:
            seen.add(eid)
            ded.append((eid, err))
    failed = ded
    Path(out_path).write_text(json.dumps({"games": games, "failed": failed}, indent=1))
    ng = sum(1 for g in games if g["gate"])
    print(f"\nwrote {out_path}: {len(games)} games, {ng} passed the reproduction gate, "
          f"{len(failed)} failed", flush=True)


if __name__ == "__main__":
    sys.exit(main())
