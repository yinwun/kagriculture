#!/usr/bin/env python
"""Attribute a top agent's plan choices to the world (prices) or to the rival.

This is the discriminating experiment for rank-1's identity.  We cannot re-run a
policy we do not own, so the test is done on the reconstructed corpus instead:
every episode in the corpus now reproduces exactly through scripts/replay_reproduce.py,
so we hold the exact state and the exact action of each agent at each step.

Two probes:

  A. attribution -- rank-correlate each PLAN descriptor of the target agent
     (herd mix, crop mix, hires, land days) against
       * WORLD features readable at the day-3/day-6 shop unlocks (product prices),
       * RIVAL features at day 9 (their herd, crops, cash),
     and report which family explains the target's choices.  A template +
     world-read agent shows strong world correlations and weak rival ones.
     Honest threshold: with n episodes, |rho| > r_crit is significant at p<0.05.

  B. endgame tracking -- at the last turns, does the target's sell amount track
     its OWN shed (terminal liquidation, i.e. a plan endpoint) or the RIVAL's
     stock (a spoiler rule)?  Reported as the correlation between liquidated
     quantity and each stock, plus who dumps first in the final window.

Usage:
  python scripts/plan_attribution.py --target Majkel1337 --rival-any
  python scripts/plan_attribution.py --target nickyl
"""
import argparse
import collections
import glob
import json
import math
from pathlib import Path

ANIMALS = ("COW", "SHEEP", "GOOSE")
CROPS = ("WHEAT", "CARROT", "MELON", "STRAWBERRY", "TOMATO")
PRODUCTS = ("WHEAT", "CARROT", "MELON", "STRAWBERRY", "TOMATO", "MILK", "WOOL",
            "EGG", "FERTILIZER")


def load(path):
    return json.loads(Path(path).read_text())


def counts(tiles):
    out = collections.Counter()
    for row in tiles:
        for cell in row:
            if not isinstance(cell, dict):
                continue
            if cell.get("animal"):
                out[cell["animal"]] += 1
            elif cell.get("crop"):
                out["CROP_" + cell["crop"]] += 1
    return out


def episode_features(d, p, rival_any=True):
    st = d["steps"]
    n = len(st)
    teams = d["info"]["TeamNames"]
    q = 1 - p
    f = {"episode": d["info"]["EpisodeId"], "team": teams[p], "rival": teams[q],
         "reward": d["rewards"][p]}

    # ---- plan descriptors, accumulated over the whole episode
    hires = 0
    sold = collections.Counter()
    land_days = []
    plants = collections.Counter()
    seen_tiles = set()
    prev_quad = None
    first_sell = {}
    for t in range(n):
        e = st[t][p]
        o = e.get("observation")
        a = e.get("action") or {}
        for m in (a.get("market") or []):
            if not isinstance(m, list) or not m:
                continue
            if m[0] == "HIRE":
                hires += 1
            elif m[0] == "SELL" and len(m) >= 3:
                try:
                    qty = int(m[2])
                except (TypeError, ValueError):
                    qty = 0
                sold[m[1]] += qty
                first_sell.setdefault(m[1], o["day"] if o else None)
        if not o:
            continue
        farm = o["farms"][p]
        quads = len(farm.get("unlocked_quadrants") or [])
        if prev_quad is None:
            prev_quad = quads
        elif quads != prev_quad:
            land_days.append(o["day"])
            prev_quad = quads
        for r, row in enumerate(farm["tiles"]):
            for c, cell in enumerate(row):
                if isinstance(cell, dict) and cell.get("kind") == "PLANT" and (r, c) not in seen_tiles:
                    seen_tiles.add((r, c))
                    plants[cell["crop"]] += 1
    final = counts(st[n - 1][p]["observation"]["farms"][p]["tiles"])
    for a in ANIMALS:
        f["final_" + a] = final[a]
    for c in CROPS:
        f["planted_" + c] = plants[c]
    f["hires"] = hires
    f["land_days"] = land_days
    for k in ("MILK", "WOOL", "STRAWBERRY", "WHEAT", "FERTILIZER", "MELON"):
        f["first_sell_" + k] = first_sell.get(k)

    # ---- WORLD features: prices at the shop-unlock turns
    for day, tag in ((3, "d3"), (6, "d6"), (8, "d8")):
        o = st[day * 24][0].get("observation")
        for k, v in (o["market"]["prices"] if o else {}).items():
            f[f"price_{tag}_{k}"] = v
        shops = o["town"]["unlocked_shops"] if o else []
        f[f"shops_{tag}"] = list(shops)

    # ---- RIVAL features at day 9
    o9 = st[9 * 24][q].get("observation")
    if o9:
        rc = counts(o9["farms"][q]["tiles"])
        for a in ANIMALS:
            f["rival_" + a] = rc[a]
        for c in CROPS:
            f["rival_planted_" + c] = rc["CROP_" + c]
        f["rival_money_d9"] = o9["farms"][q]["money"]
    rival_sold = collections.Counter()
    for t in range(n):
        for m in (st[t][q].get("action") or {}).get("market") or []:
            if isinstance(m, list) and len(m) >= 3 and m[0] == "SELL":
                try:
                    rival_sold[m[1]] += int(m[2])
                except (TypeError, ValueError):
                    pass
    for k in PRODUCTS:
        f["rival_sold_" + k] = rival_sold[k]

    # ---- B. endgame tracking over the last two days
    f["endgame"] = endgame_features(st, p, q)
    return f


