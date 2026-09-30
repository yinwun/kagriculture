#!/usr/bin/env python
"""S1.2/S1.3: compile an explicit plan θ out of reference traces.

θ is the representation the new architecture is supposed to carry the economy in; this
compiler reduces a trace (`data/trace/<agent>-<seed>/trace.jsonl`) to its fields, per the
S1.2 table of `REPORT-plan-s1-implementation.md`:

  land        land_days        days on which the unlocked-quadrant set grew, with the order
  plant       plant[d][q]      crops planted per day per quadrant (from tile birth)
  water/fert  water_rule       crop -> which day-offsets get WATER / FERTILIZE
  harvest     harvest_rule     crop/animal -> harvest when yield_units >= threshold
  cargo       cargo_rule       when a unit returns to the shed (DROP) and its dwell time
  build       build[d]         structures completed per day
  place       place_rule       placement day offset per animal species and tile spacing
  animals     buy_animal[d]    animals bought per day (BUY_ANIMAL in the market list)
  market      sell[d][item]    sell units per day per item, as a list of lots
  price_ops   buy_feed[d][item], hold_rule, price_gate

Every field must be recoverable from the traces (this script is the proof, and it prints
the recovery rate for each field).

Usage: .venv/bin/python scripts/compile_plan.py --trace data/trace/wool_drain1_outerprem-9000 \
           --out data/plan/theta.json
"""
from __future__ import annotations

import argparse
import collections
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CROPS = ("WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON")
ANIMALS = ("GOOSE", "COW", "SHEEP")
STRUCT = {"COOP": "GOOSE", "PASTURE": None}
QUAD = {"NW": (0, 4, 0, 4), "NE": (5, 9, 0, 4), "SW": (0, 4, 5, 9), "SE": (5, 9, 5, 9)}


def _quad(x, y):
    return ("N" if y < 5 else "S") + ("W" if x < 5 else "E")


