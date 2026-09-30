#!/usr/bin/env python
"""Task 42: analysis of `data/pi-attr-<ref>.json` -> channels, volume/price, production.

Every number in the report's attribution section comes from here.  The accounting is
verified to close: the per-item channel sum must reproduce the recorded wallet margin
exactly (any residual is printed and must be 0).

Usage: .venv/bin/python scripts/pi_analyse.py --ref 56642424
"""
from __future__ import annotations

import argparse
import json
import statistics as st
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PRODUCTS = ["WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON", "EGG", "MILK", "WOOL",
            "FERTILIZER"]
ANIMALS = ["GOOSE", "COW", "SHEEP"]
KEYS = PRODUCTS + ANIMALS          # crop names collide with product names on purpose:
                                   # BUY_SEED WHEAT and BUY_PRODUCT WHEAT are one budget


def load(ref):
    d = json.loads((ROOT / "data" / f"pi-attr-{ref}.json").read_text())
    return [g for g in d["games"] if g["gate"]]


def cls(g):
    m = g["margin"]
    return "loss" if m <= 0 else ("closewin" if m < 2000 else "bigwin")


def cells(g):
    """Per-item channel cells for one game, plus the closure residual."""
    a, b = g["per"]["me"], g["per"]["opp"]
    out = {}
    for k in KEYS:
        su = a["sells"].get(k, {"units": 0, "rev": 0.0})
        so = b["sells"].get(k, {"units": 0, "rev": 0.0})
        bu = a["buys"].get(k, {"units": 0, "spend": 0.0})
        bo = b["buys"].get(k, {"units": 0, "spend": 0.0})
        um, uo = su["units"], so["units"]
        rm, ro = su["rev"], so["rev"]
        sm, so_ = bu["spend"], bo["spend"]
        pm = rm / um if um else 0.0
        po = ro / uo if uo else 0.0
        out[k] = {"u_me": um, "u_op": uo, "d_u": um - uo,
                  "p_me": pm, "p_op": po, "d_p": pm - po,
                  "d_rev": rm - ro, "d_spend": sm - so_, "net": (rm - ro) - (sm - so_),
                  "vol": (um - uo) * (pm + po) / 2.0,
                  "px": (pm - po) * (um + uo) / 2.0}
    out["_other"] = {"net": -(a["other_costs"] - b["other_costs"]),
                     "hire_me": a["hire_cost"], "hire_op": b["hire_cost"],
                     "land_me": a["land_cost"], "land_op": b["land_cost"]}
    out["_resid"] = g["margin"] - (sum(out[k]["net"] for k in KEYS) + out["_other"]["net"])
    return out


def mean_cells(games):
    out = {}
    for k in KEYS + ["_other"]:
        out[k] = {f: st.mean(cells(g)[k][f] for g in games)
                  for f in cells(games[0])[k]}
    out["_resid"] = st.mean(cells(g)["_resid"] for g in games)
    return out


def production(g):
    a, b = g["per"]["me"]["acc"], g["per"]["opp"]["acc"]
    out = {}
    for key in ("prod", "harvest_units", "fed_units", "placed", "unit_discard",
                "fert_used"):
        for item in set(a.get(key, {})) | set(b.get(key, {})):
            out.setdefault(key, {})[item] = (a[key].get(item, 0), b[key].get(item, 0))
    out["verbs"] = {v: (a["verbs"].get(v, 0), b["verbs"].get(v, 0))
                    for v in set(a["verbs"]) | set(b["verbs"])}
    out["worker_actions"] = (a["worker_actions"], b["worker_actions"])
    for k in ("market_orders", "sell_steps", "multi_sell_steps", "wool_sell_steps"):
        out[k] = (a[k], b[k])
    return out


