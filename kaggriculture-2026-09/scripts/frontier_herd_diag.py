#!/usr/bin/env python
"""Why the public frontier build beats the champion: correlate the final animal
census with the per-seed duel delta.

`scripts/race_probe.py` showed the frontier's 85,884 requested sell units become
only ~1,590 executed ones (the shed caps them anyway), so its "+37.7% SELL orders"
is a request-pattern artefact, not extra sales.  This script tests the other
candidate explanation: the frontier converts geese (EGG) into sheep (WOOL) when the
town unlocks the YARN_STORE, i.e. it responds to the seed's shop list with a
different herd, which is worth ~$200/unit instead of ~$50.

For every seed it records, for both seats: the shop list at the end of day 8, the
final animal census, and the final wallets; it then prints the correlation between
the sheep difference and the per-seed duel delta taken from
data/duel-the-2945-farm-96-vs-the-top-10-public-bots.json.

Usage: .venv/bin/python scripts/frontier_herd_diag.py --seeds 9000-9029
"""
from __future__ import annotations

import argparse
import collections
import json
import multiprocessing as mp
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHAMPION = str(ROOT / "data" / "tapeopt" / "rgcs" / "main.py")
FRONTIER = str(ROOT / "data" / "cand" / "the-2945-farm-96-vs-the-top-10-public-bots" / "main.py")
DUEL = ROOT / "data" / "duel-the-2945-farm-96-vs-the-top-10-public-bots.json"


def _load(path):
    ns = {"__name__": "diag_mod"}
    exec(compile(Path(path).read_text(), str(path), "exec"), ns)
    return ns["agent"]


def census(env, seat):
    tiles = env.steps[-1][seat]["observation"]["farms"][seat]["tiles"]
    c = collections.Counter()
    for row in tiles:
        for tl in row:
            if isinstance(tl, dict) and tl.get("animal"):
                c[tl["animal"]] += 1
    return dict(c)


def one(seed):
    from kaggle_environments import make
    cand, base = _load(FRONTIER), _load(CHAMPION)
    out = {"seed": seed}
    for cand_seat in (0, 1):
        env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": seed})
        env.run([cand, base] if cand_seat == 0 else [base, cand])
        shops = list(env.steps[-1][0]["observation"]["town"]["unlocked_shops"])
        final = [float(env.steps[-1][i]["reward"] or 0) for i in (0, 1)]
        out[cand_seat] = {
            "shops": shops,
            "cand_census": census(env, cand_seat),
            "base_census": census(env, 1 - cand_seat),
            "delta": final[cand_seat] - final[1 - cand_seat],
        }
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", default="9000-9029")
    ap.add_argument("--procs", type=int, default=10)
    ap.add_argument("--out", default=str(ROOT / "data" / "race" / "herd-diag.json"))
    args = ap.parse_args()
    a, b = args.seeds.split("-")
    seeds = list(range(int(a), int(b) + 1))
    with mp.Pool(args.procs) as pool:
        rows = pool.map(one, seeds)

    duel = {}
    if DUEL.exists():
        duel = {p["seed"]: p["delta"] for p in json.loads(DUEL.read_text())["per_seed"]}
    table = []
    print(f"{'seed':>5} {'delta':>8} {'yarn':>4} {'sheep c/b':>10} {'goose c/b':>10} "
          f"{'cow c/b':>9} {'shops(day8)':>28}")
    for r in rows:
        shops = r[0]["shops"]
        yarn = sum(1 for s in shops if s == "YARN_STORE")
        sc, sb = r[0]["cand_census"].get("SHEEP", 0), r[0]["base_census"].get("SHEEP", 0)
        gc, gb = r[0]["cand_census"].get("GOOSE", 0), r[0]["base_census"].get("GOOSE", 0)
        mc, mb = r[0]["cand_census"].get("COW", 0), r[0]["base_census"].get("COW", 0)
        delta = (r[0]["delta"] + r[1]["delta"]) / 2.0
        table.append({"seed": r["seed"], "yarn": yarn, "sheep_c": sc, "sheep_b": sb,
                      "goose_c": gc, "goose_b": gb, "cow_c": mc, "cow_b": mb,
                      "delta": delta, "duel_delta": duel.get(r["seed"])})
        print(f"{r['seed']:5d} {delta:+8.0f} {yarn:4d} {sc:4d}/{sb:<5d} {gc:4d}/{gb:<5d} "
              f"{mc:4d}/{mb:<4d} {','.join(shops[:4]):>28}")

    def corr(xs, ys):
        if len(xs) < 3:
            return float("nan")
        try:
            return statistics.correlation(xs, ys)
        except Exception:
            return float("nan")

    ds = [t["delta"] for t in table]
    print()
    print(f"mean delta over {len(table)} seeds: {statistics.mean(ds):+,.0f} "
          f"(duel json mean {statistics.mean([t['duel_delta'] for t in table if t['duel_delta'] is not None]):+,.0f})")
    for key, name in (( ("sheep_c","sheep_b"), "sheep cand-base"),
                      (("goose_c","goose_b"), "goose base-cand"),
                      (("cow_c","cow_b"), "cow cand-base")):
        xs = [t[key[0]] - t[key[1]] for t in table]
        print(f"   corr(delta, {name}) = {corr(xs, ds):+.2f}   "
              f"mean {statistics.mean(xs):+.2f}")
    xs = [t["yarn"] for t in table]
    print(f"   corr(delta, count(YARN_STORE in day-8 shops)) = {corr(xs, ds):+.2f}")
    yarn_yes = [t["delta"] for t in table if t["yarn"] > 0]
    yarn_no = [t["delta"] for t in table if t["yarn"] == 0]
    print(f"   seeds WITH a YARN_STORE: n={len(yarn_yes)} mean delta "
          f"{statistics.mean(yarn_yes) if yarn_yes else float('nan'):+,.0f}")
    print(f"   seeds WITHOUT          : n={len(yarn_no)} mean delta "
          f"{statistics.mean(yarn_no) if yarn_no else float('nan'):+,.0f}")
    Path(args.out).write_text(json.dumps(table, indent=1))
    print("wrote", args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
