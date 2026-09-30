#!/usr/bin/env python
"""What governs the exact -50 losses and exact ties in 56409633's ladder games?

Reward is `money` only (engine line 963: `s.reward = float(farms[player]["money"])`),
so an exact tie is a true money tie -- there is no secondary tie-break to win, and a
-50 loss needs 51 more coins, not a better tie-break.

This script rebuilds each anomaly game with the recorded actions (shift=1) and logs EVERY
money-moving event per seat: market commits (from `_commit_unit`), hires (`_do_hire`) and
land buys (`_do_buy_land`).  Then it diffs the two seats' ledgers, globally and over the
final day, to name the mechanism.
"""
import collections
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def install(log):
    import kaggle_environments.envs.kaggriculture.kaggriculture as K
    cur, orig = {}, (K._process_market, K._commit_unit, K._do_hire, K._do_buy_land, K._drop_inventories_to_shed)

    def pm(state, env):
        o = state[0].observation
        cur["farms"] = o.farms
        cur["step"] = K.get(o, "step", None)
        return orig[0](state, env)

    def seat_of(farm):
        return next((i for i, f in enumerate(cur.get("farms") or []) if f is farm), -1)

    def commit(op, item, price, farm, private, market, shed_capacity=100):
        pid = seat_of(farm)
        ok = orig[1](op, item, price, farm, private, market, shed_capacity)
        if ok:
            log.append({"step": cur.get("step"), "seat": pid, "kind": "MKT", "op": op,
                        "item": str(item), "delta": (float(price) if op == "SELL" else -float(price))})
        return ok

    def hire(farm, private, board_size, mult=1):
        pid, before = seat_of(farm), float(farm.get("money", 0))
        r = orig[2](farm, private, board_size, mult)
        if float(farm.get("money", 0)) != before:
            log.append({"step": cur.get("step"), "seat": pid, "kind": "HIRE", "op": "HIRE",
                        "item": "HAND", "delta": float(farm["money"]) - before})
        return r

    def land(farm, board_size):
        pid, before = seat_of(farm), float(farm.get("money", 0))
        r = orig[3](farm, board_size)
        if float(farm.get("money", 0)) != before:
            log.append({"step": cur.get("step"), "seat": pid, "kind": "LAND", "op": "BUY_LAND",
                        "item": "LAND", "delta": float(farm["money"]) - before})
        return r

    def drop(private, capacity):
        shed = private.get("shed") or {}
        before = sum(shed.values())
        inv = sum(sum(v for v in (d or {}).values()) for d in (private.get("inventories") or []))
        orig[4](private, capacity)
        if inv - (sum(shed.values()) - before) > 0:
            log.append({"step": cur.get("step"), "kind": "DISCARD",
                        "units": inv - (sum(shed.values()) - before)})

    K._process_market, K._commit_unit, K._do_hire, K._do_buy_land, K._drop_inventories_to_shed = \
        pm, commit, hire, land, drop
    return orig


def restore(orig):
    import kaggle_environments.envs.kaggriculture.kaggriculture as K
    (K._process_market, K._commit_unit, K._do_hire, K._do_buy_land, K._drop_inventories_to_shed) = orig


def seat_agent(actions, seat, shift=1):
    def agent(obs):
        s = obs.get("step") if isinstance(obs, dict) else 0
        s = (s or 0) + shift
        a = actions[s][seat] if 0 <= s < len(actions) else None
        return a if isinstance(a, dict) else {}
    return agent


def ledger(log, seat, lo=None, hi=None):
    c = collections.Counter()
    for e in log:
        if e.get("seat") != seat or "delta" not in e:
            continue
        if lo is not None and not (lo <= (e.get("step") or 0) <= hi):
            continue
        c[f"{e['kind']}:{e['op']}:{e['item']}"] += e["delta"]
    return c


