#!/usr/bin/env python
"""Replay-based attribution for a submission's ladder games.

Per game it produces, for both seats:
  * per-day liquid net worth (scripts/day_gap.py math) -> which day the deficit opens;
  * per-product executed units / revenue / average realised price, **exact**, from an
    instrumented re-simulation: the replay's recorded actions (shift=1, the project's
    bank-reproduction rule) are fed back into the official engine and the engine's own
    `_commit_unit` is wrapped to log every executed unit with its seat and price;
  * farm-side worker verb counters per day, shed-overflow discards, the day-6 shop tuple;
  * market-order structure (SELL step coverage, multi-SELL steps, WOOL coverage) as the
    signature of our race / forward layers.

Usage:
  python scripts/replay_attribute.py --refs 56422944 56409633 --out data/replay-attr.json
"""
from __future__ import annotations

import argparse
import collections
import glob
import json
import statistics as st
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from day_gap import _worth  # noqa: E402

TURNS = 24
WORKER_VERBS = ("PLANT", "WATER", "HARVEST", "FEED", "CARE", "COLLECT_FERTILIZER",
                "PLACE", "PICKUP", "DROP", "DIG", "BUILD_PASTURE", "BUILD_COOP",
                "FERTILIZE", "PASS", "MOVE")


# ---------------------------------------------------------------- hooks
def install_hooks(log):
    """Wrap the engine's market/shed functions to log executed units per seat.

    `_process_market` is wrapped only to learn the current farms/step, so a commit can
    be attributed to a seat by identity of the farm dict."""
    import kaggle_environments.envs.kaggriculture.kaggriculture as K
    cur: dict = {}
    orig = (K._process_market, K._commit_unit, K._drop_inventories_to_shed)

    def pm(state, env):
        obs0 = state[0].observation
        cur["farms"] = obs0.farms
        cur["step"] = K.get(obs0, "step", None)
        return orig[0](state, env)

    def commit(op, item, price, farm, private, market, shed_capacity=100):
        pid = next((i for i, f in enumerate(cur.get("farms") or []) if f is farm), -1)
        ok = orig[1](op, item, price, farm, private, market, shed_capacity)
        if ok and op in ("SELL", "BUY_PRODUCT", "BUY_SEED", "BUY_ANIMAL"):
            log.append({"step": cur.get("step"), "seat": pid, "op": op,
                        "item": str(item), "price": float(price)})
        return ok

    def drop(private, capacity):
        shed = private.get("shed") or {}
        before = sum(shed.values())
        inv = sum(sum(v for v in (d or {}).values()) for d in (private.get("inventories") or []))
        orig[2](private, capacity)
        taken = sum(shed.values()) - before
        if inv - taken > 0:
            log.append({"step": cur.get("step"), "op": "DISCARD", "units": inv - taken})

    K._process_market, K._commit_unit, K._drop_inventories_to_shed = pm, commit, drop
    return orig


def restore_hooks(orig):
    import kaggle_environments.envs.kaggriculture.kaggriculture as K
    K._process_market, K._commit_unit, K._drop_inventories_to_shed = orig


# ---------------------------------------------------------------- replay helpers
def seat_agent(actions, seat, shift=1):
    """The project's validated replay rule: the action at index t+1 is applied to the
    state at index t (shift=1 reproduces final banks exactly)."""
    def agent(obs):
        s = obs.get("step") if isinstance(obs, dict) else None
        if s is None:
            s = len(actions) - 1
        s += shift
        a = actions[s][seat] if 0 <= s < len(actions) else None
        return a if isinstance(a, dict) else {}
    return agent


def seat_of(episodes_by_ep, eid):
    rec = episodes_by_ep.get(str(eid))
    return None if rec is None else rec


def load_manifest(ref):
    eps = json.loads((ROOT / "data" / f"episodes-{ref}-raw.json").read_text())
    out = {}
    for ep in eps:
        if ep.get("type") != "EPISODE_TYPE_PUBLIC":
            continue
        ag = ep.get("agents") or []
        if len(ag) != 2:
            continue
        mine = [a for a in ag if str(a.get("submissionId")) == str(ref)]
        if not mine:
            continue
        me = mine[0]
        seat = me.get("index")
        if seat is None:
            seat = ag.index(me)
        opp = [a for a in ag if a is not me][0]
        out[str(ep["id"])] = {"my_seat": int(seat), "my": float(me["reward"]),
                              "opp": float(opp["reward"]),
                              "margin": float(me["reward"]) - float(opp["reward"]),
                              "opp_team": opp.get("teamName"), "opp_sub": str(opp.get("submissionId"))}
    return out


def day_end_indices(steps, seat):
    """Index of the last recorded step of each in-game day."""
    last = {}
    for t, entry in enumerate(steps):
        d = entry[seat]["observation"].get("day")
        if d is not None:
            last[int(d)] = t
    return last


