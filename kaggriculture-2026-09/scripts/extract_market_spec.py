#!/usr/bin/env python
"""Extract the champion's *plan semantics* -- per-day hire / buy / sell schedule.

Rationale (REPORT-tape-replan-methodology.md §17): a from-scratch market policy lost
~20 configurations against the champion, all 0/N, and the head-to-head revenue
attribution showed why -- the tape sells few units at prices far above base (wheat
94, strawberry 138, melon 239) while our planner dumps many units at base.  The tape's
market behaviour is *co-adapted* with its labour, so the only way to inherit it
without inheriting its 7.6% idle is to lift the schedule itself:

    for each in-game day:  how many hands to hire, which seeds/animals/land to buy,
    and how many units of each product to sell.

Everything is emitted as a day-indexed spec (quantities, not positions), so our own
scheduler can execute it against a different farm.

Usage:
  python scripts/extract_market_spec.py --agent data/tapeopt/rgcs/main.py --seed 9000 \
      --out data/market_spec.json
"""
import argparse
import collections
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def load(path):
    ns = {"__name__": "spec_mod"}
    exec(compile(Path(path).read_text(), str(path), "exec"), ns)
    return ns["agent"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--agent", default=str(ROOT / "data" / "tapeopt" / "rgcs" / "main.py"))
    ap.add_argument("--opp", default="starter")
    ap.add_argument("--seed", type=int, default=9000)
    ap.add_argument("--out", default=str(ROOT / "data" / "market_spec.json"))
    args = ap.parse_args()

    from kaggle_environments import make
    ag = load(args.agent)
    opp = args.opp
    if opp != "starter":
        opp = load(opp)

    def seat0(obs, configuration=None):
        return ag(obs, configuration)

    env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": args.seed})
    env.run([seat0, opp])

    spec = collections.defaultdict(lambda: {"hire": 0, "buy_seed": collections.Counter(),
                                            "buy_animal": collections.Counter(),
                                            "buy_product": collections.Counter(),
                                            "buy_land": 0, "sell": collections.Counter(),
                                            "plant": collections.Counter(),
                                            "place": collections.Counter()})
    for t in range(len(env.steps)):
        o = env.steps[t][0].get("observation")
        a = env.steps[t][0].get("action") or {}
        if not o:
            continue
        day = o["day"]
        for m in (a.get("market") or []):
            if not (isinstance(m, list) and m):
                continue
            if m[0] == "HIRE":
                spec[day]["hire"] += 1
            elif m[0] == "BUY_LAND":
                spec[day]["buy_land"] += 1
            elif m[0] in ("BUY_SEED", "BUY_ANIMAL", "BUY_PRODUCT") and len(m) > 2:
                spec[day][m[0].lower()][m[1]] += int(m[2])
            elif m[0] == "SELL" and len(m) > 2:
                spec[day]["sell"][m[1]] += int(m[2])
        for cmd in [a.get("farmer") or []] + list(a.get("hands") or []):
            if isinstance(cmd, list) and cmd:
                if cmd[0] == "PLANT" and len(cmd) > 1:
                    spec[day]["plant"][cmd[1]] += 1
                elif cmd[0] == "PLACE" and len(cmd) > 1:
                    spec[day]["place"][cmd[1]] += 1

    out = {}
    for day, d in sorted(spec.items()):
        out[str(day)] = {"hire": d["hire"], "buy_land": d["buy_land"],
                         "buy_seed": dict(d["buy_seed"]), "buy_animal": dict(d["buy_animal"]),
                         "buy_product": dict(d["buy_product"]), "sell": dict(d["sell"]),
                         "plant": dict(d["plant"]), "place": dict(d["place"])}
    Path(args.out).write_text(json.dumps(out, indent=1))
    print(f"wrote {args.out} ({len(out)} days)")
    print(f"{'day':>3s} {'hire':>4s} {'land':>4s} {'seeds':>22s} {'animals':>12s} "
          f"{'sell units':>10s}  top sells")
    for day in sorted(out, key=int):
        d = out[day]
        sells = sum(d["sell"].values())
        top = ", ".join(f"{k}:{v}" for k, v in sorted(d["sell"].items(), key=lambda kv: -kv[1])[:3])
        print(f"{day:>3s} {d['hire']:4d} {d['buy_land']:4d} {str(d['buy_seed']):>22s} "
              f"{str(d['buy_animal']):>12s} {sells:10d}  {top}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
