#!/usr/bin/env python
"""Record the champion's market behaviour, validate the clearing model on real
games, and measure the oracle headroom of a sell-layout search.

Phase 1 -- record.  Both seats run the champion; at every step each seat records
its own observation (market inventory, its private shed, its money) and the market
list it returned.  Because both sheds are private to their owner, this is the only
way to know the whole clearing state of a step.

Phase 2 -- validate.  Replay every step through `lockstep.clear()` and compare the
predicted next-step money with the money the engine actually produced.  This is an
end-to-end check of the replica on real orders (not synthetic ones).

Phase 3 -- headroom.  For every step, take the opponent's *true* market list and
search layouts of our own list for the largest simulated `revenue_me - revenue_opp`
gain over the layout the champion actually used.  The sum of those per-step gains
is an upper bound on what a perfect layout chooser with a perfect rival model
could add to our final wallet in that game.

Usage: .venv/bin/python scripts/race_probe.py --seeds 9000,9001 --out data/race-probe.json
"""
from __future__ import annotations

import argparse
import itertools
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import lockstep  # noqa: E402

CHAMPION = ROOT / "data" / "tapeopt" / "rgcs" / "main.py"
PRODUCTS = list(lockstep.PRODUCTS)


def _load_agent(path):
    ns = {"__name__": "probe_mod"}
    exec(compile(Path(path).read_text(), str(path), "exec"), ns)
    return ns["agent"]


def record_duel(seeds, base_path=CHAMPION, cand_path=None):
    from kaggle_environments import make

    base = _load_agent(base_path)
    cand = _load_agent(cand_path) if cand_path else base

    recs = []
    for seed in seeds:
        trace = {0: {}, 1: {}}

        def wrap(agent, seat):
            def fn(obs):
                act = agent(obs)
                private = obs.get("private") or {}
                trace[seat][int(obs["step"])] = {
                    "market": [list(o) for o in ((act or {}).get("market") or [])],
                    "shed": dict(private.get("shed") or {}),
                    "money": float(obs["farms"][seat].get("money", 0.0)),
                    "inv": dict((obs.get("market") or {}).get("inventory") or {}),
                    "shops": list(((obs.get("town") or {}).get("unlocked_shops")) or []),
                }
                return act
            return fn

        env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": seed})
        env.run([wrap(cand, 0), wrap(base, 1)])
        final = [float(env.steps[-1][i]["reward"] or 0) for i in (0, 1)]
        recs.append({"seed": seed, "final": final, "trace": trace})
    return recs


def stats_of_trace(rec):
    """Distribution of the market lists and of the sell quantities."""
    out = {"steps": 0, "orders_hist": {}, "sell_items": {}, "sell_qty_hist": {},
           "slot_pairs_same_item": 0, "slot_pairs_same_item_same_qty": 0,
           "slot_pairs_both_sell": 0, "max_orders": 0}
    t = rec["trace"]
    steps = sorted(set(t[0]) & set(t[1]))
    for s in steps:
        a, b = t[0][s], t[1][s]
        out["steps"] += 1
        out["orders_hist"][len(a["market"])] = out["orders_hist"].get(len(a["market"]), 0) + 1
        out["max_orders"] = max(out["max_orders"], len(a["market"]), len(b["market"]))
        for o in a["market"]:
            if isinstance(o, list) and o:
                if o[0] == "SELL":
                    key = f"{o[1]}"
                    out["sell_items"][key] = out["sell_items"].get(key, 0) + 1
                    out["sell_qty_hist"][o[2]] = out["sell_qty_hist"].get(o[2], 0) + 1
        for i in range(max(len(a["market"]), len(b["market"]))):
            oa = a["market"][i] if i < len(a["market"]) else None
            ob = b["market"][i] if i < len(b["market"]) else None
            if (isinstance(oa, list) and oa and oa[0] == "SELL"
                    and isinstance(ob, list) and ob and ob[0] == "SELL"):
                out["slot_pairs_both_sell"] += 1
                if oa[1] == ob[1]:
                    out["slot_pairs_same_item"] += 1
                    if oa[2] == ob[2]:
                        out["slot_pairs_same_item_same_qty"] += 1
    out["orders_hist"] = {str(k): v for k, v in sorted(out["orders_hist"].items())}
    return out


def validate(rec):
    """Replay each step with lockstep.clear and compare money to the engine's."""
    t = rec["trace"]
    steps = sorted(set(t[0]) & set(t[1]))
    mism = []
    checked = 0
    for s in steps:
        nxt = s + 1
        if nxt not in t[0] or nxt not in t[1]:
            continue
        a, b = t[0][s], t[1][s]
        exp = lockstep.clear(a["market"], b["market"], a["inv"], (a["shed"], b["shed"]),
                             money=(a["money"], b["money"]))
        for p, src in ((0, a), (1, b)):
            got = t[p][nxt]["money"]
            checked += 1
            if abs(exp["money"][p] - got) > 1e-9:
                mism.append({"step": s, "player": p, "exp": exp["money"][p], "got": got,
                             "orders": [a["market"], b["market"]],
                             "inv": a["inv"], "shed": [a["shed"], b["shed"]]})
    return checked, mism


