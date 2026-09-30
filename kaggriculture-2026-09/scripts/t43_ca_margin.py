#!/usr/bin/env python
"""Task 43: sweep `_CA_MARGIN` (the carrot-swap threshold) on the pi_stack base.

WHY THIS ONE: the whole public frontier rolled `_CA_MARGIN` from -22.0 (our base, V78) to
-15.0 and branded it "V79"/"V85". Measured against our own bare V78 base that rollback is a
REGRESSION (-61, t=-3.23 / -60, t=-1.86). The condition is

    pays_now = 3*(p_carrot - DROP) - 20 > 4*p_wheat - 10 + _CA_MARGIN

so a MORE NEGATIVE margin makes the swap EASIER -- i.e. -22 swaps to carrot more readily than
-15, and that direction measured better. That means the base author's -22 may not be the
optimum, and everything below -22 is completely unexplored. It is the last live knob on this
base: every knob in our own layer stack has been swept to a confirmed optimum.

Protocol (doctrine): screen every variant against the champion on ONE fresh panel, then
CONFIRM only the winner on a SECOND fresh unused panel. A candidate counts as clearing the
bar only with delta > 0 AND t >= 3 on BOTH panels.

Usage: .venv/bin/python scripts/t43_ca_margin.py
"""
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

OUT = ROOT / "data" / "candidate"
CHAMP = OUT / "pi_stack" / "main.py"
ANCHOR = "_CA_MARGIN = -22.0"
# -22.0 is the champion itself and is rebuilt as a self-check; -15.0 is the public rollback
VALUES = [-15.0, -22.0, -30.0, -40.0, -55.0, -70.0]
SCREEN = "18000-18029"
CONFIRM = "18100-18129"

SMOKE = ("import sys\nfrom pathlib import Path\nfrom kaggle_environments import make\n"
         "p=sys.argv[1]; ns={'__name__':'m'}; exec(compile(Path(p).read_text(),p,'exec'),ns)\n"
         "e=make('kaggriculture',configuration={'episodeSteps':720,'seed':19000}); e.run([ns['agent'],ns['agent']])\n"
         "d=getattr(ns.get('_IMPL'),'chassis',None)\n"
         "print('SMOKE',[str(e.steps[-1][i]['status']) for i in (0,1)],"
         "{k:v for k,v in (d.diagnostics if d else {}).items() if v and ('error' in k or k.endswith('fallbacks'))})\n")


def duel(cand, base, seeds, label, out):
    subprocess.run([".venv/bin/python", "scripts/ab_duel.py", "--cand", str(cand), "--base", str(base),
                    "--seeds", seeds, "--label", label, "--out", str(out)],
                   cwd=ROOT, capture_output=True, text=True)
    return json.loads(Path(out).read_text())


def main():
    src = CHAMP.read_text()
    n = src.count(ANCHOR)
    if n != 1:
        raise SystemExit(f"expected exactly one '{ANCHOR}' in the champion, found {n}")
    print(f"champion {CHAMP.relative_to(ROOT)} sha256 "
          f"{hashlib.sha256(CHAMP.read_bytes()).hexdigest()[:16]}, anchor unique", flush=True)

    built = []
    for v in VALUES:
        name = f"pi_ca{str(v).replace('-', 'm').replace('.', 'p')}"
        d = OUT / name
        d.mkdir(parents=True, exist_ok=True)
        p = d / "main.py"
        p.write_text(src.replace(ANCHOR, f"_CA_MARGIN = {v}"))
        sha = hashlib.sha256(p.read_bytes()).hexdigest()
        r = subprocess.run([".venv/bin/python", "-c", SMOKE, str(p.relative_to(ROOT))],
                           cwd=ROOT, capture_output=True, text=True, timeout=1800)
        tail = (r.stdout or r.stderr).strip().splitlines()
        print(f"built {p.relative_to(ROOT)} sha256 {sha[:16]} :: {tail[-1][:140] if tail else 'NO OUTPUT'}", flush=True)
        built.append((v, p, sha))

    print(f"\n=== SCREEN vs champion (CA_MARGIN=-22) on {SCREEN} ===", flush=True)
    res = []
    for v, p, sha in built:
        o = OUT / f"duel-t43-{p.parent.name}-screen.json"
        d = duel(p, CHAMP, SCREEN, f"ca{v}", o)
        print(f"  CA={v:<7} d={d['delta']:+9.1f} t={d['t']:+6.2f} W-L {d['wins']}-{d['losses']} "
              f"err={d['errors']} exc={d['cand_exceptions']}", flush=True)
        res.append((d["delta"], d["t"], v, p, sha, d))

    # never "confirm" the champion against itself; and a byte-identical build is a bug signal
    cands = [r for r in res if r[2] != -22.0]
    if not cands:
        print("no variants built", flush=True)
        return
    cands.sort(key=lambda r: -r[0])
    d0, t0, v0, p0, sha0, _ = cands[0]
    print(f"\n=== CONFIRM CA={v0} (screen d={d0:+.1f} t={t0:+.2f}) on fresh panel {CONFIRM} ===", flush=True)
    o = OUT / f"duel-t43-ca{v0}-confirm.json"
    d1 = duel(p0, CHAMP, CONFIRM, f"ca{v0}-confirm", o)
    print(f"  CA={v0} confirm: d={d1['delta']:+.1f} t={d1['t']:+.2f} W-L {d1['wins']}-{d1['losses']} "
          f"err={d1['errors']} exc={d1['cand_exceptions']}", flush=True)

    clears = d0 > 0 and d1["delta"] > 0 and t0 >= 3 and d1["t"] >= 3
    verdict = (f"CLEARS: CA_MARGIN={v0} beats the champion on both panels" if clears
               else "NO EDGE: champion stays")
    summary = {"champion": str(CHAMP.relative_to(ROOT)),
               "champion_sha256": hashlib.sha256(CHAMP.read_bytes()).hexdigest(),
               "anchor": ANCHOR, "screen_panel": SCREEN, "confirm_panel": CONFIRM,
               "variants": [{"ca_margin": v, "path": str(p.relative_to(ROOT)), "sha256": sha,
                             "screen_delta": d["delta"], "screen_t": d["t"],
                             "screen_wl": [d["wins"], d["losses"]], "errors": d["errors"]}
                            for _, _, v, p, sha, d in res],
               "best": {"ca_margin": v0, "sha256": sha0, "confirm_delta": d1["delta"],
                        "confirm_t": d1["t"], "confirm_wl": [d1["wins"], d1["losses"]]},
               "verdict": verdict}
    (OUT / "t43-ca-margin.json").write_text(json.dumps(summary, indent=2))
    print("\nVERDICT:", verdict, flush=True)
    print("wrote data/candidate/t43-ca-margin.json", flush=True)


if __name__ == "__main__":
    main()
