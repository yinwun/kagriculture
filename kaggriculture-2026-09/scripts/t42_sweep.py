#!/usr/bin/env python
"""Task 42: screen market-layer candidates for `pi_stack` (the V78 + our-layers champion).

Candidates are all outermost-wrapper changes to the market order list only.  Depends on
`data/candidate/pi_stack_raceonly/main.py` (the race-only intermediate from
scripts/t40_stack.py) and on `data/candidate/pi_stack/main.py` (the champion).

Protocol (doctrine): every variant is smoke-gated (720 steps, both DONE, all error
counters 0); a knobs-off CONTROL rebuild must produce delta EXACTLY 0 against the champion
on the same seeds (a liveness check, not a formality); the screen runs on one fresh panel
(16400-16429, unused) and only a candidate that beats the champion there is confirmed on a
second fresh panel (16500-16529); the bar is delta > 0 with t >= 3 on BOTH panels.

Usage: .venv/bin/python scripts/t42_sweep.py [--screen-only] [--only NAME]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import build_race as BR          # noqa: E402
import build_composite_layers as B  # noqa: E402

OUT = ROOT / "data" / "candidate"
RACE_DIR = OUT / "pi_stack_raceonly" / "main.py"
CHAMP = OUT / "pi_stack" / "main.py"
SCREEN = "16400-16429"
CONFIRM = "16500-16529"

# --- patch 1: inert per-item price-fraction gate (the patch t40/t41 used, kept so the
# built code path is identical to the champion's; no fractions are configured)
OLD1 = '        min_price = float(cfg.get("forward_min_price", 2) or 0)\n'
NEW1 = OLD1 + ('        fracs = cfg.get("forward_min_frac_by_item") or {}\n'
               '        _BASE = {"WOOL": 200, "STRAWBERRY": 120, "MILK": 160, "WHEAT": 25, "CARROT": 35,\n'
               '                 "TOMATO": 60, "MELON": 250, "EGG": 50, "FERTILIZER": 100}\n')
OLD2 = '            if int(view.prices.get(item, 0)) < min_price:\n'
NEW2 = ('            if int(view.prices.get(item, 0)) < max(min_price, float(fracs.get(item, 0) or 0)\n'
        '                                                       * _BASE.get(item, 0)):\n')

# --- patch 2: per-item release multiplier (defaults to the global forward_drain_mult)
OLD3 = ('                cap = max(1, int(round(rate * float(cfg.get("forward_drain_mult", 1.0) '
        'or 1.0))))\n')
NEW3 = ('                _fmul = float((cfg.get("forward_drain_mult_by_item") or {}).get(\n'
        '                    item, cfg.get("forward_drain_mult", 1.0)) or 1.0)\n'
        '                cap = max(1, int(round(rate * _fmul)))\n')

# --- patch 3: end-of-day overflow guard.  Every unit that the night drop discards is
# worth ZERO, while a sold unit is worth its market price (>= 1), so on the last turn of a
# day we release exactly the projected overflow -- ignoring the drain cap -- taking the
# most expensive sellable goods in the shed first.  This is NOT the refuted price-floor /
# deferral family: it never withholds stock, it only refuses to let stock be destroyed.
GUARD = '''
        if bool(cfg.get("forward_overflow_guard")) and \\
                step % int(cfg.get("turns_per_day", 24) or 24) >= \\
                int(cfg.get("turns_per_day", 24) or 24) - int(cfg.get("forward_guard_turns", 1) or 1):
            try:
                cap_tot = int(cfg.get("shed_capacity", 100) or 100)
                shed_tot = sum(max(0, _int(v)) for v in projected.values())
                units_act = [result.get("farmer") or ["PASS"]] + list(result.get("hands") or [])
                hand_tot = 0
                for _i in range(len(view.positions)):
                    _inv = view.inv(_i) or {}
                    _tot = sum(max(0, _int(v)) for v in _inv.values())
                    _a = units_act[_i] if _i < len(units_act) else None
                    if (isinstance(_a, list) and _a and _a[0] == "DROP"
                            and _shed_adjacent(view.positions[_i], view.board)):
                        _tot = 0          # already counted inside `projected`
                    hand_tot += _tot
                over = (shed_tot - min(sum(planned.values()), shed_tot)
                        + hand_tot - cap_tot)
                if over > 0:
                    _guard = cfg.get("forward_guard_items") or _FWD_GUARD_DEFAULT
                    _cands = []
                    for _it in _guard:
                        _slack = max(0, _int(projected.get(_it, 0))) - planned.get(_it, 0)
                        if _slack > 0:
                            _cands.append((float(view.prices.get(_it, 0)), _it, _slack))
                    _cands.sort(reverse=True)
                    for _price, _it, _slack in _cands:
                        if over <= 0:
                            break
                        _take = min(_slack, over)
                        _merged = False
                        for _o in market:
                            if (isinstance(_o, list) and len(_o) >= 3 and _o[0] == "SELL"
                                    and _o[1] == _it):
                                _o[2] = max(0, _int(_o[2])) + _take
                                _merged = True
                                break
                        if not _merged:
                            if len(market) >= cfg["max_orders"]:
                                _fwd_diag("forward_overflow_skipped", _take)
                                continue
                            market.append(["SELL", _it, _take])
                        planned[_it] = planned.get(_it, 0) + _take
                        over -= _take
                        _fwd_diag("forward_overflow_units", _take)
                        _fwd_diag("forward_overflow_orders")
            except Exception:
                _fwd_diag("forward_overflow_errors")
'''
GUARD_ANCHOR = '        result["market"] = market\n'
# inserted just before `agent = _fwd_outer` in FWD_LIB
GUARD_DEFAULT_ANCHOR = "\nagent = _fwd_outer\n"
GUARD_DEFAULT = ('\n_FWD_GUARD_DEFAULT = ["FERTILIZER", "WOOL", "STRAWBERRY", "MILK",\n'
                 '                    "CARROT", "TOMATO", "MELON", "EGG"]\n')


def patch_lib():
    lib = B.FWD_LIB
    for old, new in ((OLD1, NEW1), (OLD2, NEW2), (OLD3, NEW3)):
        assert lib.count(old) == 1, f"anchor not unique: {old[:60]!r}"
        lib = lib.replace(old, new)
    assert lib.count(GUARD_ANCHOR) == 1, "market-assign anchor not unique"
    lib = lib.replace(GUARD_ANCHOR, GUARD + GUARD_ANCHOR)
    assert lib.count(GUARD_DEFAULT_ANCHOR) == 1, "agent-assign anchor not unique"
    lib = lib.replace(GUARD_DEFAULT_ANCHOR, GUARD_DEFAULT + GUARD_DEFAULT_ANCHOR)
    B.FWD_LIB = lib


GUARD_DEFAULT_ITEMS = ["FERTILIZER", "WOOL", "STRAWBERRY", "MILK", "CARROT", "TOMATO",
                       "MELON", "EGG"]
BASE_FWD = {"forward_items": ["WOOL", "STRAWBERRY", "MILK"], "forward_drain": True,
            "forward_start_by_item": {"STRAWBERRY": 312, "MILK": 312},
            "forward_drain_mult": 24.0}

VARIANTS = {
    # knobs-off control: every new knob present but inert.  Must give delta EXACTLY 0.
    "t42_ctl": dict(BASE_FWD),
    # the end-of-day overflow guard (the new mechanism), default item set
    "t42_guard": {**BASE_FWD, "forward_overflow_guard": True},
    # guard over every sellable product, feed wheat included
    "t42_guard_wide": {**BASE_FWD, "forward_overflow_guard": True,
                       "forward_guard_items": GUARD_DEFAULT_ITEMS + ["WHEAT"]},
    # guard without fertilizer (isolates the input item)
    "t42_guard_nof": {**BASE_FWD, "forward_overflow_guard": True,
                      "forward_guard_items": [i for i in GUARD_DEFAULT_ITEMS
                                              if i != "FERTILIZER"]},
    # guard spread over the last three turns of each day instead of only the last
    "t42_guard3": {**BASE_FWD, "forward_overflow_guard": True, "forward_guard_turns": 3},
    # per-item release multiplier: the t38 plateau suggested wool can take more
    "t42_wool48": {**BASE_FWD, "forward_drain_mult_by_item": {"WOOL": 48.0}},
    # the late-window items under a tighter cap than the global optimum
    "t42_late12": {**BASE_FWD,
                   "forward_drain_mult_by_item": {"STRAWBERRY": 12.0, "MILK": 12.0}},
    # melon in the late window (never tested on this base)
    "t42_melon": {**BASE_FWD, "forward_items": ["WOOL", "STRAWBERRY", "MILK", "MELON"],
                  "forward_start_by_item": {"STRAWBERRY": 312, "MILK": 312, "MELON": 312}},
}

SMOKE = ("import sys\nfrom pathlib import Path\nfrom kaggle_environments import make\n"
         "p=sys.argv[1]; ns={'__name__':'m'}; exec(compile(Path(p).read_text(),p,'exec'),ns)\n"
         "e=make('kaggriculture',configuration={'episodeSteps':720,'seed':16000}); "
         "e.run([ns['agent'],ns['agent']])\n"
         "d=getattr(ns.get('_IMPL'),'chassis',None)\n"
         "diag=d.diagnostics if d else {}\n"
         "bad={k:v for k,v in diag.items() if v and ('error' in k or 'fallback' in k)}\n"
         "print('SMOKE',[str(e.steps[-1][i]['status']) for i in (0,1)],'bad',bad,"
         "'fwd',{k:v for k,v in diag.items() if 'forward' in k})\n")


def run(cmd, **kw):
    return subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, **kw)


def duel(cand, base, seeds, label, out):
    run([".venv/bin/python", "scripts/ab_duel.py", "--cand", str(cand), "--base", str(base),
         "--seeds", seeds, "--label", label, "--out", str(out)])
    return json.loads(out.read_text())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--screen-only", action="store_true")
    ap.add_argument("--only", default=None)
    args = ap.parse_args()
    if not RACE_DIR.exists() or not CHAMP.exists():
        raise SystemExit("run scripts/t40_stack.py first")
    patch_lib()
    champ_sha = hashlib.sha256(CHAMP.read_bytes()).hexdigest()

    built = {}
    for name, spec in VARIANTS.items():
        if args.only and name != args.only:
            continue
        p = B.build_fwd(spec, name, base_path=RACE_DIR, out_root=OUT)
        sha = hashlib.sha256(Path(p).read_bytes()).hexdigest()
        r = run([".venv/bin/python", "-c", SMOKE, str(p.relative_to(ROOT))], timeout=1800)
        last = (r.stdout or r.stderr).strip().splitlines()[-1] if (r.stdout or r.stderr).strip() else "NO OUTPUT"
        print(f"built {p.relative_to(ROOT)} sha256 {sha}\n    {last[:200]}", flush=True)
        built[name] = (p, sha)

    print(f"\n=== SCREEN {SCREEN} vs champion pi_stack ({champ_sha[:12]}) ===", flush=True)
    res = {}
    for name, (p, sha) in built.items():
        out = OUT / f"duel-t42-{name}-screen.json"
        d = duel(p, CHAMP, SCREEN, name, out)
        res[name] = d
        print(f"  {name:16s} d={d['delta']:+9.1f} t={d['t']:+6.2f} W-L {d['wins']}-{d['losses']} "
              f"wallet {round(d['cand_wallet'])}/{round(d['base_wallet'])} err={d['errors']} "
              f"exc={d['cand_exceptions']}/{d['base_exceptions']} "
              f"diag={ {k:v for k,v in (d.get('cand_diag') or {}).items() if 'forward' in k or 'race' in k} }",
              flush=True)

    ctl = res.get("t42_ctl")
    if ctl is not None:
        ok = ctl["delta"] == 0.0 and ctl["t"] == 0.0
        print(f"\nCONTROL CHECK: delta={ctl['delta']!r} t={ctl['t']!r} -> "
              f"{'OK (exactly 0)' if ok else 'FAIL (control is not inert!)'}", flush=True)
        if not ok:
            raise SystemExit("control not inert: the new code path changes behaviour with all knobs off")

    if args.screen_only or args.only:
        json.dump({k: {kk: v[kk] for kk in ("delta", "t", "wins", "losses", "errors",
                                           "cand_exceptions", "base_exceptions")}
                   for k, v in res.items()},
                  open(OUT / "t42-screen.json", "w"), indent=1)
        return

    cands = sorted(((v["delta"], v["t"], k) for k, v in res.items() if k != "t42_ctl"),
                   reverse=True)
    if not cands or cands[0][0] <= 0:
        print("\nno candidate beats the champion on the screen panel", flush=True)
        json.dump({"verdict": "NO CANDIDATE", "screen": {
            k: {"delta": v["delta"], "t": v["t"]} for k, v in res.items()}},
            open(OUT / "t42-sweep.json", "w"), indent=1)
        return
    d0, t0, name0 = cands[0]
    p0, sha0 = built[name0]
    print(f"\n=== CONFIRM {name0} (screen d={d0:+.1f} t={t0:+.2f}) on fresh panel {CONFIRM} ===",
          flush=True)
    out = OUT / f"duel-t42-{name0}-confirm.json"
    d1 = duel(p0, CHAMP, CONFIRM, f"{name0}-confirm", out)
    print(f"  {name0} confirm d={d1['delta']:+.1f} t={d1['t']:+.2f} W-L {d1['wins']}-{d1['losses']} "
          f"err={d1['errors']} exc={d1['cand_exceptions']}", flush=True)
    verdict = ("CLEARS: beats the champion on both panels with t>=3"
               if d0 > 0 and d1["delta"] > 0 and t0 >= 3 and d1["t"] >= 3
               else "NO EDGE: champion stays")
    summary = {"champion": str(CHAMP.relative_to(ROOT)), "champion_sha256": champ_sha,
               "screen_panel": SCREEN, "confirm_panel": CONFIRM,
               "screen": {k: {"delta": v["delta"], "t": v["t"], "wins": v["wins"],
                              "losses": v["losses"], "errors": v["errors"],
                              "cand_exceptions": v["cand_exceptions"],
                              "cand_diag": v.get("cand_diag")}
                          for k, v in res.items()},
               "built": {k: {"path": str(v[0].relative_to(ROOT)), "sha256": v[1]}
                         for k, v in built.items()},
               "best": {"name": name0, "sha256": sha0, "screen_delta": d0, "screen_t": t0,
                        "confirm_delta": d1["delta"], "confirm_t": d1["t"],
                        "confirm_wl": [d1["wins"], d1["losses"]]},
               "verdict": verdict}
    json.dump(summary, open(OUT / "t42-sweep.json", "w"), indent=1)
    print("\nVERDICT:", verdict, flush=True)
    print("wrote data/candidate/t42-sweep.json", flush=True)


if __name__ == "__main__":
    main()