def rev_split(orders_me, orders_opp, inv0, shed_me, shed_opp):
    r = lockstep.clear(orders_me, orders_opp, inv0, (shed_me, shed_opp))
    return r["rev"][0], r["rev"][1]


def candidate_layouts(orders, max_slots=10):
    """Layouts of our own list that keep every non-SELL order in place."""
    sells = [(i, o) for i, o in enumerate(orders)
             if isinstance(o, list) and o and o[0] == "SELL" and len(o) >= 3]
    fixed = {i: o for i, o in enumerate(orders) if i not in {i for i, _ in sells}}
    free = [i for i in range(max_slots) if i not in fixed]
    out = []

    def emit(assign):
        """assign: list of (slot, order)"""
        slots = dict(fixed)
        for slot, o in assign:
            if slot in slots:
                return None
            slots[slot] = o
        return [slots[k] for k in sorted(slots)]

    if len(sells) <= 6:
        for perm in itertools.permutations(range(len(sells))):
            assign = [(free[k] if k < len(free) else sells[perm[k]][0], sells[perm[k]][1])
                      for k in range(len(sells))]
            cand = emit(assign)
            if cand is None or len(cand) > max_slots:
                continue
            out.append(cand)
    return out


def headroom(rec, max_perm=6):
    """Sum over steps of the best simulated differential gain over the actual layout."""
    t = rec["trace"]
    steps = sorted(set(t[0]) & set(t[1]))
    total = 0.0
    per_step = []
    for s in steps:
        a, b = t[0][s], t[1][s]
        if not any(isinstance(o, list) and o and o[0] == "SELL" for o in a["market"]):
            continue
        base0, base1 = rev_split(a["market"], b["market"], a["inv"], a["shed"], b["shed"])
        base = base0 - base1
        best = base
        best_layout = None
        for cand in candidate_layouts(a["market"], max_slots=10):
            if len([o for o in cand if isinstance(o, list) and o and o[0] == "SELL"]) > max_perm:
                continue
            r0, r1 = rev_split(cand, b["market"], a["inv"], a["shed"], b["shed"])
            if r0 - r1 > best + 1e-9:
                best = r0 - r1
                best_layout = cand
        if best_layout is not None:
            total += best - base
            per_step.append({"step": s, "gain": best - base, "layout": best_layout,
                             "mine": a["market"], "theirs": b["market"]})
    return total, per_step


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", default="9000")
    ap.add_argument("--cand", default=None)
    ap.add_argument("--base", default=str(CHAMPION))
    ap.add_argument("--out", default=None)
    ap.add_argument("--headroom", action="store_true")
    args = ap.parse_args()

    seeds = [int(x) for x in args.seeds.split(",")]
    recs = record_duel(seeds, base_path=args.base, cand_path=args.cand)
    summary = []
    for rec in recs:
        st = stats_of_trace(rec)
        checked, mism = validate(rec)
        row = {"seed": rec["seed"], "final": rec["final"], "validated": checked,
               "money_mismatches": len(mism), "stats": st}
        print(f"seed {rec['seed']}: final {rec['final']}, steps {st['steps']}, "
              f"orders/step hist {st['orders_hist']}, max orders {st['max_orders']}")
        print(f"   sell orders by item {st['sell_items']}")
        print(f"   sell qty hist {dict(sorted(st['sell_qty_hist'].items(), key=lambda kv: int(kv[0]))) }")
        print(f"   slots with a SELL on both sides {st['slot_pairs_both_sell']}, "
              f"same item {st['slot_pairs_same_item']}, same item and qty "
              f"{st['slot_pairs_same_item_same_qty']}")
        print(f"   clearing replay: {checked} player-steps, mismatches {len(mism)}")
        if mism:
            print("   FIRST MISMATCH", json.dumps(mism[0])[:400])
        if args.headroom:
            total, per = headroom(rec)
            row["headroom_total"] = total
            row["headroom_steps"] = len(per)
            row["headroom_per_step"] = per[:40]
            print(f"   ORACLE HEADROOM (perfect rival layout, permutations of our own "
                  f"list): {total:,.0f} over {len(per)} reorderable steps")
            if per:
                top = sorted(per, key=lambda d: -d["gain"])[:5]
                for d in top:
                    print(f"      step {d['step']:3d} gain {d['gain']:+8.0f} "
                          f"mine {d['mine']} theirs {d['theirs']} -> {d['layout']}")
        summary.append(row)
    if args.out:
        Path(args.out).write_text(json.dumps(summary, indent=1))
        print("wrote", args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