def endgame_features(st, p, q, days=2):
    n = len(st)
    start = (30 - days) * 24
    own = collections.Counter()
    riv = collections.Counter()
    own_dump_step = {}
    riv_dump_step = {}
    last_shed = collections.Counter()
    for t in range(start, n):
        o = st[t][p].get("observation")
        a = st[t][p].get("action") or {}
        if o:
            last_shed = collections.Counter(
                {k: v for k, v in o["private"]["shed"].items() if v})
        for m in (a.get("market") or []):
            if isinstance(m, list) and len(m) >= 3 and m[0] == "SELL":
                try:
                    own[m[1]] += int(m[2])
                except (TypeError, ValueError):
                    pass
                own_dump_step.setdefault(m[1], t)
        for m in ((st[t][q].get("action") or {}).get("market") or []):
            if isinstance(m, list) and len(m) >= 3 and m[0] == "SELL":
                try:
                    riv[m[1]] += int(m[2])
                except (TypeError, ValueError):
                    pass
                riv_dump_step.setdefault(m[1], t)
    return {
        "own_sold_unmatched": sum(own[k] for k in ("STRAWBERRY", "MILK", "WOOL", "MELON")),
        "rival_sold_premium": sum(riv[k] for k in ("STRAWBERRY", "MILK", "WOOL", "MELON")),
        "own_final_shed": dict(last_shed),
        "own_final_shed_units": sum(last_shed.values()),
        "own_dump_step": own_dump_step,
        "rival_dump_step": riv_dump_step,
    }


def rank(xs):
    order = sorted(range(len(xs)), key=lambda i: xs[i])
    r = [0.0] * len(xs)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and xs[order[j + 1]] == xs[order[i]]:
            j += 1
        avg = (i + j) / 2 + 1
        for k in range(i, j + 1):
            r[order[k]] = avg
        i = j + 1
    return r


def spearman(a, b):
    pairs = [(x, y) for x, y in zip(a, b) if x is not None and y is not None]
    if len(pairs) < 4:
        return None, len(pairs)
    xs = rank([x for x, _ in pairs])
    ys = rank([y for _, y in pairs])
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    dx = math.sqrt(sum((x - mx) ** 2 for x in xs))
    dy = math.sqrt(sum((y - my) ** 2 for y in ys))
    return (num / (dx * dy) if dx and dy else None), n