def attribute_game(path, rec, ref, ratings):
    d = json.loads(Path(path).read_text())
    steps = d["steps"]
    me, opp = rec["my_seat"], 1 - rec["my_seat"]
    actions = [[steps[t][p].get("action") or {} for p in (0, 1)] for t in range(len(steps))]

    # ---- exact market attribution via instrumented re-simulation
    log: list = []
    orig = install_hooks(log)
    seed = d.get("info", {}).get("seed")
    cfg = dict(d.get("configuration") or {})
    cfg["seed"] = None
    try:
        env = make_and_run(cfg, seed, actions)
        repro = [round(float(env.steps[-1][p]["reward"] or 0)) for p in (0, 1)]
    finally:
        restore_hooks(orig)
    recorded = [round(float(r)) for r in d["rewards"]]
    gate = repro == recorded

    # ---- per-day liquid net worth from the replay's own observations
    last = day_end_indices(steps, me)
    worth = {}
    for day, t in sorted(last.items()):
        o_me = steps[t][me]["observation"]
        o_op = steps[t][opp]["observation"]
        worth[day] = (float(_worth(o_me, me)), float(_worth(o_op, opp)))

    # ---- market orders: item stats from the log, structure from the recorded actions
    item = collections.defaultdict(lambda: {"units": 0, "rev": 0.0})
    buys = collections.defaultdict(lambda: {"units": 0, "spend": 0.0})
    for e in log:
        if e.get("op") == "DISCARD":
            continue
        s = e.get("seat")
        if s not in (me, opp):
            continue
        key = ("me" if s == me else "opp", e["item"])
        if e["op"] == "SELL":
            item[key]["units"] += 1
            item[key]["rev"] += e["price"]
        elif e["op"] == "BUY_PRODUCT":
            buys[key]["units"] += 1
            buys[key]["spend"] += e["price"]

    disc = collections.Counter()
    for e in log:
        if e.get("op") == "DISCARD":
            disc[int(e.get("step") or 0) // TURNS] += e["units"]

    # ---- worker verbs per day (from the recorded actions, shift=1)
    verbs = collections.defaultdict(collections.Counter)
    sells_wool_steps = multi_sell_steps = sell_steps = 0
    for t in range(len(steps) - 1):
        a = actions[t + 1][me]
        day = t // TURNS
        for cmd in [a.get("farmer") or []] + list(a.get("hands") or []):
            if isinstance(cmd, list) and cmd:
                v = str(cmd[0])
                if v in ("NORTH", "SOUTH", "EAST", "WEST"):
                    v = "MOVE"
                if v in WORKER_VERBS or v == "MOVE":
                    verbs[day][v] += 1
        mk = a.get("market") or []
        n_sell = sum(1 for o in mk if isinstance(o, list) and o and o[0] == "SELL")
        if n_sell:
            sell_steps += 1
        if n_sell >= 2:
            multi_sell_steps += 1
        if any(isinstance(o, list) and len(o) >= 3 and o[0] == "SELL" and o[1] == "WOOL" for o in mk):
            sells_wool_steps += 1

    opp_obs_shops = steps[2 * TURNS][opp]["observation"].get("town", {}).get("unlocked_shops")
    my_obs_shops = steps[2 * TURNS][me]["observation"].get("town", {}).get("unlocked_shops")

    items = {}
    for (who, it), v in item.items():
        items[f"{who}:{it}"] = {"units": v["units"], "rev": v["rev"],
                                "avg": (v["rev"] / v["units"]) if v["units"] else 0.0}
    for (who, it), v in buys.items():
        items.setdefault(f"{who}:{it}", {"units": 0, "rev": 0.0, "avg": 0.0})
        items[f"{who}:{it}"]["buy_units"] = v["units"]
        items[f"{who}:{it}"]["spend"] = v["spend"]

    fin = {t: worth[t] for t in worth}
    first_def = None
    for day in sorted(fin):
        if fin[day][0] - fin[day][1] < 0:
            first_def = day
            break
    return {"episode": d.get("id"), "my_seat": me, "opp_team": rec["opp_team"],
            "opp_sub": rec["opp_sub"], "opp_score": ratings.get(rec["opp_sub"]),
            "margin": rec["margin"], "money_match": gate, "recorded": recorded, "reproduced": repro,
            "day_worth": {str(k): v for k, v in fin.items()},
            "day_gap": {str(k): round(v[0] - v[1]) for k, v in fin.items()},
            "first_deficit_day": first_def,
            "final_gap": round(list(fin.values())[-1][0] - list(fin.values())[-1][1]) if fin else None,
            "items": items, "discards_by_day": {str(k): v for k, v in disc.items()},
            "verbs_by_day": {str(k): dict(v) for k, v in verbs.items()},
            "structure": {"sell_steps": sell_steps, "multi_sell_steps": multi_sell_steps,
                          "wool_sell_steps": sells_wool_steps},
            "shops_day2": {"me": my_obs_shops, "opp": opp_obs_shops}}


def make_and_run(cfg, seed, actions):
    from kaggle_environments import make
    env = make("kaggriculture", configuration=cfg, debug=True)
    env.info["seed"] = seed
    env.run([seat_agent(actions, 0), seat_agent(actions, 1)])
    return env


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--refs", nargs="+", required=True)
    ap.add_argument("--replays", default=str(ROOT / "data" / "replays"))
    ap.add_argument("--out", default=str(ROOT / "data" / "replay-attr.json"))
    args = ap.parse_args()
    lb = json.loads((ROOT / "data" / "leaderboard.json").read_text())
    ratings = {str(r.get("teamId")): float(r["score"]) for r in lb if r.get("score")}
    res = {}
    for ref in args.refs:
        eps = load_manifest(ref)
        games = []
        for p in sorted(glob.glob(str(Path(args.replays) / "episode-*-replay.json"))):
            eid = Path(p).name.split("-")[1]
            rec = eps.get(eid)
            if rec is None:
                continue
            try:
                g = attribute_game(p, rec, ref, ratings)
            except Exception as exc:  # noqa: BLE001
                print(f"  {eid}: FAILED {type(exc).__name__}: {exc}", flush=True)
                continue
            g["ref"] = ref
            games.append(g)
            print(f"  {ref} ep {eid} margin {g['margin']:+,.0f} gate={g['money_match']} "
                  f"first_deficit_day={g['first_deficit_day']} final_gap={g['final_gap']:+,.0f}",
                  flush=True)
        res[ref] = games
    Path(args.out).write_text(json.dumps(res, indent=1, default=str))
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
