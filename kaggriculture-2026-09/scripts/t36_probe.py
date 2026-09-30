#!/usr/bin/env python
"""Mechanism check: does the winning variant move WOOL/STRAWBERRY units and realised price?"""
import collections, json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
def load(p):
    ns = {"__name__": "m"}; exec(compile(Path(p).read_text(), p, "exec"), ns); return ns["agent"]
def run(cand, base, seeds):
    import kaggle_environments.envs.kaggriculture.kaggriculture as K
    from kaggle_environments import make
    C, B = load(cand), load(base)
    tot = {0: collections.defaultdict(lambda: [0, 0.0]), 1: collections.defaultdict(lambda: [0, 0.0])}
    res = []
    orig, cur = K._commit_unit, {}
    o_pm = K._process_market
    def pm(state, env):
        cur["farms"] = state[0].observation.farms
        return o_pm(state, env)
    def commit(op, item, price, farm, private, market, shed=100):
        pid = next((i for i, f in enumerate(cur.get("farms") or []) if f is farm), -1)
        ok = orig(op, item, price, farm, private, market, shed)
        if ok and op == "SELL" and str(item) in ("WOOL", "STRAWBERRY"):
            tot[pid][str(item)][0] += 1; tot[pid][str(item)][1] += float(price)
        return ok
    K._commit_unit, K._process_market = commit, pm
    try:
        for s in seeds:
            for swap in (0, 1):
                e = make("kaggriculture", configuration={"episodeSteps": 720, "seed": s})
                e.run([C, B] if swap == 0 else [B, C])
                me, op = (0, 1) if swap == 0 else (1, 0)
                res.append(float(e.steps[-1][me]["reward"] or 0) - float(e.steps[-1][op]["reward"] or 0))
    finally:
        K._commit_unit, K._process_market = orig, o_pm
    return tot, res
tot, res = run(sys.argv[1], sys.argv[2], [int(x) for x in sys.argv[3].split(",")])
print(f"signed margins (candidate seat0-positive): {[round(x) for x in res]}")
print(f"mean margin {sum(res)/len(res):+,.0f}")
for pid, label in ((0, "seat0"), (1, "seat1")):
    for item in ("WOOL", "STRAWBERRY"):
        u, r = tot[pid][item]
        print(f"  {label} {item:11} units {u:6d}  revenue {r:11,.0f}  avg realised price {r/u if u else 0:6.2f}")
