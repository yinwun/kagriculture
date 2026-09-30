#!/usr/bin/env python
"""Task 37: sweep forward_drain_mult above 2.0 vs the current best cap2."""
import hashlib, json, subprocess, sys, collections
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import build_race as BR
import build_composite_layers as B
SHEP = ROOT / "data/cand/the-shepherds-ledger-herd-safe-sovereign-extracted-main.py"
BEST = "data/candidate/shep_v_cap2/main.py"
OUT = ROOT / "data" / "candidate"
PANELS = [("p1", "11000-11029"), ("p2", "11100-11129")]
# same FWD_LIB patch as Task 36 (fraction-of-base gate), so cap2 reproduces byte-identically
OLD1 = '        min_price = float(cfg.get("forward_min_price", 2) or 0)\n'
NEW1 = OLD1 + ('        fracs = cfg.get("forward_min_frac_by_item") or {}\n'
               '        _BASE = {"WOOL": 200, "STRAWBERRY": 120, "MILK": 160, "WHEAT": 25, "CARROT": 35,\n'
               '                 "TOMATO": 60, "MELON": 250, "EGG": 50, "FERTILIZER": 100}\n')
OLD2 = '            if int(view.prices.get(item, 0)) < min_price:\n'
NEW2 = ('            if int(view.prices.get(item, 0)) < max(min_price, float(fracs.get(item, 0) or 0)\n'
        '                                                       * _BASE.get(item, 0)):\n')
B.FWD_LIB = B.FWD_LIB.replace(OLD1, NEW1).replace(OLD2, NEW2)
RACE = {"race_layout": 1, "race_hyp": "clone", "race_hook": "outer",
        "race_items": ["MILK", "WOOL", "STRAWBERRY", "MELON"]}
def fwd(mult):
    return {"forward_items": ["WOOL", "STRAWBERRY", "MILK"], "forward_drain": True,
            "forward_start_by_item": {"STRAWBERRY": 312, "MILK": 312}, "forward_drain_mult": mult}
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
built = {}
print("building...", flush=True)
for mult, name in ((2.0, "shep_v_cap2_ctl"), (3.0, "shep_v_cap3"), (4.0, "shep_v_cap4"),
                   (6.0, "shep_v_cap6"), (8.0, "shep_v_cap8")):
    r = BR.build(RACE, name + "_raceonly", out_root=OUT, base_path=SHEP, outer_prefix="_clr")
    B.check_collisions(SHEP.read_text(), r.read_text())
    built[name] = B.build_fwd(fwd(mult), name, base_path=r, out_root=OUT)
ctl = ROOT / "data" / "candidate" / "shep_v_cap2_ctl" / "main.py"
print(f"CONTROL byte-identity vs committed cap2: {sha(ctl) == sha(ROOT / BEST)}")
print(f"cap2 sha {sha(ROOT / BEST)[:16]}  ctl sha {sha(ctl)[:16]}")
SMOKE = ("import sys\nfrom pathlib import Path\nfrom kaggle_environments import make\n"
         "p=sys.argv[1]; ns={'__name__':'m'}; exec(compile(Path(p).read_text(),p,'exec'),ns)\n"
         "e=make('kaggriculture',configuration={'episodeSteps':720,'seed':11000}); e.run([ns['agent'],ns['agent']])\n"
         "d=getattr(ns.get('_IMPL'),'chassis',None)\n"
         "errs={k:v for k,v in (d.diagnostics if d else {}).items() if v and ('error' in k or k.endswith('fallbacks'))}\n"
         "print('SMOKE', [str(e.steps[-1][i]['status']) for i in (0,1)], 'ERR', errs)\n")
print("\n=== SMOKE ===")
for name, p in built.items():
    r = subprocess.run([".venv/bin/python", "-c", SMOKE, str(p.relative_to(ROOT))], cwd=ROOT,
                       capture_output=True, text=True, timeout=900)
    line = (r.stdout or r.stderr).strip().splitlines()
    print(f"  {name:18} {line[-1][:120] if line else 'FAIL'}")
