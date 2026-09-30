#!/usr/bin/env python
"""Check whether a stronger *available* version exists: pull, build, and duel.

Our tracked line is V42 + room_guard + clamp_sells (ref 56307906).  The public
ecosystem has moved on since V42 (V43/V45, "top-10", "2900+", "93.8% win rate",
THUNDER c68 ...), and those builds have never been measured against our line.  This
orchestrator pulls a list of public notebooks, builds each into an agent main.py, and
runs the paired duel (seeds doubled with the seats swapped) against the champion.

Only versions that beat the champion with t>=3 are candidates to submit.

Usage:
  python scripts/check_stronger.py --towns 30 --procs 10
  python scripts/check_stronger.py --skip-pull --only data/league/v43 ...
"""
import argparse
import json
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# The delta that matters now is against what we have SUBMITTED, not the old champion.
BASE = ROOT / "data" / "forward" / "wool_drain1_outerprem" / "main.py"   # ref 56349751
CHAMPION = ROOT / "data" / "tapeopt" / "rgcs" / "main.py"
PY = str(ROOT / ".venv" / "bin" / "python")

# notebooks the meta has published since V42 (highest-value first)
NOTEBOOKS = [
    # newest public builds (pulled 2026-09-20 into data/cand/*.ipynb), highest value first.
    # Data provenance measured in REPORT-frontier-2.md: * = carries our exact route blob.
    "thomastschinkel/the-metav4-farm-submission-v13",        # newest composite (blob identical)
    "haideptry/the-2950-peak-farm",                          # *
    "haideptry/countering-the-big-3-meta",                   # *
    "haideptry/demystifying-2900-meta-reflex-engine-and-bot",# *
    "guruprasaathas111/kaggriculture-master-engine-v4",
    "koshinm/kaggriculture-local-best-2026-09-20",
    "nathanjacob/kaggriculture-pipe16-idle-workers",
    "nathanjacob/kaggriculture-pipe15-two-layers",
    "ahmedberatozer/kaggriculture-v53-opening-signature",
    "ahmedberatozer/kaggriculture-v52-lean-flock-yarn-route",
    "ahmedberatozer/kaggriculture-v51-lean-flock",
    "ahmedberatozer/kaggriculture-v50-early-yarn-commit",
    "shiiin9/beat-v48-100-0-your-herd-is-decided-on-day-6",
    "takamichitoda/flyfarmer-connectome-plays-kaggriculture",
    "alperen5252525/kaggriculture-market-rhythm-sale-policy",# different non-route payload
    "laveshjadon/kagriculture-winning-notebook",             # *
]


def pull(slug, out_dir, tries=4):
    out_dir.mkdir(parents=True, exist_ok=True)
    for i in range(tries):
        r = subprocess.run([PY, "-m", "kaggle", "kernels", "pull", slug, "-p", str(out_dir)],
                           capture_output=True, text=True)
        if "downloaded to" in (r.stdout or "") + (r.stderr or ""):
            return True
        time.sleep(4)
    return False


def build(nb, out_dir):
    r = subprocess.run([PY, "scripts/run_notebook.py", str(nb), str(out_dir)],
                       capture_output=True, text=True, cwd=str(ROOT))
    ok = (out_dir / "main.py").exists()
    if not ok:
        print(f"    build failed: {(r.stdout or r.stderr or '')[-200:]}", flush=True)
    return ok


def duel(cand, towns, procs):
    out = ROOT / "data" / f"duel-{cand.parent.name}.json"
    r = subprocess.run([PY, "scripts/ab_duel.py", "--cand", str(cand), "--base", str(BASE),   # the live submitted line (ref 56349751)
                        "--seeds", f"9000-{8999 + towns}", "--procs", str(procs),
                        "--label", cand.parent.name, "--out", str(out)],
                       capture_output=True, text=True, cwd=str(ROOT))
    m = re.search(r"delta\s+([-+0-9,]+)\s+t=([-+0-9.]+)\s+W/L\s+(\d+)/(\d+)", r.stdout or "")
    if not m:
        print(f"    duel failed: {(r.stdout or r.stderr or '')[-200:]}", flush=True)
        return None
    d = int(m.group(1).replace(",", ""))
    return {"name": cand.parent.name, "delta": d, "t": float(m.group(2)),
            "wins": int(m.group(3)), "losses": int(m.group(4))}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--towns", type=int, default=30)
    ap.add_argument("--procs", type=int, default=10)
    ap.add_argument("--skip-pull", action="store_true")
    ap.add_argument("--only", nargs="*", default=None, help="already-built agent dirs")
    args = ap.parse_args()

    cands = []
    if args.only:
        cands = [Path(p) / "main.py" for p in args.only]
    else:
        for slug in NOTEBOOKS:
            nb_dir = ROOT / "data" / "notebooks" / slug.replace("/", "_")
            if not args.skip_pull and not list(nb_dir.glob("*.ipynb")):
                print(f"pulling {slug} ...", flush=True)
                if not pull(slug, nb_dir):
                    print("  pull failed", flush=True)
                    continue
            nbs = sorted(nb_dir.glob("*.ipynb"))
            if not nbs:
                continue
            out_dir = ROOT / "data" / "cand" / slug.split("/")[-1]
            if not (out_dir / "main.py").exists():
                print(f"building {slug} ...", flush=True)
                if not build(nbs[0], out_dir):
                    continue
            cands.append(out_dir / "main.py")

    print(f"\n{len(cands)} candidates to duel vs the champion on {args.towns} towns", flush=True)
    rows = []
    for c in cands:
        print(f"duelling {c.parent.name} ...", flush=True)
        res = duel(c, args.towns, args.procs)
        if res:
            rows.append(res)
            print(f"  {res['name']}: delta {res['delta']:+,} t={res['t']:+.2f} W/L {res['wins']}/{res['losses']}",
                  flush=True)
    rows.sort(key=lambda r: -r["delta"])
    print("\n=== summary (delta vs our champion; positive = stronger) ===")
    for r in rows:
        flag = "  <-- CANDIDATE" if r["delta"] > 0 and r["t"] >= 3 else ""
        print(f"  {r['name']:56s} {r['delta']:+9,} t={r['t']:+6.2f} W/L {r['wins']}/{r['losses']}{flag}")
    (ROOT / "data" / "stronger-check.json").write_text(json.dumps(rows, indent=1))
    print(f"\nwrote data/stronger-check.json")


if __name__ == "__main__":
    sys.exit(main())
