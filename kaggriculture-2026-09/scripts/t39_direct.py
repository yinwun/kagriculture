#!/usr/bin/env python
"""Task 39: direct end-to-end contrast of cap24 / cap8 vs shep_straw (x1)."""
import collections, difflib, json, statistics as st, subprocess, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
X1 = "data/candidate/shep_straw/main.py"
ARMS = {"cap24": "data/candidate/shep_v_cap24/main.py", "cap8": "data/candidate/shep_v_cap8/main.py"}
PANELS = [("p1", "12000-12029"), ("p2", "12100-12129")]

print("=== file-level control: only the mult scalar differs from shep_straw ===")
a = (ROOT / X1).read_text().splitlines()
for arm, p in ARMS.items():
    b = (ROOT / p).read_text().splitlines()
    d = [l for l in difflib.unified_diff(a, b, lineterm="", n=0) if l.startswith(("+", "-")) and not l.startswith(("+++", "---"))]
    print(f"  {arm}: {len(d)} differing lines -> {d[:4]}")

print("\n=== direct duels vs shep_straw (x1) ===")
res = {}
for arm, p in ARMS.items():
    for panel, seeds in PANELS:
        o = ROOT / "data" / "candidate" / f"duel-t39-{arm}-vs-x1-{panel}.json"
        if not o.exists():
            subprocess.run([".venv/bin/python", "scripts/ab_duel.py", "--cand", p, "--base", X1,
                            "--seeds", seeds, "--label", arm, "--out", str(o.relative_to(ROOT))],
                           cwd=ROOT, capture_output=True, text=True)
        if o.exists():
            d = json.loads(o.read_text()); res.setdefault(arm, {})[panel] = d
            pct = 100 * d["delta"] / d["base_wallet"]
            print(f"  {arm:6} {panel} d={d['delta']:+,.0f} ({pct:+.2f}%) t={d['t']:+.2f} W-L {d['wins']}-{d['losses']} "
                  f"wallet {round(d['cand_wallet'])}/{round(d['base_wallet'])} exc {d['cand_exceptions']} err {d['errors']}", flush=True)
print("\n=== direct vs transitive ===")
for arm, dd in res.items():
    pcts, dels = [], []
    for panel, _ in PANELS:
        if panel in dd:
            d = dd[panel]; pcts.append(100 * d["delta"] / d["base_wallet"]); dels += [r["delta"] for r in d["per_seed"]]
    if pcts:
        print(f"  {arm:6} mean direct effect {st.mean(pcts):+.2f}% of wallet across panels")
    if len(dels) > 1:
        m = st.mean(dels); se = st.stdev(dels) / len(dels) ** 0.5
        lo, hi = m - 1.96 * se, m + 1.96 * se
        print(f"         pooled over {len(dels)} towns: {m:+,.0f} coins/game  t={m/se:+.2f}  "
              f"95% CI [{lo:+,.0f}, {hi:+,.0f}] -> [{145*lo/99000:+.0f}, {145*hi/99000:+.0f}] rating pts")
    print(f"         positive towns {sum(1 for x in dels if x>0)}/{len(dels)}")

# mechanism probes (fixed orientation: seat0 = arm, seat1 = x1), with MILK
import kaggle_environments.envs.kaggriculture.kaggriculture as K
from kaggle_environments import make
def load(p):
    ns = {"__name__": "m"}; exec(compile(Path(p).read_text(), p, "exec"), ns); return ns["agent"]
def probe(armpath, seeds=range(12000, 12008)):
    C, B = load(armpath), load(X1)
    tot = {0: collections.defaultdict(lambda: [0, 0.0]), 1: collections.defaultdict(lambda: [0, 0.0])}
    cur = {}; orig, o_pm = K._commit_unit, K._process_market
    def pm(state, env):
        cur["farms"] = state[0].observation.farms; return o_pm(state, env)
    def commit(op, item, price, farm, private, market, shed=100):
        pid = next((i for i, f in enumerate(cur.get("farms") or []) if f is farm), -1)
        ok = orig(op, item, price, farm, private, market, shed)
        if ok and op == "SELL" and str(item) in ("WOOL", "STRAWBERRY", "MILK"):
            tot[pid][str(item)][0] += 1; tot[pid][str(item)][1] += float(price)
        return ok
    K._commit_unit, K._process_market = commit, pm
    marg = []
    try:
        for s in seeds:
            e = make("kaggriculture", configuration={"episodeSteps": 720, "seed": s}); e.run([C, B])
            marg.append(float(e.steps[-1][0]["reward"] or 0) - float(e.steps[-1][1]["reward"] or 0))
    finally:
        K._commit_unit, K._process_market = orig, o_pm
    return tot, marg
print("\n=== mechanism (seat0 = arm, seat1 = x1; 8 games each) ===")
for arm, p in ARMS.items():
    tot, marg = probe(str(ROOT / p))
    print(f"  {arm} mean margin {st.mean(marg):+,.0f}")
    for pid, label in ((0, arm), (1, "x1")):
        for it in ("WOOL", "STRAWBERRY", "MILK"):
            u, r = tot[pid][it]
            print(f"    {label:6} {it:11} units {u:6d} revenue {r:11,.0f} avg realised price {r/u if u else 0:6.2f}")
json.dump({k: v for k, v in res.items()}, open(ROOT / "data" / "t39-direct.json", "w"), default=str)