def main():
    eps = json.loads((ROOT / "data" / "episodes-56409633-raw.json").read_text())
    anom = []
    for ep in eps:
        ag = ep.get("agents") or []
        mine = [a for a in ag if str(a.get("submissionId")) == "56409633"]
        if len(ag) != 2 or not mine or any(a.get("reward") is None for a in ag):
            continue
        me = mine[0]
        opp = [a for a in ag if a is not me][0]
        m = float(me["reward"]) - float(opp["reward"])
        if m in (0.0, -50.0):
            anom.append({"episode": ep["id"], "margin": m, "seat": me.get("index", 0),
                         "opp_team": opp.get("teamName"), "opp_sub": str(opp.get("submissionId")),
                         "mine": float(me["reward"]), "theirs": float(opp["reward"])})
    print(f"{len(anom)} anomaly games (0 or -50): "
          f"{sum(1 for a in anom if a['margin'] == 0)} ties, "
          f"{sum(1 for a in anom if a['margin'] == -50)} at -50")
    print("opponents:", collections.Counter(a["opp_team"] for a in anom).most_common())

    rows = []
    for a in anom:
        p = ROOT / "data" / "replays" / f"episode-{a['episode']}-replay.json"
        if not p.exists():
            print(f"  {a['episode']}: replay missing")
            continue
        d = json.loads(p.read_text())
        steps = d["steps"]
        actions = [[steps[t][s].get("action") or {} for s in (0, 1)] for t in range(len(steps))]
        log: list = []
        orig = install(log)
        try:
            from kaggle_environments import make
            cfg = dict(d.get("configuration") or {})
            cfg["seed"] = None
            env = make("kaggriculture", configuration=cfg, debug=True)
            env.info["seed"] = d.get("info", {}).get("seed")
            env.run([seat_agent(actions, 0), seat_agent(actions, 1)])
            repro = [round(float(env.steps[-1][s]["reward"] or 0)) for s in (0, 1)]
        finally:
            restore(orig)
        me = a["seat"]
        opp = 1 - me
        rec = [round(float(r)) for r in d["rewards"]]
        gate = repro == rec
        # mirror detection over the recorded action streams
        same_mkt = sum(1 for t in range(len(actions)) if actions[t][0].get("market") == actions[t][1].get("market"))
        same_farmer = sum(1 for t in range(len(actions)) if actions[t][0].get("farmer") == actions[t][1].get("farmer"))
        # ledgers
        Lme, Lop = ledger(log, me), ledger(log, opp)
        keys = sorted(set(Lme) | set(Lop), key=lambda k: (Lme[k] - Lop[k]))
        day = len(steps) // 24 - 1
        lme_d, lop_d = ledger(log, me, day * 24, 10 ** 9), ledger(log, opp, day * 24, 10 ** 9)
        # last money-moving events
        last_me = [e for e in log if e.get("seat") == me][-4:]
        last_op = [e for e in log if e.get("seat") == opp][-4:]
        print(f"\n=== ep {a['episode']} margin {a['margin']:+.0f} gate={gate} "
              f"me {rec[me]} opp {rec[opp]} vs {a['opp_team']}")
        print(f"  mirror: identical market lists {same_mkt}/{len(actions)} steps, "
              f"identical farmer action {same_farmer}/{len(actions)}")
        for k in keys:
            if abs(Lme[k] - Lop[k]) >= 1:
                print(f"  ledger {k:24} me {Lme[k]:>+10,.0f}  opp {Lop[k]:>+10,.0f}  diff {Lme[k]-Lop[k]:>+9,.0f}")
        print(f"  final-day net: me {sum(lme_d.values()):+,.0f} opp {sum(lop_d.values()):+,.0f}")
        print(f"  last events me : {[(e.get('step'), e.get('kind'), e.get('op'), e.get('item'), e.get('delta')) for e in last_me]}")
        print(f"  last events opp: {[(e.get('step'), e.get('kind'), e.get('op'), e.get('item'), e.get('delta')) for e in last_op]}")
        rows.append({"episode": a["episode"], "margin": a["margin"], "gate": gate,
                     "mirror_mkt": same_mkt, "mirror_farmer": same_farmer,
                     "ledger_diff": {k: Lme[k] - Lop[k] for k in keys if abs(Lme[k] - Lop[k]) >= 1}})
    (ROOT / "data" / "anomaly-50.json").write_text(json.dumps(rows, indent=1, default=str))
    # ---- aggregate the ledger difference across anomaly games
    agg = collections.Counter()
    for r in rows:
        for k, v in r["ledger_diff"].items():
            agg[k] += v
    print(f"\nAGGREGATE ledger difference (me - opp) over {len(rows)} anomaly games:")
    for k, v in sorted(agg.items(), key=lambda kv: kv[1]):
        print(f"  {k:26} {v:>+10,.0f}   (mean {v/len(rows):+.1f}/game)")
    print(f"\nall anomaly games byte-identical mirror of the opponent's market stream: "
          f"{sum(1 for r in rows if r['mirror_mkt'] == 719)}/{len(rows)}")


if __name__ == "__main__":
    sys.exit(main())