def r_crit(n, alpha=0.05):
    # two-sided Spearman critical value via t-approximation
    if n < 5:
        return None
    t = {5: 2.571, 6: 2.447, 7: 2.365, 8: 2.306, 9: 2.262, 10: 2.228,
         12: 2.179, 15: 2.131, 20: 2.086}.get(n, 1.96)
    return t / math.sqrt(n - 2 + t * t)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", default="Majkel1337")
    ap.add_argument("paths", nargs="*", default=["data/top/episode-*.json",
                                                 "data/replays/episode-*.json"])
    args = ap.parse_args()

    rows = []
    seen = set()
    for pat in args.paths:
        for path in sorted(glob.glob(pat)):
            d = load(path)
            eid = d["info"]["EpisodeId"]
            for p, t in enumerate(d["info"]["TeamNames"]):
                if t != args.target or (eid, p) in seen:
                    continue
                seen.add((eid, p))
                rows.append(episode_features(d, p))
    if len(rows) < 5:
        raise SystemExit(f"only {len(rows)} episodes for {args.target}; need >=5")

    print(f"target: {args.target}   episodes: {len(rows)}   "
          f"|rho| significant at p<0.05: > {r_crit(len(rows)):.2f}")
    print(f"opponents: {sorted({r['rival'] for r in rows})}")

    targets = [k for k in ("final_COW", "final_SHEEP", "final_GOOSE", "hires",
                           "planted_STRAWBERRY", "planted_MELON", "planted_WHEAT")
               if any(r.get(k) for r in rows)]
    world = [k for k in rows[0] if k.startswith("price_d8_") or k.startswith("price_d6_")]
    rival = [k for k in rows[0] if k.startswith("rival_") and not k.startswith("rival_sold_")]

    print("\nA. attribution of plan descriptors (top |rho| per descriptor)")
    print(f"{'descriptor':22s} {'best WORLD feature':38s} {'rho':>6s}   {'best RIVAL feature':32s} {'rho':>6s}")
    for tgt in targets:
        y = [r.get(tgt) for r in rows]
        bestw = bestr = (None, None)
        for k in world:
            rho, n = spearman([r.get(k) for r in rows], y)
            if rho is not None and (bestw[1] is None or abs(rho) > abs(bestw[1])):
                bestw = (k, rho)
        for k in rival:
            rho, n = spearman([r.get(k) for r in rows], y)
            if rho is not None and (bestr[1] is None or abs(rho) > abs(bestr[1])):
                bestr = (k, rho)
        fw = f"{bestw[0]} ({bestw[1]:+.2f})" if bestw[0] else "-"
        fr = f"{bestr[0]} ({bestr[1]:+.2f})" if bestr[0] else "-"
        print(f"{tgt:22s} {bestw[0] or '-':38s} {bestw[1] if bestw[1] is not None else 0:+6.2f}   "
              f"{bestr[0] or '-':32s} {bestr[1] if bestr[1] is not None else 0:+6.2f}")

    # aggregate: max |rho| within each family, per descriptor
    print("\n   per-descriptor max |rho| by family (world / rival):")
    for tgt in targets:
        y = [r.get(tgt) for r in rows]
        mw = max((abs(spearman([r.get(k) for r in rows], y)[0] or 0) for k in world), default=0)
        mr = max((abs(spearman([r.get(k) for r in rows], y)[0] or 0) for k in rival), default=0)
        verdict = "WORLD" if mw > mr else "RIVAL"
        print(f"     {tgt:22s} world={mw:.2f}  rival={mr:.2f}   -> {verdict}")

    print("\nB. endgame tracking (last 2 days)")
    print(f"{'episode':10s} {'own premium sold':>16s} {'rival premium sold':>18s} "
          f"{'own shed left':>13s} {'own 1st dump':>12s} {'rival 1st dump':>14s}")
    for r in rows:
        eg = r["endgame"]
        od = min(eg["own_dump_step"].values()) if eg["own_dump_step"] else None
        rd = min(eg["rival_dump_step"].values()) if eg["rival_dump_step"] else None
        print(f"{r['episode']:10d} {eg['own_sold_unmatched']:16d} {eg['rival_sold_premium']:18d} "
              f"{eg['own_final_shed_units']:13d} {str(od):>12s} {str(rd):>14s}")
    own = [r["endgame"]["own_sold_unmatched"] for r in rows]
    riv = [r["endgame"]["rival_sold_premium"] for r in rows]
    rho, n = spearman(own, riv)
    print(f"\n   rho(own endgame sells, rival endgame sells) = {rho:+.2f} (n={n})"
          f"   [null ~0 if the endgame is own-inventory driven, strongly + if it races the rival]")

    out = Path("data/plan_attribution.json")
    out.write_text(json.dumps(rows, indent=1, default=str))
    print(f"\nwrote {out}")


if __name__ == "__main__":
    main()