print("\n=== DUELS vs cap2 (mult 2.0) ===")
res = {}
for name, p in built.items():
    if name.endswith("_ctl"):
        continue
    for panel, seeds in PANELS:
        o = OUT / f"duel-t37-{name}-{panel}.json"
        if not o.exists():
            subprocess.run([".venv/bin/python", "scripts/ab_duel.py", "--cand", str(p.relative_to(ROOT)),
                            "--base", BEST, "--seeds", seeds, "--label", name, "--out", str(o.relative_to(ROOT))],
                           cwd=ROOT, capture_output=True, text=True)
        if o.exists():
            d = json.loads(o.read_text()); res.setdefault(name, {})[panel] = d
            print(f"  {name:18} {panel} d={d['delta']:+,.0f} t={d['t']:+.2f} W-L {d['wins']}-{d['losses']} "
                  f"wallet {round(d['cand_wallet'])}/{round(d['base_wallet'])} exc {d['cand_exceptions']} err {d['errors']}", flush=True)
print("\n=== BAR (d>0, t>=3 both panels) ===")
best = None
for name, dd in res.items():
    if set(dd) == {"p1", "p2"}:
        a, b = dd["p1"], dd["p2"]
        go = a["delta"] > 0 and b["delta"] > 0 and a["t"] >= 3 and b["t"] >= 3
        if go and (best is None or min(a["delta"], b["delta"]) > best[1]):
            best = (name, min(a["delta"], b["delta"]))
        print(f"  {name:18} {'GO' if go else 'no-go'}  p1 {a['delta']:+,.0f} (t={a['t']:+.2f})  p2 {b['delta']:+,.0f} (t={b['t']:+.2f})")
print(f"\nPEAK: {best[0] if best else 'none clears'}")
# control duel: ctl (mult 2.0 rebuilt) vs committed cap2 must be exactly 0
subprocess.run([".venv/bin/python", "scripts/ab_duel.py", "--cand", "data/candidate/shep_v_cap2_ctl/main.py",
                "--base", BEST, "--seeds", "11000-11009", "--label", "ctl",
                "--out", "data/candidate/duel-t37-ctl.json"], cwd=ROOT, capture_output=True, text=True)
c = json.loads((ROOT / "data/candidate/duel-t37-ctl.json").read_text())
print(f"CONTROL duel: delta={c['delta']:+.1f} t={c['t']:+.2f} errors={c['errors']} exc={c['cand_exceptions']}")
# mechanism probe for the winner
if best:
    sys.path.insert(0, str(ROOT / "scripts"))
    import importlib
    import kaggle_environments.envs.kaggriculture.kaggriculture as K
    from kaggle_environments import make
    def load(p):
        ns = {"__name__": "m"}; exec(compile(Path(p).read_text(), p, "exec"), ns); return ns["agent"]
    C = load(ROOT / "data" / "candidate" / best[0] / "main.py"); Bb = load(ROOT / BEST)
    tot = {0: collections.defaultdict(lambda: [0, 0.0]), 1: collections.defaultdict(lambda: [0, 0.0])}
    cur = {}; orig, o_pm = K._commit_unit, K._process_market
    def pm(state, env):
        cur["farms"] = state[0].observation.farms; return o_pm(state, env)
    def commit(op, item, price, farm, private, market, shed=100):
        pid = next((i for i, f in enumerate(cur.get("farms") or []) if f is farm), -1)
        ok = orig(op, item, price, farm, private, market, shed)
        if ok and op == "SELL" and str(item) in ("WOOL", "STRAWBERRY"):
            tot[pid][str(item)][0] += 1; tot[pid][str(item)][1] += float(price)
        return ok
    K._commit_unit, K._process_market = commit, pm
    marg = []
    try:
        for s in range(11000, 11008):
            e = make("kaggriculture", configuration={"episodeSteps": 720, "seed": s}); e.run([C, Bb])
            marg.append(float(e.steps[-1][0]["reward"] or 0) - float(e.steps[-1][1]["reward"] or 0))
    finally:
        K._commit_unit, K._process_market = orig, o_pm
    print(f"\n=== MECHANISM ({best[0]} seat0 vs cap2 seat1, 8 games): mean margin {sum(marg)/len(marg):+,.0f}")
    for pid, label in ((0, best[0][:14]), (1, "cap2 ")):
        for it in ("WOOL", "STRAWBERRY"):
            u, r = tot[pid][it]
            print(f"  {label:15} {it:11} units {u:6d} revenue {r:11,.0f} avg realised price {r/u if u else 0:6.2f}")
