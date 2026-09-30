#!/usr/bin/env python
"""Task 33 step 3: stack OUR market layers (race + wool + late strawberry) on the shepherds base.

Only to be run if the candidate clears the pre-registered bar.  Builds outermost-wrapper
variants from the shepherds extracted source, byte-identity control, smoke, then duels our
current best comp_straw on the two unused panels.
"""
import hashlib, json, subprocess, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import build_race as BR
import build_composite_layers as B

SHEP = ROOT / "data/cand/the-shepherds-ledger-herd-safe-sovereign-extracted-main.py"
NAME = "shep_straw"
OUT = ROOT / "data" / "candidate"

def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()

FWD = {**B.FWD_WOOL, "forward_items": ["WOOL", "STRAWBERRY"],
       "forward_start_by_item": {"STRAWBERRY": 312}}

print("building stack on the shepherds base...")
race = BR.build(B.RACE_PREM, NAME + "_raceonly", out_root=OUT, base_path=SHEP, outer_prefix="_clr")
B.check_collisions(SHEP.read_text(), race.read_text())
full = B.build_fwd(FWD, NAME, base_path=race, out_root=OUT)
print("payload sha256:", sha(full))
# knobs-off control: same source, forward layer disabled -> must be behaviour-identical to the
# race-only build (used below as the control pair)
ctl = B.build_fwd({"forward_items": None}, NAME + "_ctl", base_path=race, out_root=OUT)
print("control sha256:", sha(ctl))
code = ("import sys\nfrom pathlib import Path\nfrom kaggle_environments import make\n"
        "p=sys.argv[1]; ns={'__name__':'m'}\n"
        "exec(compile(Path(p).read_text(),p,'exec'),ns)\n"
        "e=make('kaggriculture',configuration={'episodeSteps':720,'seed':10200}); e.run([ns['agent'],ns['agent']])\n"
        "print('SMOKE', [str(e.steps[-1][i]['status']) for i in (0,1)], [float(e.steps[-1][i]['reward'] or 0) for i in (0,1)],\n"
        "      ns['_IMPL'].chassis.diagnostics if hasattr(ns.get('_IMPL'),'chassis') else {})\n")
for label, path in (("STACK", full), ("CONTROL(forward off)", ctl)):
    r = subprocess.run([".venv/bin/python", "-c", code, str(path)], cwd=ROOT, capture_output=True, text=True, timeout=900)
    print(f"{label}: {r.stdout.strip()[-400:] or r.stderr.strip()[-200:]}")
for label, seeds, out in (("p3", "10200-10259", "data/candidate/duel-t33-stack-p3.json"),
                          ("p4", "10300-10359", "data/candidate/duel-t33-stack-p4.json")):
    subprocess.run([".venv/bin/python", "scripts/ab_duel.py", "--cand", str(full.relative_to(ROOT)),
                    "--base", "data/composite/comp_straw/main.py", "--seeds", seeds,
                    "--label", NAME, "--out", out], cwd=ROOT, capture_output=True, text=True)
    d = json.loads((ROOT / out).read_text())
    print(f"STACK {label} vs comp_straw: d={d['delta']:+,.0f} t={d['t']:+.2f} W-L {d['wins']}-{d['losses']} "
          f"wire {round(d['cand_wallet'])}/{round(d['base_wallet'])} exc {d['cand_exceptions']}/{d['base_exceptions']} err {d['errors']}")
    print(f"   counters cand={d['cand_diag']}")
# control duel: knobs-off build vs race-only build must be exactly 0
subprocess.run([".venv/bin/python", "scripts/ab_duel.py", "--cand", str(ctl.relative_to(ROOT)),
                "--base", str(race.relative_to(ROOT)), "--seeds", "10200-10209",
                "--label", "ctl", "--out", "data/candidate/duel-t33-ctl.json"], cwd=ROOT, capture_output=True, text=True)
c = json.loads((ROOT / "data/candidate/duel-t33-ctl.json").read_text())
print(f"CONTROL (knobs off) delta={c['delta']:+.0f} t={c['t']:+.2f} errors={c['errors']} exc={c['cand_exceptions']}")
subprocess.run([".venv/bin/python", "scripts/composite_timing.py", "--agents", str(full.relative_to(ROOT)),
                "--out", "data/candidate/timing-t33.json"], cwd=ROOT)
