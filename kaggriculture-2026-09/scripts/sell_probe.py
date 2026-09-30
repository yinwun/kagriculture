#!/usr/bin/env python
"""Record per-step market SELL orders of two agents, to compare sell timing.

    python scripts/sell_probe.py A/main.py B/main.py --games 4 --out data/sell-probe.json

Both agents are wrapped so that every returned action is logged together with the
step and the pre-step inventory of the item being sold, i.e. the exact price the
first unit of that order transacts at.  This is the instrument for the sell-timing
mechanism: the market price is a pure function of `market.inventory`, and the town
shops consume inventory on steps where step % 4 == 0, so *when* a lot is sold
determines the average price obtained for it.
"""
import argparse
import importlib.util
import json
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod.agent


def wrap(path, name, log, tag):
    inner = load(path, name)

    def agent(observation, configuration=None):
        action = inner(observation, configuration)
        try:
            step = observation["step"] if isinstance(observation, dict) else observation.step
            inv = observation["market"]["inventory"]
            for o in (action or {}).get("market") or []:
                if o and o[0] == "SELL" and len(o) >= 3:
                    log.append({"tag": tag, "step": step, "item": o[1], "qty": o[2],
                                "inv": inv.get(o[1])})
        except Exception:
            pass
        return action
    return agent


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("a")
    ap.add_argument("b")
    ap.add_argument("--games", type=int, default=4)
    ap.add_argument("--start", type=int, default=9000)
    ap.add_argument("--out", default="data/sell-probe.json")
    args = ap.parse_args()
    from kaggle_environments import make

    rows = []
    for g in range(args.games):
        log = []
        agents = [wrap(args.a, f"probe_a_{g}", log, "A"), wrap(args.b, f"probe_b_{g}", log, "B")]
        if g % 2:
            agents.reverse()
        env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": args.start + g},
                   debug=True)
        env.run(agents)
        final = env.steps[-1]
        # env.steps[i][p]["action"] is the action applied at step i
        applied = {("A" if (p == 0) != bool(g % 2) else "B"): [] for p in (0, 1)}
        for t, step in enumerate(env.steps):
            for p in (0, 1):
                tag = "A" if (p == 0) != bool(g % 2) else "B"
                act = step[p].get("action")
                inv = step[p]["observation"]["market"]["inventory"]
                for o in (act or {}).get("market") or []:
                    if o and o[0] == "SELL" and len(o) >= 3:
                        applied[tag].append({"step": t, "item": o[1], "qty": o[2],
                                             "inv": inv.get(o[1])})
        rows.append({"game": g, "seed": args.start + g,
                     "bank": {("A" if p == 0 else "B"): final[p]["reward"]
                              for p in (0, 1)},
                     "orders": applied})
        print(f"game {g}: A bank {rows[-1]['bank']['A']:,.0f}  B bank {rows[-1]['bank']['B']:,.0f}"
              f"  A orders {len(applied['A'])}  B orders {len(applied['B'])}", flush=True)
    Path(args.out).write_text(json.dumps(rows))

    print("\n=== sell-order statistics (per agent, all games) ===")
    for tag in ("A", "B"):
        qs, by_item, by_par = [], {}, {0: [0, 0], 1: [0, 0], 2: [0, 0], 3: [0, 0]}
        tot = {}
        for r in rows:
            for o in r["orders"][tag]:
                qs.append(o["qty"])
                by_item.setdefault(o["item"], []).append(o["qty"])
                tot[o["item"]] = tot.get(o["item"], 0) + o["qty"]
                by_par[o["step"] % 4][0] += 1
                by_par[o["step"] % 4][1] += o["qty"]
        if not qs:
            print(f"{tag}: no sell orders recorded")
            continue
        print(f"\n{tag}: orders {len(qs)}  qty mean {statistics.mean(qs):.2f} median "
              f"{statistics.median(qs):.0f} max {max(qs)}")
        print(f"   step%4 distribution (count, qty): " +
              "  ".join(f"{k}:{v[0]}/{v[1]}" for k, v in sorted(by_par.items())))
        top = sorted(tot.items(), key=lambda kv: -kv[1])[:6]
        print(f"   units sold: " + "  ".join(f"{i}={n}" for i, n in top))
        for i, _ in top[:4]:
            v = by_item[i]
            print(f"     {i:11s} n={len(v):4d} mean {statistics.mean(v):7.2f} median "
                  f"{statistics.median(v):6.0f} max {max(v):4d}")
    print(f"\nwrote {args.out}")


if __name__ == "__main__":
    main()