def table(name, gs):
    M = mean_cells(gs)
    print(f"\n--- {name}: n={len(gs)}, mean margin {st.mean(g['margin'] for g in gs):+,.0f} ---")
    print(f"{'item':12s} {'u_me':>8} {'u_op':>8} {'du':>7} {'p_me':>8} {'p_op':>8} "
          f"{'dp':>7} {'dRev':>8} {'dSpend':>8} {'net':>8} {'volEff':>8} {'pxEff':>8}")
    t = {x: 0.0 for x in ("d_rev", "d_spend", "net", "vol", "px")}
    for k in KEYS:
        r = M[k]
        if max(abs(r[x]) for x in ("u_me", "u_op", "d_rev", "d_spend")) < 0.05:
            continue
        print(f"{k:12s} {r['u_me']:8.1f} {r['u_op']:8.1f} {r['d_u']:+7.1f} {r['p_me']:8.2f} "
              f"{r['p_op']:8.2f} {r['d_p']:+7.2f} {r['d_rev']:+8.0f} {r['d_spend']:+8.0f} "
              f"{r['net']:+8.0f} {r['vol']:+8.0f} {r['px']:+8.0f}")
        for x in t:
            t[x] += r[x]
    print(f"{'hire+land':12s} {'':8} {'':8} {'':8} {'':8} {'':8} {'':8} {'':8} {'':8} "
          f"{M['_other']['net']:+8.0f}")
    print(f"{'TOTAL':12s} {'':8} {'':8} {'':8} {'':8} {'':8} {'':8} {t['d_rev']:+8.0f} "
          f"{t['d_spend']:+8.0f} {t['net']+M['_other']['net']:+8.0f} {t['vol']:+8.0f} "
          f"{t['px']:+8.0f}")
    print(f"closure residual (must be 0): {M['_resid']:+.4f}")
    return M


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ref", default="56642424")
    args = ap.parse_args()
    games = load(args.ref)
    games.sort(key=lambda g: g["margin"])
    losses = [g for g in games if cls(g) == "loss"]
    close = [g for g in games if cls(g) == "closewin"]
    big = [g for g in games if cls(g) == "bigwin"]
    print(f"{len(games)} games with a valid reproduction gate: {len(losses)} losses, "
          f"{len(close)} close wins (<2000), {len(big)} big wins")

    M = {"all": table("ALL 91", games), "loss": table("LOSSES", losses),
         "closewin": table("CLOSE WINS", close)}

    print("\n=== per-game channel table, the 14 losses ===")
    print(f"{'eid':>10} {'margin':>9} {'wheat':>8} {'egg':>8} {'straw':>8} {'wool':>8} "
          f"{'milk':>8} {'tomato':>8} {'carrot':>8} {'fert':>8} {'melon':>8} "
          f"{'animBuy':>8} {'other':>8} {'resid':>6} {'oppScore':>8}")
    for g in losses:
        c = cells(g)
        anim = sum(c[k]["net"] for k in ANIMALS)
        print(f"{g['episodeId']:>10} {g['margin']:>+9,.0f} {c['WHEAT']['net']:>+8,.0f} "
              f"{c['EGG']['net']:>+8,.0f} {c['STRAWBERRY']['net']:>+8,.0f} "
              f"{c['WOOL']['net']:>+8,.0f} {c['MILK']['net']:>+8,.0f} "
              f"{c['TOMATO']['net']:>+8,.0f} {c['CARROT']['net']:>+8,.0f} "
              f"{c['FERTILIZER']['net']:>+8,.0f} {c['MELON']['net']:>+8,.0f} "
              f"{anim:>+8,.0f} {c['_other']['net']:>+8,.0f} {c['_resid']:>+6.0f} "
              f"{(g['opp_score'] or 0):>8.0f}")

    print("\n=== production (units, mean per game), me / opp (delta) ===")
    for name, gs in (("loss", losses), ("closewin", close), ("bigwin", big)):
        print(f"\n--- {name} n={len(gs)} ---")
        keys = ("harvest_units", "fed_units", "placed", "unit_discard", "fert_used")
        items = sorted({i for g in gs for k in keys for i in production(g).get(k, {})})
        print(f"{'item':11s} " + " ".join(f"{k:>22s}" for k in keys))
        for it in items:
            cs = []
            for k in keys:
                a = st.mean(production(g).get(k, {}).get(it, (0, 0))[0] for g in gs)
                b = st.mean(production(g).get(k, {}).get(it, (0, 0))[1] for g in gs)
                cs.append(f"{a:8.1f}/{b:8.1f}({a-b:+5.1f})")
            print(f"{it:11s} " + " ".join(cs))
        print("verbs me-opp: " + ", ".join(
            f"{v} {st.mean(production(g)['verbs'].get(v,(0,0))[0]-production(g)['verbs'].get(v,(0,0))[1] for g in gs):+.0f}"
            for v in sorted(production(gs[0])["verbs"])))
        for k in ("market_orders", "sell_steps", "multi_sell_steps", "wool_sell_steps"):
            print(f"  {k:18s} me {st.mean(production(g)[k][0] for g in gs):8.1f} "
                  f"opp {st.mean(production(g)[k][1] for g in gs):8.1f}")

    print("\n=== opponent strength vs outcome ===")
    for name, gs in (("loss", losses), ("closewin", close), ("bigwin", big)):
        sc = [g["opp_score"] for g in gs if g["opp_score"]]
        print(f"{name:9s} n={len(gs):3d}  opp score mean {st.mean(sc):7.0f} "
              f"median {st.median(sc):7.0f}  range {min(sc):.0f}-{max(sc):.0f}")

    print("\n=== day-gap curves (mean me-opp liquid net worth) ===")
    days = sorted({int(d) for g in games for d in g["day_gap"]})
    print(f"{'day':>4} " + " ".join(f"{c:>12s}" for c in ("loss", "closewin", "bigwin")))
    for d in days:
        cs = []
        for gs in (losses, close, big):
            vals = [g["day_gap"][str(d)] for g in gs if str(d) in g["day_gap"]]
            cs.append(f"{st.mean(vals):+12,.0f}" if vals else f"{'-':>12s}")
        print(f"{d:>4} " + " ".join(cs))

    print("\n=== margin distribution (all 91) ===")
    ms = sorted(g["margin"] for g in games)
    for thr in (0, 100, 250, 500, 1000, 2000, 5000):
        print(f"  |margin| <= {thr:5d}: {sum(1 for m in ms if abs(m) <= thr):3d} games")
    print(f"  mean {st.mean(ms):+,.0f} median {st.median(ms):+,.0f} sum {sum(ms):+,.0f}")
    print(f"  losses converted by a uniform +250:  "
          f"{sum(1 for m in ms if -250 <= m < 0)}; +500: {sum(1 for m in ms if -500 <= m < 0)}; "
          f"+1100: {sum(1 for m in ms if -1100 <= m < 0)}")

    print("\n=== counterfactual: our units at the opponent's realised price ===")
    for name in ("loss", "closewin"):
        gs = losses if name == "loss" else close
        C = M[name]
        tot = sum(C[k]["u_me"] * C[k]["d_p"] for k in KEYS)
        three = sum(C[k]["u_me"] * C[k]["d_p"] for k in ("WOOL", "STRAWBERRY", "MILK"))
        print(f"  {name:9s} all items {tot:+,.0f}/game ; wool+straw+milk {three:+,.0f}/game")

    Path(ROOT / "data" / f"pi-analysis-{args.ref}.json").write_text(
        json.dumps({"n": len(games),
                    "windows": {k: {kk: vv for kk, vv in v.items()}
                                for k, v in M.items()}}, indent=1, default=str))
    print(f"\nwrote data/pi-analysis-{args.ref}.json")


if __name__ == "__main__":
    main()
