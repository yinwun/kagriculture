#!/usr/bin/env python
"""Task 41: sweep our forward-layer parameters ON THE NEW V78 BASE.

Rationale: `pi_stack` (V78 base + race + forward at drain_mult=24) is the strongest build we
have ever measured, but every parameter sweep in this project was done on the OLD shepherds
base. The drain multiplier is exactly the knob whose optimum could move when the base changes
(the base's own market layers change how much the town drains between our releases). So sweep
it on the new base before spending any of the remaining submission slots.

Protocol (doctrine): screen every variant on ONE fresh panel against the current champion,
then CONFIRM only the top variant on a SECOND fresh unused panel. Never trust a single panel.

Usage: .venv/bin/python scripts/t41_pi_sweep.py
"""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import build_race as BR  # noqa: E402
import build_composite_layers as B  # noqa: E402

OUT = ROOT / "data" / "candidate"
RACE_DIR = OUT / "pi_stack_raceonly" / "main.py"   # build_fwd takes a FILE, not a directory
CHAMP = OUT / "pi_stack" / "main.py"          # drain_mult = 24.0, the submitted build
SCREEN = "15000-15029"
CONFIRM = "15100-15129"

# same inert min-price patch that produced the champion, so builds are byte-comparable
OLD1 = '        min_price = float(cfg.get("forward_min_price", 2) or 0)\n'
NEW1 = OLD1 + ('        fracs = cfg.get("forward_min_frac_by_item") or {}\n'
               '        _BASE = {"WOOL": 200, "STRAWBERRY": 120, "MILK": 160, "WHEAT": 25, "CARROT": 35,\n'
               '                 "TOMATO": 60, "MELON": 250, "EGG": 50, "FERTILIZER": 100}\n')
OLD2 = '            if int(view.prices.get(item, 0)) < min_price:\n'
NEW2 = ('            if int(view.prices.get(item, 0)) < max(min_price, float(fracs.get(item, 0) or 0)\n'
        '                                                       * _BASE.get(item, 0)):\n')
B.FWD_LIB = B.FWD_LIB.replace(OLD1, NEW1).replace(OLD2, NEW2)

BASE_FWD = {"forward_items": ["WOOL", "STRAWBERRY", "MILK"], "forward_drain": True,
            "forward_start_by_item": {"STRAWBERRY": 312, "MILK": 312}}
MULTS = [1.0, 2.0, 8.0, 12.0, 48.0]

SMOKE = ("import sys\nfrom pathlib import Path\nfrom kaggle_environments import make\n"
         "p=sys.argv[1]; ns={'__name__':'m'}; exec(compile(Path(p).read_text(),p,'exec'),ns)\n"
         "e=make('kaggriculture',configuration={'episodeSteps':720,'seed':16000}); e.run([ns['agent'],ns['agent']])\n"
         "d=getattr(ns.get('_IMPL'),'chassis',None)\n"
         "print('SMOKE',[str(e.steps[-1][i]['status']) for i in (0,1)],"
         "{k:v for k,v in (d.diagnostics if d else {}).items() if v and ('error' in k or k.endswith('fallbacks'))})\n")


def duel(cand, base, seeds, label, out):
    subprocess.run([".venv/bin/python", "scripts/ab_duel.py", "--cand", str(cand), "--base", str(base),
                    "--seeds", seeds, "--label", label, "--out", str(out)],
                   cwd=ROOT, capture_output=True, text=True)
    return json.loads(Path(out).read_text())


def main():
    if not RACE_DIR.exists():
        raise SystemExit("race-only intermediate missing; run scripts/t40_stack.py first")
    if not CHAMP.exists():
        raise SystemExit("champion pi_stack missing; run scripts/t40_stack.py first")

    built = []
    for m in MULTS:
        # 24.0 is the champion itself; rebuild it under the same code path as a self-check
        name = f"pi_dm{str(m).replace('.', 'p')}"
        try:
            p = B.build_fwd({**BASE_FWD, "forward_drain_mult": m}, name,
                            base_path=RACE_DIR, out_root=OUT)
        except Exception as exc:  # noqa: BLE001
            print(f"BUILD FAILED {name}: {type(exc).__name__}: {exc}", flush=True)
            continue
        sha = hashlib.sha256(Path(p).read_bytes()).hexdigest()
        r = subprocess.run([".venv/bin/python", "-c", SMOKE, str(p.relative_to(ROOT))],
                           cwd=ROOT, capture_output=True, text=True, timeout=1800)
        last = (r.stdout or r.stderr).strip().splitlines()[-1] if (r.stdout or r.stderr).strip() else "NO OUTPUT"
        print(f"built {p.relative_to(ROOT)} sha256 {sha[:16]} :: {last[:150]}", flush=True)
        built.append((m, p, sha))

    print(f"\n=== SCREEN vs champion pi_stack (drain_mult=24) on {SCREEN} ===", flush=True)
    res = []
    for m, p, sha in built:
        o = OUT / f"duel-t41-{p.parent.name}-screen.json"
        d = duel(p, CHAMP, SCREEN, f"dm{m}", o)
        print(f"  dm={m:<5} d={d['delta']:+9.1f} t={d['t']:+6.2f} W-L {d['wins']}-{d['losses']} "
              f"err={d['errors']} exc={d['cand_exceptions']}", flush=True)
        res.append((d["delta"], d["t"], m, p, sha, d))

    # winner of the screen = best delta among variants that are NOT the champion itself
    cands = [r for r in res if r[2] != 24.0]
    if not cands:
        print("no variants built", flush=True)
        return
    cands.sort(key=lambda r: -r[0])
    d0, t0, m0, p0, sha0, _ = cands[0]
    print(f"\n=== CONFIRM dm={m0} (screen d={d0:+.1f} t={t0:+.2f}) on fresh panel {CONFIRM} ===", flush=True)
    o = OUT / f"duel-t41-dm{m0}-confirm.json"
    d1 = duel(p0, CHAMP, CONFIRM, f"dm{m0}-confirm", o)
    print(f"  dm={m0} confirm: d={d1['delta']:+.1f} t={d1['t']:+.2f} W-L {d1['wins']}-{d1['losses']} "
          f"err={d1['errors']} exc={d1['cand_exceptions']}", flush=True)

    pooled_n = d0 and (60 + 60)
    verdict = ("CLEARS: beats the submitted champion on both panels"
               if d0 > 0 and d1["delta"] > 0 and t0 >= 3 and d1["t"] >= 3
               else "NO EDGE: champion stays")
    summary = {"champion": str(CHAMP.relative_to(ROOT)),
               "champion_sha256": hashlib.sha256(CHAMP.read_bytes()).hexdigest(),
               "screen_panel": SCREEN, "confirm_panel": CONFIRM,
               "variants": [{"drain_mult": m, "path": str(p.relative_to(ROOT)), "sha256": sha,
                             "screen_delta": d["delta"], "screen_t": d["t"],
                             "screen_wl": [d["wins"], d["losses"]], "errors": d["errors"]}
                            for _, _, m, p, sha, d in res],
               "best": {"drain_mult": m0, "sha256": sha0,
                        "confirm_delta": d1["delta"], "confirm_t": d1["t"],
                        "confirm_wl": [d1["wins"], d1["losses"]]},
               "verdict": verdict}
    (OUT / "t41-pi-sweep.json").write_text(json.dumps(summary, indent=2))
    print("\nVERDICT:", verdict, flush=True)
    print("wrote data/candidate/t41-pi-sweep.json", flush=True)


if __name__ == "__main__":
    main()
