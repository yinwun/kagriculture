#!/usr/bin/env python
"""How hardcoded is each agent?  Compare an agent's full per-step action trace
across the different games we have of it.

Community analysis of the official daily dataset claims several 3100+ players are
100% identical across games ("hardcoded"), while the leaderboard #1 is not.  This
script measures the same thing on our own replays: for every pair of games of the
same agent it reports

  identical_full   : fraction of steps whose farmer+hands+market action is exactly
                     equal (coordinates and quantities included -> catches a pure
                     tape, but also a tape whose actions depend on the town)
  identical_skel   : fraction of steps whose *verb skeleton* is equal (which verbs
                     each worker performs, ignoring tiles and quantities)
  games_identical  : how many of the agent's games match another game 100%

Usage:
  python scripts/trace_identity.py data/top/episode-*.json data/replays/episode-*.json
"""
import collections
import glob
import itertools
import json
import sys
from pathlib import Path


def trace(path, p):
    d = json.loads(Path(path).read_text())
    out = []
    for entry in d["steps"]:
        if p >= len(entry):
            break
        a = entry[p].get("action") or {}
        f = tuple(a.get("farmer") or ())
        h = tuple(tuple(x) for x in (a.get("hands") or []))
        m = tuple(tuple(x) for x in (a.get("market") or ()))
        out.append((f, h, m))
    return out


def skel(t):
    def s(x):
        if isinstance(x, str):
            return (x,)
        return tuple(v[0] if isinstance(v, (list, tuple)) and v else v for v in x if v)
    return tuple((s(f), tuple(s(h) for h in hs), s(m)) for f, hs, m in t)


def teams_of(path):
    d = json.loads(Path(path).read_text())
    return d.get("info", {}).get("TeamNames", [])


def main():
    paths = []
    for a in sys.argv[1:]:
        paths.extend(sorted(glob.glob(a)))
    by_team = collections.defaultdict(list)
    for path in paths:
        for p, t in enumerate(teams_of(path)):
            by_team[t].append((path, p))

    print(f"{'agent':22s} {'games':>5s} {'pairs':>5s}  full-identical  skel-identical  games 100% identical")
    rows = []
    for team, items in by_team.items():
        if len(items) < 2:
            continue
        trs = {i: trace(path, p) for i, (path, p) in enumerate(items)}
        sk = {i: skel(trs[i]) for i in trs}
        n = min(len(v) for v in trs.values())
        full, skel_, perfect = [], [], 0
        comp = {"market": [], "farmer": [], "hands": []}
        for i, j in itertools.combinations(trs, 2):
            fi = sum(1 for k in range(n) if trs[i][k] == trs[j][k]) / n
            si = sum(1 for k in range(n) if sk[i][k] == sk[j][k]) / n
            for ci, key in ((0, "farmer"), (1, "hands"), (2, "market")):
                live = [k for k in range(n)
                        if trs[i][k][ci] or trs[j][k][ci]]
                comp[key].append(
                    (sum(1 for k in live if trs[i][k][ci] == trs[j][k][ci]) / len(live))
                    if live else 1.0)
            full.append(fi)
            skel_.append(si)
            if fi > 0.999:
                perfect += 1
        rows.append((team, len(items), len(full), sum(full) / len(full),
                     sum(skel_) / len(skel_), perfect,
                     {k: sum(v) / len(v) for k, v in comp.items()}))
    for team, g, pr, fu, sk_, pf, c in sorted(rows, key=lambda r: -r[3]):
        print(f"{team:22s} {g:5d} {pr:5d}  {fu:13.3f}  {sk_:15.3f}  {pf:3d}/{pr}"
              f"   farmer~{c['farmer']:.3f} hands~{c['hands']:.3f} market~{c['market']:.3f} (live-step conditional)")
    print("\n(perfect pairs = ${} of pairs with 100% identical full traces)")


if __name__ == "__main__":
    main()
