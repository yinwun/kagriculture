#!/usr/bin/env python
"""Task 42b: the end-of-day overflow guard, version 2 (corrected executable accounting).

Why v2 exists.  v1 (scripts/t42_sweep.py) computed the projected overflow as
    over = shed - min(sum(planned), shed) + carried - cap
i.e. it credited the base's own planned SELL orders with freeing shed space.  Measured
result: over > 0 only 3 times in 60 games (forward_overflow_units = 3), delta +0.1.

But the replay attribution says 8.37 units/game are still destroyed (12.71 in the losses)
WITH the base's own `room_guard` layer active.  The explanation is that an order only frees
space if it can EXECUTE: `_commit_unit` SELL requires the item to be in the SHED, so an
order for goods that are still in a worker's hands (which is what the night drop overflow
actually consists of) is dead -- it consumes a market slot and sells nothing.  v2 therefore
counts only executable planned sells (SELL lots for items present in the projected shed,
within the engine's first `maxMarketOrdersPerTurn` slots), measures the residual overflow
against THAT, and attacks it in three steps:

  1. retarget dead SELL lots (item with zero projected shed stock) to a sellable item,
     keeping the slot -- this costs no slot and repairs an order that cannot execute;
  2. merge extra quantity into an existing executable SELL lot for the chosen item;
  3. append a new SELL lot only if the list is shorter than `max_orders`.

The guard never withholds stock and never raises a quantity above what is in the shed.

Usage:
  .venv/bin/python scripts/t42b_sweep.py --probe        # 1 seed, print the counters
  .venv/bin/python scripts/t42b_sweep.py                # screen + confirm
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
import build_composite_layers as B  # noqa: E402

OUT = ROOT / "data" / "candidate"
RACE_DIR = OUT / "pi_stack_raceonly" / "main.py"
CHAMP = OUT / "pi_stack" / "main.py"
SCREEN = "16400-16429"
CONFIRM = "16500-16529"

OLD1 = '        min_price = float(cfg.get("forward_min_price", 2) or 0)\n'
NEW1 = OLD1 + ('        fracs = cfg.get("forward_min_frac_by_item") or {}\n'
               '        _BASE = {"WOOL": 200, "STRAWBERRY": 120, "MILK": 160, "WHEAT": 25, "CARROT": 35,\n'
               '                 "TOMATO": 60, "MELON": 250, "EGG": 50, "FERTILIZER": 100}\n')
OLD2 = '            if int(view.prices.get(item, 0)) < min_price:\n'
NEW2 = ('            if int(view.prices.get(item, 0)) < max(min_price, float(fracs.get(item, 0) or 0)\n'
        '                                                       * _BASE.get(item, 0)):\n')
OLD3 = ('                cap = max(1, int(round(rate * float(cfg.get("forward_drain_mult", 1.0) '
        'or 1.0))))\n')
NEW3 = ('                _fmul = float((cfg.get("forward_drain_mult_by_item") or {}).get(\n'
        '                    item, cfg.get("forward_drain_mult", 1.0)) or 1.0)\n'
        '                cap = max(1, int(round(rate * _fmul)))\n')

GUARD = '''
        if bool(cfg.get("forward_overflow_guard")):
            _tpd = int(cfg.get("turns_per_day", 24) or 24)
            if step % _tpd >= _tpd - int(cfg.get("forward_guard_turns", 1) or 1):
                try:
                    _cap_tot = int(cfg.get("shed_capacity", 100) or 100)
                    _maxo = int(cfg.get("max_orders", 10) or 10)
                    _shed_tot = sum(max(0, _int(v)) for v in projected.values())
                    _units_act = ([result.get("farmer") or ["PASS"]]
                                  + list(result.get("hands") or []))
                    _hand_tot = 0
                    for _i in range(len(view.positions)):
                        _inv = view.inv(_i) or {}
                        _tot = sum(max(0, _int(v)) for v in _inv.values())
                        _a = _units_act[_i] if _i < len(_units_act) else None
                        if (isinstance(_a, list) and _a and _a[0] == "DROP"
                                and _shed_adjacent(view.positions[_i], view.board)):
                            _tot = 0
                        _hand_tot += _tot
                    # executable planned sells only: within the engine's slot budget and
                    # backed by stock that is actually in the shed this turn
                    _win = market[:_maxo]
                    _exe = 0
                    for _o in _win:
                        if (isinstance(_o, list) and len(_o) >= 3 and _o[0] == "SELL"):
                            _av = max(0, _int(projected.get(_o[1], 0)))
                            _exe += min(max(0, _int(_o[2])), _av)
                    _over = _shed_tot - _exe + _hand_tot - _cap_tot
                    _fwd_diag("g_shed", _shed_tot)
                    _fwd_diag("g_hand", _hand_tot)
                    _fwd_diag("g_exe", _exe)
                    if _over > 0:
                        _fwd_diag("g_over", _over)
                        _fwd_diag("g_over_turns")
                        _guard = cfg.get("forward_guard_items") or _FWD_GUARD_DEFAULT
                        _slack = {}
                        for _it in _guard:
                            _s = max(0, _int(projected.get(_it, 0))) - planned.get(_it, 0)
                            if _s > 0:
                                _slack[_it] = _s
                        _order = sorted(_slack, key=lambda k: -float(view.prices.get(k, 0)))
                        # 1. retarget dead SELL lots (nothing in the shed to sell)
                        for _i, _o in enumerate(_win):
                            if _over <= 0 or not _order:
                                break
                            if not (isinstance(_o, list) and len(_o) >= 3
                                    and _o[0] == "SELL"):
                                continue
                            if max(0, _int(projected.get(_o[1], 0))) > 0:
                                continue
                            _it = _order[0]
                            _take = min(_slack[_it], _over)
                            market[_i] = ["SELL", _it, _take]
                            planned[_it] = planned.get(_it, 0) + _take
                            _slack[_it] -= _take
                            _over -= _take
                            if _slack[_it] <= 0:
                                _order.pop(0)
                            _fwd_diag("g_retarget", _take)
                        # 2/3. merge into an executable lot, else append while slots remain
                        for _it in list(_order):
                            if _over <= 0:
                                break
                            _take = min(_slack[_it], _over)
                            if _take <= 0:
                                continue
                            _done = False
                            for _o in market:
                                if (isinstance(_o, list) and len(_o) >= 3 and _o[0] == "SELL"
                                        and _o[1] == _it
                                        and max(0, _int(projected.get(_it, 0))) > 0):
                                    _o[2] = max(0, _int(_o[2])) + _take
                                    _done = True
                                    break
                            if not _done:
                                if len(market) >= _maxo:
                                    _fwd_diag("g_blocked", _take)
                                    continue
                                market.append(["SELL", _it, _take])
                            planned[_it] = planned.get(_it, 0) + _take
                            _over -= _take
                            _fwd_diag("g_release", _take)
                except Exception:
                    _fwd_diag("g_errors")
'''
GUARD_ANCHOR = '        result["market"] = market\n'
GUARD_DEFAULT_ANCHOR = "\nagent = _fwd_outer\n"
GUARD_DEFAULT = ('\n_FWD_GUARD_DEFAULT = ["FERTILIZER", "WOOL", "STRAWBERRY", "MILK",\n'
                 '                    "CARROT", "TOMATO", "MELON", "EGG"]\n')


def patch_lib():
    lib = B.FWD_LIB
    for old, new in ((OLD1, NEW1), (OLD2, NEW2), (OLD3, NEW3)):
        assert lib.count(old) == 1, f"anchor not unique: {old[:50]!r}"
        lib = lib.replace(old, new)
    assert lib.count(GUARD_ANCHOR) == 1
    lib = lib.replace(GUARD_ANCHOR, GUARD + GUARD_ANCHOR)
    assert lib.count(GUARD_DEFAULT_ANCHOR) == 1
    lib = lib.replace(GUARD_DEFAULT_ANCHOR, GUARD_DEFAULT + GUARD_DEFAULT_ANCHOR)
    B.FWD_LIB = lib


GUARD_ITEMS = ["FERTILIZER", "WOOL", "STRAWBERRY", "MILK", "CARROT", "TOMATO", "MELON",
               "EGG"]
BASE_FWD = {"forward_items": ["WOOL", "STRAWBERRY", "MILK"], "forward_drain": True,
            "forward_start_by_item": {"STRAWBERRY": 312, "MILK": 312},
            "forward_drain_mult": 24.0}
VARIANTS = {
    "t42b_ctl": dict(BASE_FWD),
    "t42b_guard_v2": {**BASE_FWD, "forward_overflow_guard": True},
    "t42b_guard_v2_wide": {**BASE_FWD, "forward_overflow_guard": True,
                           "forward_guard_items": GUARD_ITEMS + ["WHEAT"]},
    "t42b_guard_v2_3": {**BASE_FWD, "forward_overflow_guard": True,
                        "forward_guard_turns": 3},
}
SMOKE = ("import sys\nfrom pathlib import Path\nfrom kaggle_environments import make\n"
         "p=sys.argv[1]; ns={'__name__':'m'}; exec(compile(Path(p).read_text(),p,'exec'),ns)\n"
         "e=make('kaggriculture',configuration={'episodeSteps':720,'seed':16000}); "
         "e.run([ns['agent'],ns['agent']])\n"
         "d=getattr(ns.get('_IMPL'),'chassis',None); diag=d.diagnostics if d else {}\n"
         "print('SMOKE',[str(e.steps[-1][i]['status']) for i in (0,1)],"
         "sorted(k for k,v in diag.items() if v and ('error' in k or 'fallback' in k)),"
         "{k:v for k,v in diag.items() if k.startswith('g_')})\n")


def run(cmd, **kw):
    return subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, **kw)


def duel(cand, base, seeds, label, out):
    run([".venv/bin/python", "scripts/ab_duel.py", "--cand", str(cand), "--base", str(base),
         "--seeds", seeds, "--label", label, "--out", str(out)])
    return json.loads(out.read_text())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--probe", action="store_true")
    ap.add_argument("--screen-only", action="store_true")
    args = ap.parse_args()
    patch_lib()
    built = {}
    for name, spec in VARIANTS.items():
        p = B.build_fwd(spec, name, base_path=RACE_DIR, out_root=OUT)
        sha = hashlib.sha256(Path(p).read_bytes()).hexdigest()
        r = run([".venv/bin/python", "-c", SMOKE, str(p.relative_to(ROOT))], timeout=1800)
        last = (r.stdout or r.stderr).strip().splitlines()[-1] if (r.stdout or r.stderr).strip() else "NO OUTPUT"
        print(f"built {p.relative_to(ROOT)} sha256 {sha}\n    {last[:240]}", flush=True)
        built[name] = (p, sha)
    if args.probe:
        d = duel(built["t42b_guard_v2"][0], CHAMP, "16400", "probe-guard-v2",
                 OUT / "duel-t42b-probe.json")
        print("PROBE diag:", json.dumps(d.get("cand_diag"), indent=1))
        return
    print(f"\n=== SCREEN {SCREEN} vs champion pi_stack ===", flush=True)
    res = {}
    for name, (p, sha) in built.items():
        out = OUT / f"duel-t42b-{name}-screen.json"
        d = duel(p, CHAMP, SCREEN, name, out)
        res[name] = d
        g = {k: v for k, v in (d.get("cand_diag") or {}).items() if k.startswith("g_")}
        print(f"  {name:20s} d={d['delta']:+9.1f} t={d['t']:+6.2f} W-L {d['wins']}-{d['losses']} "
              f"err={d['errors']} exc={d['cand_exceptions']}/{d['base_exceptions']} diag={g}",
              flush=True)
    ctl = res["t42b_ctl"]
    print(f"\nCONTROL: delta={ctl['delta']!r} t={ctl['t']!r} "
          f"-> {'OK' if ctl['delta'] == 0.0 else 'FAIL'}", flush=True)
    if ctl["delta"] != 0.0:
        raise SystemExit("control not inert")
    if args.screen_only:
        return
    cands = sorted(((v["delta"], v["t"], k) for k, v in res.items() if k != "t42b_ctl"),
                   reverse=True)
    if not cands or cands[0][0] <= 0:
        print("\nno candidate beats the champion on the screen panel", flush=True)
        json.dump({"verdict": "NO CANDIDATE",
                   "screen": {k: {"delta": v["delta"], "t": v["t"],
                                  "cand_diag": {kk: vv for kk, vv in (v.get("cand_diag") or {}).items() if kk.startswith("g_")}}
                              for k, v in res.items()}},
                  open(OUT / "t42b-sweep.json", "w"), indent=1)
        return
    d0, t0, name0 = cands[0]
    p0, sha0 = built[name0]
    print(f"\n=== CONFIRM {name0} (screen d={d0:+.1f} t={t0:+.2f}) on fresh panel {CONFIRM} ===",
          flush=True)
    out = OUT / f"duel-t42b-{name0}-confirm.json"
    d1 = duel(p0, CHAMP, CONFIRM, f"{name0}-confirm", out)
    print(f"  {name0} confirm d={d1['delta']:+.1f} t={d1['t']:+.2f} W-L {d1['wins']}-{d1['losses']} "
          f"err={d1['errors']} exc={d1['cand_exceptions']}", flush=True)
    verdict = ("CLEARS: beats the champion on both panels with t>=3"
               if d0 > 0 and d1["delta"] > 0 and t0 >= 3 and d1["t"] >= 3
               else "NO EDGE: champion stays")
    json.dump({"champion": str(CHAMP.relative_to(ROOT)),
               "champion_sha256": hashlib.sha256(CHAMP.read_bytes()).hexdigest(),
               "screen_panel": SCREEN, "confirm_panel": CONFIRM,
               "screen": {k: {"delta": v["delta"], "t": v["t"], "wins": v["wins"],
                              "losses": v["losses"], "errors": v["errors"],
                              "cand_exceptions": v["cand_exceptions"],
                              "cand_diag": v.get("cand_diag")} for k, v in res.items()},
               "built": {k: {"path": str(v[0].relative_to(ROOT)), "sha256": v[1]}
                         for k, v in built.items()},
               "best": {"name": name0, "sha256": sha0, "screen_delta": d0, "screen_t": t0,
                        "confirm_delta": d1["delta"], "confirm_t": d1["t"],
                        "confirm_wl": [d1["wins"], d1["losses"]]},
               "verdict": verdict},
              open(OUT / "t42b-sweep.json", "w"), indent=1)
    print("\nVERDICT:", verdict, flush=True)


if __name__ == "__main__":
    main()
