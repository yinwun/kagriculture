#!/usr/bin/env python
"""Aggregate data/replay-attr-*.json into the Task-23 cause table.

Classes, in priority order (first match wins) -- all numbers are per game:
  PRODUCT   one item explains >= 50 % of the liquid-worth deficit
  VOLUME    opponent out-produced us (units_opp/units_me > 1.05) and the volume
            difference at our own average price explains >= 50 % of the deficit
  PRICE     units within +-5 % but our average realised price is >= 3 % lower
  LATE      the deficit first opens at day >= 8
  EARLY     the deficit first opens at day <= 2 (a near-tie decided early)
  OTHER     none of the above

Usage: python scripts/replay_causes.py
"""
import collections
import json
import statistics as st
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CLASS_ORDER = ["PRODUCT", "VOLUME", "PRICE", "LATE", "EARLY", "OTHER"]


def items_of(g, who):
    out = {}
    for k, v in g["items"].items():
        w, it = k.split(":", 1)
        if w != who:
            continue
        out[it] = {"units": v.get("units", 0), "rev": v.get("rev", 0.0),
                   "spend": v.get("spend", 0.0), "buy_units": v.get("buy_units", 0)}
    return out


def classify(g, force=False):
    me, op = items_of(g, "me"), items_of(g, "opp")
    gap = g["final_gap"]
    if gap >= 0 and not force:
        return "WIN", {}
    # a money-loss can still show a POSITIVE liquid gap (we lost on cash but held more
    # goods): force=True keeps it in the loss analysis with a floor of 1 coin
    deficit = max(-gap, 1.0)
    keys = set(me) | set(op)
    per_item = {}
    for it in keys:
        m, o = me.get(it, {}), op.get(it, {})
        net_m = m.get("rev", 0.0) - m.get("spend", 0.0)
        net_o = o.get("rev", 0.0) - o.get("spend", 0.0)
        per_item[it] = net_m - net_o
    worst = sorted(per_item.items(), key=lambda kv: kv[1])[:3]
    u_m = sum(v.get("units", 0) for v in me.values())
    u_o = sum(v.get("units", 0) for v in op.values())
    r_m = sum(v.get("rev", 0.0) for v in me.values())
    r_o = sum(v.get("rev", 0.0) for v in op.values())
    p_m = (r_m / u_m) if u_m else 0.0
    p_o = (r_o / u_o) if u_o else 0.0
    vol_gain = (u_o - u_m) * p_m if p_m else 0.0
    tags = []
    if worst and deficit > 0 and -worst[0][1] / deficit >= 0.5:
        tags.append("PRODUCT")
    if u_m and u_o / u_m > 1.05 and vol_gain / deficit >= 0.5:
        tags.append("VOLUME")
    if u_m and abs(u_o / u_m - 1) <= 0.05 and p_m and (p_o / p_m - 1) >= 0.03:
        tags.append("PRICE")
    d = g["first_deficit_day"]
    if d is not None and d >= 8:
        tags.append("LATE")
    if d is not None and d <= 2:
        tags.append("EARLY")
    primary = next((t for t in CLASS_ORDER if t in tags), "OTHER")
    return primary, {"tags": tags, "deficit": deficit, "worst_items": worst,
                     "units": (u_m, u_o), "avg_price": (p_m, p_o),
                     "rev": (r_m, r_o), "vol_gain": vol_gain,
                     "first_day": d, "margin": g["margin"]}


def group(games, lo, hi):
    return [g for g in games if lo <= g["margin"] < hi]


def day_table(games, label):
    days = sorted({int(d) for g in games for d in g["day_gap"]})
    print(f"\n  mean per-day liquid net-worth gap (me - opp), {label} (n={len(games)}):")
    print(f"    {'day':>4} " + " ".join(f"{d:>8}" for d in days))
    row_mean, row_sd = [], []
    for d in days:
        vals = [g["day_gap"][str(d)] for g in games if str(d) in g["day_gap"]]
        row_mean.append(st.mean(vals) if vals else 0)
        row_sd.append(st.pstdev(vals) if len(vals) > 1 else 0)
    print(f"    {'mean':>4} " + " ".join(f"{v:>+8,.0f}" for v in row_mean))
    print(f"    {'sd':>4} " + " ".join(f"{v:>8,.0f}" for v in row_sd))
    first = next((d for d, v in zip(days, row_mean) if v < 0), None)
    print(f"    first day the MEAN gap is negative: day {first}")
    return {"days": days, "mean": row_mean, "sd": row_sd, "first_neg_day": first}


