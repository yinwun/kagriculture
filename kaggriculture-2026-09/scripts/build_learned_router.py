#!/usr/bin/env python
"""Build a router whose shop->tape table is LEARNED from local A/B sweeps.

scripts/route_sweep.py forces each candidate tape on identical towns (the seed
fixes the town), so the measured wallet is a controlled comparison of the one
decision this whole agent family is built around: which tape to replay.

This builder turns those measurements into a replacement for the source
``_router``:

  * key = the first two unlocked shops at day 6, exactly the stock key
    (so coverage is complete: every key in the stock tables is a key here too);
  * value = the tape with the best measured wallet for that key, falling back to
    the stock table when the key was never swept;
  * the day-27 switch to tape 2 is preserved.

Usage:
  python scripts/build_learned_router.py --sweep data/route_sweep_all.json \
      --out data/tapeopt/router_learned [--min-gain 0]
"""
import argparse
import ast
import collections
import importlib.util
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASE = (ROOT / "data" / "league" /
        "ahmedberatozer_kaggriculture-v42-production-that-fits-the-marke" / "main.py")

ROUTER = '''def _router(observation, step, state):
    if step >= 648 and not state.get('day27'):
        state['route'] = 2
        state['day27'] = True
    elif step >= 144 and not state.get('day6'):
        shops = tuple((_get(_get(observation, 'town', {}), 'unlocked_shops', []) or [])[:2])
        use_new = shops.count('YARN_STORE') <= 0
        table = _LEARNED_SHOP_ROUTES if shops in _LEARNED_SHOP_ROUTES else (
            _R108_SHOP_ROUTES if use_new else _R110_OLD_SHOPS)
        state['route'] = table.get(shops, 100 if use_new else 0)
        state['day6'] = True
    return state.get('route', 0)
'''


def stock_tables():
    spec = importlib.util.spec_from_file_location("v42_stock", str(BASE))
    mod = importlib.util.module_from_spec(spec)
    sys.modules["v42_stock"] = mod
    spec.loader.exec_module(mod)
    return mod._R108_SHOP_ROUTES, mod._R110_OLD_SHOPS


def learn(rows, min_gain):
    """(shop pair at day 6) -> tape with the best mean wallet."""
    per = collections.defaultdict(lambda: collections.defaultdict(list))
    for r in rows:
        key = tuple(r["shops_day6"][:2]) if len(r["shops_day6"]) >= 2 else tuple(r["shops_day6"])
        per[key][r["route"]].append(r["mine"])
    table, detail = {}, {}
    for key, routes in per.items():
        means = {rt: sum(v) / len(v) for rt, v in routes.items()}
        best = max(means, key=lambda k: means[k])
        table[key] = best
        detail[key] = {"best": best, "mean": round(means[best]),
                       "n_routes": len(means), "n_seeds": len(next(iter(routes.values())))}
    return table, detail


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sweep", default="data/route_sweep_all.json")
    ap.add_argument("--out", default="data/tapeopt/router_learned")
    ap.add_argument("--min-gain", type=float, default=0.0)
    args = ap.parse_args()
    rows = json.loads((ROOT / args.sweep).read_text())
    table, detail = learn(rows, args.min_gain)
    stock_new, stock_old = stock_tables()
    covered = sum(1 for k in table if k in stock_new or k in stock_old)
    print(f"learned {len(table)} shop keys from {len(rows)} games "
          f"({covered} of them exist in the stock tables)")
    for k, v in sorted(detail.items(), key=lambda kv: -kv[1]["mean"])[:12]:
        old = stock_new.get(k, stock_old.get(k))
        gain = ""
        if old is not None:
            per = collections.defaultdict(list)
            for r in rows:
                key = tuple(r["shops_day6"][:2])
                if key == k:
                    per[r["route"]].append(r["mine"])
            if old in per:
                m_old = sum(per[old]) / len(per[old])
                gain = f"  stock {old} -> {m_old:,.0f}  gain {v['mean']-m_old:+,.0f}"
        print(f"  {str(k):44} -> {v['best']:>3} (mean {v['mean']:,}){gain}")

    src = BASE.read_text()
    pat = re.compile(r"def _router\(observation,step,state\):.*?(?=\n_R42_OPENING)", re.S)
    if not pat.search(src):
        raise SystemExit("could not find _router in the base source")
    literal = "_LEARNED_SHOP_ROUTES = " + repr({tuple(k): v for k, v in table.items()}) + "\n\n\n"
    out = pat.sub(literal + ROUTER + "\n", src, count=1)
    d = ROOT / args.out
    d.mkdir(parents=True, exist_ok=True)
    (d / "main.py").write_text(out)
    (d / "table.json").write_text(json.dumps({str(k): v for k, v in table.items()}, indent=1))
    print(f"wrote {d/'main.py'} ({len(out):,} bytes) and {d/'table.json'}")


if __name__ == "__main__":
    main()
