#!/usr/bin/env python
"""Task 36: single-change variants on the wool/strawberry price channel + mechanism probe."""
import hashlib, json, subprocess, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import build_race as BR
import build_composite_layers as B

SHEP = ROOT / "data/cand/the-shepherds-ledger-herd-safe-sovereign-extracted-main.py"
BASE = "data/candidate/shep_milk/main.py"
OUT = ROOT / "data" / "candidate"
PANELS = [("p1", "10800-10829"), ("p2", "10900-10929")]

# --- add a fraction-of-base price gate to the forward layer (monkeypatched into FWD_LIB)
OLD1 = '        min_price = float(cfg.get("forward_min_price", 2) or 0)\n'
NEW1 = OLD1 + ('        fracs = cfg.get("forward_min_frac_by_item") or {}\n'
               '        _BASE = {"WOOL": 200, "STRAWBERRY": 120, "MILK": 160, "WHEAT": 25, "CARROT": 35,\n'
               '                 "TOMATO": 60, "MELON": 250, "EGG": 50, "FERTILIZER": 100}\n')
OLD2 = '            if int(view.prices.get(item, 0)) < min_price:\n'
NEW2 = ('            if int(view.prices.get(item, 0)) < max(min_price, float(fracs.get(item, 0) or 0)\n'
        '                                                       * _BASE.get(item, 0)):\n')
assert OLD1 in B.FWD_LIB and OLD2 in B.FWD_LIB
B.FWD_LIB = B.FWD_LIB.replace(OLD1, NEW1).replace(OLD2, NEW2)

RACE = {"race_layout": 1, "race_hyp": "clone", "race_hook": "outer",
        "race_items": ["MILK", "WOOL", "STRAWBERRY", "MELON"]}
FWD = {"forward_items": ["WOOL", "STRAWBERRY", "MILK"], "forward_drain": True,
       "forward_start_by_item": {"STRAWBERRY": 312, "MILK": 312}}
def fwd(**kw):
    d = dict(FWD); d.update(kw); return d
V = {
    "shep_v_s0":     (RACE, fwd(forward_start_by_item={"STRAWBERRY": 0, "MILK": 312})),
    "shep_v_s168":   (RACE, fwd(forward_start_by_item={"STRAWBERRY": 168, "MILK": 312})),
    "shep_v_frac06": (RACE, fwd(forward_min_frac_by_item={"WOOL": 0.6, "STRAWBERRY": 0.6})),
    "shep_v_frac08": (RACE, fwd(forward_min_frac_by_item={"WOOL": 0.8, "STRAWBERRY": 0.8})),
    "shep_v_cap05":  (RACE, fwd(forward_drain_mult=0.5)),
    "shep_v_cap2":   (RACE, fwd(forward_drain_mult=2.0)),
    "shep_v_racece": ({**RACE, "race_items": ["MILK", "WOOL", "STRAWBERRY", "CARROT", "EGG"]}, fwd()),
    "shep_v_racem":  ({**RACE, "race_items": ["MILK", "WOOL", "STRAWBERRY"]}, fwd()),
    "shep_v_ctl":    (RACE, fwd(forward_min_frac_by_item={"WOOL": 0.0, "STRAWBERRY": 0.0})),
}
ALIAS = {"shep_v_ctl": "shep_v_frac06"}

def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
print("building variants...", flush=True)
built = {}
for name, (race, fw) in V.items():
    r = BR.build(race, name + "_raceonly", out_root=OUT, base_path=SHEP, outer_prefix="_clr")
    B.check_collisions(SHEP.read_text(), r.read_text())
    p = B.build_fwd(fw, name, base_path=r, out_root=OUT)
    built[name] = p
print("reference base sha:", sha(ROOT / BASE))

SMOKE = ("import sys\nfrom pathlib import Path\nfrom kaggle_environments import make\n"
         "p=sys.argv[1]; ns={'__name__':'m'}; exec(compile(Path(p).read_text(),p,'exec'),ns)\n"
         "e=make('kaggriculture',configuration={'episodeSteps':720,'seed':10800}); e.run([ns['agent'],ns['agent']])\n"
         "d=getattr(ns.get('_IMPL'),'chassis',None)\n"
         "errs={k:v for k,v in (d.diagnostics if d else {}).items() if v and 'error' in k or k.endswith('fallbacks')}\n"
         "print('SMOKE', [str(e.steps[-1][i]['status']) for i in (0,1)], [float(e.steps[-1][i]['reward'] or 0) for i in (0,1)], 'ERR', errs)\n")
print("\n=== SMOKE ===")
for name, p in built.items():
    r = subprocess.run([".venv/bin/python", "-c", SMOKE, str(p.relative_to(ROOT))], cwd=ROOT, capture_output=True, text=True, timeout=900)
    print(f"  {name:14} {(r.stdout or r.stderr).strip().splitlines()[-1][:150] if (r.stdout or r.stderr).strip() else 'FAIL'}")

print("\n=== DUELS vs shep_milk ===")
res = {}
for name, p in built.items():
    for panel, seeds in PANELS:
        o = OUT / f"duel-t36-{name}-{panel}.json"
        if not o.exists():
            subprocess.run([".venv/bin/python", "scripts/ab_duel.py", "--cand", str(p.relative_to(ROOT)),
                            "--base", BASE, "--seeds", seeds, "--label", name, "--out", str(o.relative_to(ROOT))],
                           cwd=ROOT, capture_output=True, text=True)
        if o.exists():
            d = json.loads(o.read_text()); res.setdefault(name, {})[panel] = d
            print(f"  {name:14} {panel} d={d['delta']:+,.0f} t={d['t']:+.2f} W-L {d['wins']}-{d['losses']} "
                  f"wallet {round(d['cand_wallet'])}/{round(d['base_wallet'])} exc {d['cand_exceptions']} err {d['errors']}", flush=True)
print("\n=== BAR (d>0, t>=3 both panels) ===")
for name, dd in res.items():
    if set(dd) == {"p1", "p2"}:
        a, b = dd["p1"], dd["p2"]
        go = a["delta"] > 0 and b["delta"] > 0 and a["t"] >= 3 and b["t"] >= 3
        print(f"  {name:14} {'GO' if go else 'no-go'}  p1 {a['delta']:+,.0f} (t={a['t']:+.2f})  p2 {b['delta']:+,.0f} (t={b['t']:+.2f})")
    else:
        print(f"  {name:14} incomplete")
json.dump({k: {p: v for p, v in d.items()} for k, d in res.items()},
          open(ROOT / "data" / "t36-variants.json", "w"), default=str)
