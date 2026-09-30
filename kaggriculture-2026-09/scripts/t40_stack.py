#!/usr/bin/env python
"""Task 40 step 4: stack our market layers on the winning frontier base and measure vs cap24."""
import hashlib, json, subprocess, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import build_race as BR
import build_composite_layers as B
WIN = ROOT / "data/cand/31415926535897932384626433832795058202884197169399-extracted-main.py"
BASE = "data/candidate/shep_v_cap24/main.py"
OUT = ROOT / "data" / "candidate"
NAME = "pi_stack"
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
FWD = {"forward_items": ["WOOL", "STRAWBERRY", "MILK"], "forward_drain": True,
       "forward_start_by_item": {"STRAWBERRY": 312, "MILK": 312}, "forward_drain_mult": 24.0}
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
try:
    race = BR.build(RACE, NAME + "_raceonly", out_root=OUT, base_path=WIN, outer_prefix="_clr")
    B.check_collisions(WIN.read_text(), race.read_text())
    full = B.build_fwd(FWD, NAME, base_path=race, out_root=OUT)
    ctl = B.build_fwd({**FWD, "forward_items": None}, NAME + "_fwdctl", base_path=race, out_root=OUT)
    print("STACK sha:", sha(full)); print("RACEONLY sha:", sha(race)); print("FWDCTL sha:", sha(ctl))
except Exception as exc:
    print("STACK BUILD FAILED:", type(exc).__name__, exc); sys.exit(0)
SMOKE = ("import sys\nfrom pathlib import Path\nfrom kaggle_environments import make\n"
         "p=sys.argv[1]; ns={'__name__':'m'}; exec(compile(Path(p).read_text(),p,'exec'),ns)\n"
         "e=make('kaggriculture',configuration={'episodeSteps':720,'seed':13000}); e.run([ns['agent'],ns['agent']])\n"
         "d=getattr(ns.get('_IMPL'),'chassis',None)\n"
         "print('SMOKE',[str(e.steps[-1][i]['status']) for i in (0,1)],"
         "{k:v for k,v in (d.diagnostics if d else {}).items() if v and ('error' in k or k.endswith('fallbacks'))})\n")
for lbl, p in (("STACK", full), ("FWD-OFF-CTL", ctl)):
    r = subprocess.run([".venv/bin/python", "-c", SMOKE, str(p.relative_to(ROOT))], cwd=ROOT, capture_output=True, text=True, timeout=900)
    print(f"{lbl}: {(r.stdout or r.stderr).strip().splitlines()[-1][:160]}")
for panel, seeds in (("p1", "13000-13029"), ("p2", "13100-13129")):
    o = OUT / f"duel-t40-pi_stack-{panel}.json"
    subprocess.run([".venv/bin/python", "scripts/ab_duel.py", "--cand", str(full.relative_to(ROOT)),
                    "--base", BASE, "--seeds", seeds, "--label", NAME, "--out", str(o.relative_to(ROOT))],
                   cwd=ROOT, capture_output=True, text=True)
    d = json.loads(o.read_text())
    print(f"STACK {panel} vs cap24: d={d['delta']:+,.0f} t={d['t']:+.2f} W-L {d['wins']}-{d['losses']} "
          f"wallet {round(d['cand_wallet'])}/{round(d['base_wallet'])} exc {d['cand_exceptions']} err {d['errors']}")
o = OUT / "duel-t40-fwdctl.json"
subprocess.run([".venv/bin/python", "scripts/ab_duel.py", "--cand", str(ctl.relative_to(ROOT)),
                "--base", str(race.relative_to(ROOT)), "--seeds", "13000-13009", "--label", "fwdctl",
                "--out", str(o.relative_to(ROOT))], cwd=ROOT, capture_output=True, text=True)
c = json.loads(o.read_text())
print(f"CONTROL fwd-off vs race-only: delta={c['delta']:+.1f} t={c['t']:+.2f} errors={c['errors']} exc={c['cand_exceptions']}")
subprocess.run([".venv/bin/python", "scripts/composite_timing.py", "--agents", str(full.relative_to(ROOT)),
                "--out", "data/candidate/timing-t40.json"], cwd=ROOT)