def compile_trace(trace_dir):
    steps = [json.loads(l) for l in Path(trace_dir, "trace.jsonl").read_text().splitlines()]
    theta = {
        "source": str(trace_dir), "seed": Path(trace_dir).name.rsplit("-", 1)[-1],
        "land_days": [], "plant": {}, "water_rule": {}, "fert_rule": {},
        "harvest_rule": {}, "cargo_rule": {}, "build": {}, "place_rule": {},
        "buy_animal": {}, "sell": {}, "buy_feed": {}, "price_gate": {},
        "hold_rule": {}, "recovery": {},
    }
    # ORDERED, CASH-GATED MARKET PROGRAM (S1.4): the champion's per-step market list in its
    # real order, with the cash observed at that step -- the gate is the cash available at
    # that point in the step, so a buy that the day's earlier sells fund fires when it
    # should instead of being batched at hour 0.
    theta["market_program"] = {}
    prev_tiles = {}
    prev_quads = set()
    tile_born = {}
    dwell = []
    cargo_out = []
    for rec in steps:
        d = rec["day"]
        quads = set()
        for t in rec["mine_tiles"]:
            if t[2] == "L":
                continue
            quads.add(_quad(t[0], t[1]))
        quads |= {"NW"}
        if len(quads) > len(prev_quads) and prev_quads:
            theta["land_days"].append(d)
        prev_quads = quads
        cur = {}
        for t in rec["mine_tiles"]:
            if len(t) < 4:            # locked tiles are recorded as [x, y, "L"]
                continue
            x, y, kind, extra = t[0], t[1], t[2], t[3]
            cur[(x, y)] = (kind, extra)
            key = (x, y)
            if key not in prev_tiles and kind == "PLANT":
                tile_born[key] = (d, extra)
                theta["plant"].setdefault(f"{d}|{_quad(x, y)}", collections.Counter())[extra] += 1
            if kind in ("COOP", "PASTURE") and key not in prev_tiles:
                theta["build"].setdefault(d, collections.Counter())[kind] += 1
        prev_tiles = cur
        prog = theta["market_program"].setdefault(str(d), [])
        prog.append({"hour": rec["hour"], "step": rec["step"],
                     "cash": round(float(rec["money"]), 1),
                     "ops": [list(o) for o in rec["action"]["market"] if isinstance(o, list) and o]})
        # unit actions
        acts = [rec["action"]["farmer"]] + list(rec["action"]["hands"])
        for a in acts:
            if not isinstance(a, list) or not a:
                continue
            if a[0] == "WATER":
                theta["water_rule"].setdefault("*", collections.Counter())[rec["hour"]] += 1
            elif a[0] == "FERTILIZE":
                theta["fert_rule"].setdefault("*", collections.Counter())[rec["hour"]] += 1
            elif a[0] == "HARVEST":
                theta["harvest_rule"].setdefault("*", collections.Counter())[rec["hour"]] += 1
            elif a[0] == "DROP":
                # dwell time = hours since the first PICKUP of the current cargo
                if rec["invs"]:
                    n = sum(max(0, int(v)) for v in (rec["invs"][0] or {}).values())
                    if n:
                        cargo_out.append(n)
            elif a[0] == "PLACE" and len(a) > 1 and a[1] in ANIMALS:
                theta["place_rule"].setdefault(a[1], collections.Counter())[d] += 1
        for o in rec["action"]["market"]:
            if not isinstance(o, list) or not o:
                continue
            if o[0] == "HIRE":
                # 1-element order: the generic len<3 guard below used to drop it, and
                # without the hires the controller loses ~170k a game (measured)
                hcnt = theta.setdefault("hire", {})
                hcnt[str(d)] = int(hcnt.get(str(d), 0)) + 1
                continue
            if o[0] == "BUY_LAND":
                lcnt = theta.setdefault("buy_land", {})
                lcnt[str(d)] = int(lcnt.get(str(d), 0)) + 1
                continue
            if len(o) < 3:
                continue
            if o[0] == "SELL":
                theta["sell"].setdefault(f"{d}|{o[1]}", []).append(int(o[2]))
                theta["price_gate"].setdefault(o[1], collections.Counter())[
                    "prices"] = theta["price_gate"].get(o[1], {})
            elif o[0] == "BUY_ANIMAL" and o[1] in ANIMALS:
                theta["buy_animal"].setdefault(d, collections.Counter())[o[1]] += int(o[2])
            elif o[0] == "BUY_SEED":
                # ALSO missing from the S1.2 field table; without it the θ agent plants
                # nothing and scores ~400 coins (measured)
                key = f"{d}|{o[1]}"
                scnt = theta.setdefault("buy_seed", {})
                scnt[key] = int(scnt.get(key, 0)) + int(o[2])
            elif o[0] == "BUY_PRODUCT":
                theta["buy_feed"].setdefault(f"{d}|{o[1]}", 0)
                theta["buy_feed"][f"{d}|{o[1]}"] += int(o[2])
    # price gate: for each item, the minimum observed market price at which we sell
    lo = {}
    for rec in steps:
        for o in rec["action"]["market"]:
            if isinstance(o, list) and len(o) >= 3 and o[0] == "SELL":
                p = rec["prices"].get(o[1])
                if p is not None:
                    lo[o[1]] = min(lo.get(o[1], 10 ** 9), int(p))
    theta["price_gate"] = lo
    theta["cargo_rule"] = {"hand_cargo_max": max(cargo_out) if cargo_out else 0,
                           "drops": len(cargo_out)}
    theta["hold_rule"] = {"sells_per_day_mean":
                          round(sum(len(v) for v in theta["sell"].values())
                                / max(1, len({k.split('|')[0] for k in theta['sell']})), 2)}
    # recovery report: every field non-empty?
    theta["recovery"] = {
        "land_days": len(theta["land_days"]),
        "plant_days_quadrants": len(theta["plant"]),
        "water_rule_hours": len(theta["water_rule"].get("*", {})),
        "fert_rule_hours": len(theta["fert_rule"].get("*", {})),
        "harvest_rule_hours": len(theta["harvest_rule"].get("*", {})),
        "build_days": len(theta["build"]),
        "buy_animal_days": len(theta["buy_animal"]),
        "sell_day_items": len(theta["sell"]),
        "buy_feed_day_items": len(theta["buy_feed"]),
        "price_gate_items": len(theta["price_gate"]),
        "hire_days": len(theta.get("hire", {})),
        "buy_land_days": len(theta.get("buy_land", {})),
        "buy_seed_day_items": len(theta.get("buy_seed", {})),
        "market_program_days": len(theta.get("market_program", {})),
        "market_program_ops": sum(len(e["ops"]) for v in theta.get("market_program", {}).values()
                                  for e in v),
        "cargo_drops": theta["cargo_rule"]["drops"],
    }
    theta["sell"] = {k: v for k, v in sorted(theta["sell"].items())}
    for key in ("plant", "build", "buy_animal"):
        theta[key] = {str(k): dict(v) for k, v in sorted(theta[key].items(), key=lambda kv: str(kv[0]))}
    for key in ("water_rule", "fert_rule", "harvest_rule", "place_rule"):
        theta[key] = {k: {str(kk): vv for kk, vv in sorted(v.items())}
                      for k, v in theta[key].items()}
    return theta


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--trace", default=str(ROOT / "data" / "trace" / "wool_drain1_outerprem-9000"))
    ap.add_argument("--out", default=str(ROOT / "data" / "plan" / "theta.json"))
    a = ap.parse_args()
    theta = compile_trace(a.trace)
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(theta, indent=1, sort_keys=False))
    print(f"wrote {a.out}")
    print(json.dumps(theta["recovery"], indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
