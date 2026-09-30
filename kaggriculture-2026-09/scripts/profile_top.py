#!/usr/bin/env python
"""Profile a top team's play from a replay: the full configuration side by side.

For each player it reports land, animals, crop throughput, water/fertilizer use,
labour, the reconciled revenue/spend (see scripts/audit_market.py) and the final
prices, so the gap to the leader can be read off directly instead of guessed.

Usage:
  python scripts/profile_top.py data/top/episode-*.json
  python scripts/profile_top.py data/top/episode-X.json --team 16718819
"""
import argparse
import collections
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from audit_market import CROPS, ANIMALS, LAND_PRICES, hire_cost  # noqa: E402

STRUCTS = {"COOP", "PASTURE"}


def profile(steps, player):
    obs_seq = [steps[t][player].get("observation") for t in range(len(steps))]
    obs_seq = [o for o in obs_seq if o]
    first, last = obs_seq[0], obs_seq[-1]
    out = {"start": float(first["farms"][player]["money"]),
           "wallet": float(last["farms"][player]["money"]),
           "quadrants": len(last["farms"][player]["unlocked_quadrants"]),
           "animals": collections.Counter(), "structs": 0, "empty": 0,
           "planted": 0, "ops": collections.Counter(), "plants": 0, "harv": 0,
           "seed_buys": collections.Counter(), "animal_buys": collections.Counter(),
           "hires": 0, "spend": collections.Counter(), "revenue": 0.0}
    for row in last["farms"][player]["tiles"]:
        for t in row:
            if isinstance(t, dict) and "animal" in t:
                out["animals"][t["animal"]] += 1
            elif isinstance(t, dict) and t.get("kind") in STRUCTS:
                out["structs"] += 1
            elif isinstance(t, dict) and t.get("kind") == "PLANT":
                out["planted"] += 1
            elif t is None:
                out["empty"] += 1
    hc = collections.Counter()
    for i in range(1, len(obs_seq)):
        prev, cur = obs_seq[i - 1], obs_seq[i]
        act = steps[i - 1][player].get("action") or {}
        s = 0.0
        for od in (act.get("market") or []):
            if not isinstance(od, list) or not od:
                continue
            op = od[0]
            if op == "BUY_SEED" and len(od) > 2:
                c = CROPS.get(od[1], 0) * int(od[2] or 0)
                s += c
                out["spend"]["seed"] += c
                out["seed_buys"][od[1]] += int(od[2] or 0)
            elif op == "BUY_ANIMAL" and len(od) > 2:
                c = ANIMALS.get(od[1], 0) * int(od[2] or 0)
                s += c
                out["spend"]["animal"] += c
                out["animal_buys"][od[1]] += int(od[2] or 0)
            elif op == "BUY_PRODUCT" and len(od) > 2:
                c = cur["market"]["prices"].get(od[1], 0) * int(od[2] or 0)
                s += c
                out["spend"]["buy_" + str(od[1])] += c
            elif op == "BUY_LAND":
                n = len(prev["farms"][player].get("unlocked_quadrants") or []) - 1
                if 0 <= n < len(LAND_PRICES):
                    s += LAND_PRICES[n]
                    out["spend"]["land"] += LAND_PRICES[n]
            elif op == "HIRE":
                c = hire_cost(hc[cur["day"]])
                hc[cur["day"]] += 1
                s += c
                out["spend"]["hire"] += c
                out["hires"] += 1
        out["revenue"] += (float(cur["farms"][player]["money"])
                           - float(prev["farms"][player]["money"]) + s)
        for c in [act.get("farmer")] + list(act.get("hands") or []):
            if isinstance(c, list) and c:
                out["ops"][c[0]] += 1
    return out


def fmt(prof):
    an = ",".join(f"{k}:{v}" for k, v in sorted(prof["animals"].items())) or "-"
    sp = " ".join(f"{k}:{v:,.0f}" for k, v in sorted(prof["spend"].items(),
                                                     key=lambda kv: -kv[1])[:5])
    ops = prof["ops"]
    return (f"wallet {prof['wallet']:9,.0f} | land {prof['quadrants']} | rev {prof['revenue']:8,.0f} "
            f"| spend {sum(prof['spend'].values()):8,.0f} ({sp})\n"
            f"      animals {an} structs {prof['structs']} planted {prof['planted']} empty {prof['empty']}\n"
            f"      ops WATER {ops['WATER']} HARVEST {ops['HARVEST']} PLANT {ops['PLANT']} "
            f"PASS {ops['PASS']} CARE {ops['CARE']} FEED {ops['FEED']} "
            f"COLLECT_FERT {ops['COLLECT_FERTILIZER']} FERTILIZE {ops['FERTILIZE']} "
            f"hires {prof['hires']}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("replays", nargs="+")
    ap.add_argument("--team", type=int, default=None)
    args = ap.parse_args()
    lb = {int(r["teamId"]): (r["teamName"], float(r["score"]))
          for r in json.load(open(Path(__file__).resolve().parent.parent /
                                  "data" / "leaderboard.json")) if r.get("score")}
    for path in args.replays:
        d = json.loads(Path(path).read_text())
        steps = d["steps"]
        n = len(steps[0])
        rewards = [steps[-1][p].get("reward") for p in range(n)]
        names = []
        for p in range(n):
            nm = None
            for f in (Path(__file__).resolve().parent.parent / "data" / "top").glob("candidates-*.json"):
                for r in json.loads(f.read_text()):
                    if r["episode"] == int(Path(path).stem.split("-")[1]):
                        for tid, rw in r["rewards"].items():
                            if rw == rewards[p]:
                                nm = lb.get(tid, (str(tid), 0))
                        break
            names.append(nm or ("?", 0))
        print(f"=== {Path(path).name} ===")
        for p in range(n):
            print(f"  P{p} {names[p][0]} (ladder {names[p][1]:.0f}) reward {rewards[p]:,.0f}")
            print(f"      {fmt(profile(steps, p))}")
        prices = steps[-1][0]["observation"]["market"]["prices"]
        print(f"  final prices: {{k: prices[k] for k in sorted(prices)}}"
              .replace("{k: prices[k] for k in sorted(prices)}",
                       str({k: prices[k] for k in sorted(prices)})))


if __name__ == "__main__":
    main()