def report(ref, games, label):
    print(f"\n{'='*104}\n{label} (ref {ref}): {len(games)} attributed games")
    win = group(games, 0.0001, 10 ** 9)
    near = group(games, -500, 0.0001)
    loss = group(games, -10 ** 9, -500)
    for name, gg in (("losses (<-500)", loss), ("near-losses (-500..0)", near), ("wins (>0)", win)):
        if not gg:
            continue
        gaps = [g["final_gap"] for g in gg]
        days = [g["first_deficit_day"] for g in gg if g["first_deficit_day"] is not None]
        print(f"  {name:22} n={len(gg):3}  liquid gap mean {st.mean(gaps):+8,.0f} "
              f"median {st.median(gaps):+8,.0f}  first-deficit day: "
              f"{dict(sorted(collections.Counter(days).items()))}")
    tabs = {}
    for name, gg in (("losses", loss), ("near", near), ("wins", win)):
        if gg:
            tabs[name] = day_table(gg, f"{label} {name}")
    # ---- cause table over losses (and near-losses)
    causes = collections.defaultdict(list)
    detail = []
    for g in loss + near:
        prim, meta = classify(g, force=True)
        causes[prim].append(meta)
        detail.append({"episode": g["episode"], "margin": g["margin"], "primary": prim, **meta})
    print(f"\n  CAUSE TABLE over {len(loss+near)} losses+near-losses:")
    print(f"    {'class':9} {'games':>6} {'mean deficit':>13} {'median':>9} "
          f"{'worst item (mean contrib)':>34}  tags")
    for c in CLASS_ORDER:
        ms = causes.get(c)
        if not ms:
            continue
        ds = [m["deficit"] for m in ms]
        wc = collections.Counter(m["worst_items"][0][0] for m in ms if m["worst_items"])
        tagc = collections.Counter(t for m in ms for t in m["tags"])
        print(f"    {c:9} {len(ms):>6} {st.mean(ds):>+13,.0f} {st.median(ds):>+9,.0f} "
              f"{wc.most_common(1)[0][0] if wc else '-':>34}  {dict(tagc)}")
    # ---- item-level attribution over losses+near
    net = collections.defaultdict(list)
    for g in loss + near:
        me, op = items_of(g, "me"), items_of(g, "opp")
        for it in set(me) | set(op):
            m, o = me.get(it, {}), op.get(it, {})
            net[it].append((m.get("rev", 0.0) - m.get("spend", 0.0))
                           - (o.get("rev", 0.0) - o.get("spend", 0.0)))
    print(f"\n  ITEM-LEVEL net contribution (my revenue - my spend) - (opp revenue - opp spend),"
          f" mean over {len(loss+near)} losses+near-losses:")
    print(f"    {'item':12} {'mean net':>10} {'median':>9} {'neg games':>10}")
    for it, vals in sorted(net.items(), key=lambda kv: st.mean(kv[1])):
        print(f"    {it:12} {st.mean(vals):>+10,.0f} {st.median(vals):>+9,.0f} "
              f"{sum(1 for v in vals if v < 0):>4}/{len(vals):<5}")
    # ---- volume vs price decomposition of the top deficit items
    print(f"\n  VOLUME vs PRICE decomposition over {len(loss+near)} losses+near-losses"
          f" (symmetric: vol = (u_me-u_opp)*p_avg, price = (p_me-p_opp)*u_avg):")
    print(f"    {'item':12} {'u_me':>7} {'u_opp':>7} {'p_me':>7} {'p_opp':>7} "
          f"{'vol effect':>11} {'price effect':>13} {'net':>9}")
    for it, _ in sorted(net.items(), key=lambda kv: st.mean(kv[1]))[:6]:
        row = []
        for g in loss + near:
            me, op = items_of(g, "me"), items_of(g, "opp")
            m, o = me.get(it, {}), op.get(it, {})
            um, uo = m.get("units", 0), o.get("units", 0)
            pm = (m.get("rev", 0.0) / um) if um else 0.0
            po = (o.get("rev", 0.0) / uo) if uo else 0.0
            p_avg, u_avg = (pm + po) / 2, (um + uo) / 2
            row.append((um, uo, pm, po, (um - uo) * p_avg, (pm - po) * u_avg))
        if not row:
            continue
        col = list(zip(*row))
        mu = [st.mean(c) for c in col]
        print(f"    {it:12} {mu[0]:>7.1f} {mu[1]:>7.1f} {mu[2]:>7.1f} {mu[3]:>7.1f} "
              f"{mu[4]:>+11,.0f} {mu[5]:>+13,.0f} {mu[4]+mu[5]:>+9,.0f}")
    # ---- layer signature
    st_me = {k: st.mean([g["structure"][k] for g in games]) for k in
             ("sell_steps", "multi_sell_steps", "wool_sell_steps")}
    wool_units = st.mean([items_of(g, "me").get("WOOL", {}).get("units", 0) for g in games])
    print(f"\n  LAYER SIGNATURE (mean per game over all {len(games)} games): "
          f"SELL steps {st_me['sell_steps']:.0f}/719, multi-SELL steps {st_me['multi_sell_steps']:.0f}, "
          f"WOOL-SELL steps {st_me['wool_sell_steps']:.0f}, WOOL units sold {wool_units:.0f}")
    disc = sum(sum(g["discards_by_day"].values()) for g in games)
    print(f"  shed-overflow discards total across games: {disc} units")
    return {"label": label, "n": len(games), "tables": tabs,
            "causes": {c: {"games": len(v), "mean_deficit": st.mean([m["deficit"] for m in v]),
                           "median_deficit": st.median([m["deficit"] for m in v])}
                       for c, v in causes.items()},
            "detail": detail, "signature": st_me, "wool_units": wool_units,
            "discards": disc}


def main():
    out = {}
    for ref, f, label in (("56422944", "data/replay-attr-newline.json", "56422944 = composite + our two layers"),
                          ("56409633", "data/replay-attr-composite.json", "56409633 = plain composite")):
        p = ROOT / f
        if not p.exists():
            continue
        games = json.loads(p.read_text())
        # games list may be a dict {ref: [games]} or a list
        if isinstance(games, dict):
            games = next(iter(games.values()))
        gated = [g for g in games if g.get("money_match")]
        print(f"\n{label}: {len(games)} games, {len(gated)} pass the bank-reproduction gate; "
              f"{len([g for g in games if g['first_deficit_day'] is not None])} without a deficit day")
        out[ref] = report(ref, gated, label)
    (ROOT / "data" / "replay-causes.json").write_text(json.dumps(out, indent=1, default=str))
    print("\nwrote data/replay-causes.json")


if __name__ == "__main__":
    main()
