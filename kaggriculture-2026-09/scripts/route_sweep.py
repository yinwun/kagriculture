#!/usr/bin/env python
"""Learn the shop->route table by A/B testing routes on identical towns.

The random seed fixes the town (its shop unlock schedule), so forcing different
tapes on the SAME seed is a controlled experiment: only our own build changes,
the opponent is held fixed.  That gives a local signal for the one decision the
whole agent family is built around -- which tape to replay for this town.

Each candidate is run in its own freshly imported module (the chassis holds the
router as an instance attribute, so patching it per module is safe).

Usage:
  python scripts/route_sweep.py --seeds 6 --start 500 --routes 0,101,105,123 --opponent <main.py>
Output: data/route_sweep.json + a printed table of our wallet per (seed, route).
"""
import argparse
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
V42 = (ROOT / "data" / "league" /
       "ahmedberatozer_kaggriculture-v42-production-that-fits-the-marke" / "main.py")
_counter = [0]


def load_agent(path, route=None):
    """Fresh module instance; optionally force one tape route."""
    _counter[0] += 1
    name = f"agent_{path.stem}_{_counter[0]}"
    spec = importlib.util.spec_from_file_location(name, str(path))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    if route is not None:
        mod._IMPL.chassis.router = (lambda obs, step, state, r=route: r)
    return mod.agent


def shops_at(env, player, step):
    o = env.steps[step][player]["observation"]
    return tuple((o.get("town") or {}).get("unlocked_shops") or [])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, default=6)
    ap.add_argument("--start", type=int, default=500)
    ap.add_argument("--routes", default="0,101,105,123")
    ap.add_argument("--opponent", default=str(V42))
    ap.add_argument("--out", default="data/route_sweep.json")
    args = ap.parse_args()
    if args.routes.strip() == "all":
        import re as _re
        src = V42.read_text()
        roles = sorted({int(x) for x in _re.findall(r'\"(\d+)\": \[', src)})
        if not roles:
            import base64, zlib
            b = _re.search(r"b85decode\('([^']+)'\)", src).group(1)
            roles = sorted(int(k) for k in json.loads(zlib.decompress(base64.b85decode(b)))["routes"])
    else:
        roles = [int(r) for r in args.routes.split(",") if r.strip()]
    from kaggle_environments import make
    rows = []
    for s in range(args.seeds):
        seed = args.start + s
        for r in roles:
            env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": seed})
            a = load_agent(V42, route=r)
            b = load_agent(Path(args.opponent))
            env.run([a, b])
            f = env.steps[-1]
            mine = f[0]["reward"] or 0
            theirs = f[1]["reward"] or 0
            shops6 = shops_at(env, 0, 6 * 24)
            rows.append({"seed": seed, "route": r, "mine": mine, "theirs": theirs,
                         "shops_day6": list(shops6)})
            print(f"seed {seed} route {r:>3}: mine {mine:9,.0f} theirs {theirs:9,.0f} "
                  f"shops@d6 {shops6}", flush=True)
    Path(ROOT / args.out).write_text(json.dumps(rows, indent=1))
    print(f"\nwrote {args.out}")
    # best route per seed
    by_seed = {}
    for r in rows:
        by_seed.setdefault(r["seed"], []).append(r)
    for seed, rs in sorted(by_seed.items()):
        rs.sort(key=lambda x: -x["mine"])
        best, worst = rs[0], rs[-1]
        gain = best["mine"] - worst["mine"]
        print(f"seed {seed}: best route {best['route']:>3} ({best['mine']:,.0f}) vs worst "
              f"{worst['route']:>3} ({worst['mine']:,.0f}) -> spread {gain:,.0f}")


if __name__ == "__main__":
    main()
