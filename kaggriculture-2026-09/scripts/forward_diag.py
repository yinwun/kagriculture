#!/usr/bin/env python
"""Mechanism diagnostic for the sell-forward layer.

Reports, per player, on one seed:
  * wool units sold in days 0-23 (the high-price window) vs days 24-29 (the
    collapse) — the layer must move units INTO the early window for the wallet gain
    to be the claimed mechanism;
  * executed units and the mean realised price per unit by product (the
    frontier-vs-champion comparison from REPORT-herd-swap.md §4);
  * the run diagnostics (forward_orders/units, layer_fallbacks).

Usage: .venv/bin/python scripts/forward_diag.py --cand data/forward/wool/main.py --seed 9009
"""
from __future__ import annotations

import argparse
import collections
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import lockstep  # noqa: E402
import race_trace  # noqa: E402

PRODUCTS = list(lockstep.PRODUCTS)


def run(cand_path, base_path, seed):
    from kaggle_environments import make

    cand = {"__name__": "d_cand"}
    exec(compile(Path(cand_path).read_text(), str(cand_path), "exec"), cand)
    base = {"__name__": "d_base"}
    exec(compile(Path(base_path).read_text(), str(base_path), "exec"), base)

    seen = {0: {}, 1: {}}

    def wrap(agent, seat):
        def fn(obs):
            act = agent(obs)
            seen[seat][int(obs["step"])] = {
                "inv": {k: int(v) for k, v in dict(obs.market.inventory).items()},
                "shed": {k: int(v) for k, v in dict(obs.private.shed).items()},
                "prices": {k: int(v) for k, v in dict(obs.market.prices).items()},
            }
            return act
        return fn

    env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": seed})
    env.run([wrap(cand["agent"], 0), wrap(base["agent"], 1)])
    return cand, env, seen


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cand", default=str(ROOT / "data" / "forward" / "wool" / "main.py"))
    ap.add_argument("--base", default=str(ROOT / "data" / "tapeopt" / "rgcs" / "main.py"))
    ap.add_argument("--seeds", default="9009,9005")
    args = ap.parse_args()
    for seed in [int(x) for x in args.seeds.split(",")]:
        ns, env, seen = run(args.cand, args.base, seed)
        final = [float(env.steps[-1][i]["reward"] or 0) for i in (0, 1)]
        print(f"=== seed {seed}: cand {final[0]:,.0f} base {final[1]:,.0f} "
              f"delta {final[0]-final[1]:+,.0f}")
        steps = sorted(seen[0])
        for seat, name in ((0, "CAND"), (1, "BASE")):
            acts = [env.steps[t][seat].get("action") or {} for t in range(len(env.steps))]
            early = late = 0
            per = {it: [0, 0.0] for it in PRODUCTS}
            for t in steps:
                src = seen[seat][t]
                m = acts[t].get("market") or []
                for it in PRODUCTS:
                    orders = [o for o in m if isinstance(o, list) and len(o) >= 3
                              and o[0] == "SELL" and o[1] == it]
                    if not orders:
                        continue
                    n = sum(max(0, int(o[2])) for o in orders)
                    n = min(n, max(0, src["shed"].get(it, 0)))
                    idx = src["inv"].get(it, 10000)
                    for _ in range(n):
                        pr = lockstep.market_price(it, idx)
                        per[it][0] += 1
                        per[it][1] += pr
                        if it == "WOOL":
                            if t // 24 <= 23:
                                early += 1
                            else:
                                late += 1
                        if pr > 1:
                            idx += 1
            print(f"   {name}: WOOL early(d0-23) {early:4d} late(d24-29) {late:4d}")
            top = sorted(((it, v[0], v[1]) for it, v in per.items() if v[0]),
                         key=lambda r: -r[2])[:5]
            for it, u, rev in top:
                print(f"      {it:11s} units {u:5d} revenue {rev:9,.0f} mean {rev/max(1,u):6.2f}")
        d = ns["_IMPL"].chassis.diagnostics
        print(f"   layer: forward_orders {d.get('forward_orders')} forward_units "
              f"{d.get('forward_units')} layer_fallbacks {d.get('layer_fallbacks')} "
              f"entry_fallbacks {d.get('entry_fallbacks')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
