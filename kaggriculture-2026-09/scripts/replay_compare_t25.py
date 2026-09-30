#!/usr/bin/env python
"""Task-25 re-validation: old (Task-23/24 sample) vs new (overnight) games, same instruments.

For each ref and each window it reports
  * class sizes and the mean per-day liquid net-worth gap (which day the deficit opens);
  * item net (my revenue - my spend) - (opp ...) by outcome, and the loss-minus-win contrast;
  * the volume/price split for the leading deficit items;
  * the mirror share, measured from the action streams (identical market lists >= 716/720);
  * exact-margin frequencies (0, -50, |m| <= 60).

Usage: python scripts/replay_compare_t25.py
"""
import collections
import glob
import json
import statistics as st
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MIRROR_THRESH = 716


def load_games(path):
    d = json.loads(Path(path).read_text())
    games = next(iter(d.values())) if isinstance(d, dict) else d
    return [g for g in games if g.get("money_match")]


def margin_counts(raw_path):
    d = json.loads(Path(raw_path).read_text())
    ms = []
    for ep in d:
        ag = ep.get("agents") or []
        if len(ag) != 2:
            continue
        if any(a.get("reward") is None for a in ag):
            continue
        ref = str(ep["agents"][0].get("submissionId"))
        # margin is symmetric; use absolute ordering of the pair
        ms.append(float(ag[0]["reward"]) - float(ag[1]["reward"]))
    if not ms:
        return {}
    return {"n": len(ms), "zero": sum(1 for x in ms if x == 0),
            "minus50": sum(1 for x in ms if x == -50), "plus50": sum(1 for x in ms if x == 50),
            "abs_le60": sum(1 for x in ms if abs(x) <= 60),
            "median": st.median(ms)}


def mirror_stats(replay_dir, episodes=None):
    """Fraction of the selected games whose two seats played (nearly) the same market stream.
    data/replays holds exactly the old selection and data/replays-t25 the new one, so no
    id filter is needed."""
    same, n = 0, 0
    for p in glob.glob(str(Path(replay_dir) / "episode-*-replay.json")):
        try:
            d = json.loads(Path(p).read_text())
            st_ = d["steps"]
            ident = sum(1 for t in range(len(st_))
                        if (st_[t][0].get("action") or {}).get("market")
                        == (st_[t][1].get("action") or {}).get("market"))
            n += 1
            same += ident >= MIRROR_THRESH
        except Exception:
            continue
    return same, n


def items_of(g, who):
    out = {}
    for k, v in g["items"].items():
        w, it = k.split(":", 1)
        if w == who:
            out[it] = {"units": v.get("units", 0), "rev": v.get("rev", 0.0),
                       "spend": v.get("spend", 0.0)}
    return out


def net_items(g):
    me, op = items_of(g, "me"), items_of(g, "opp")
    return {it: (me.get(it, {}).get("rev", 0) - me.get(it, {}).get("spend", 0))
            - (op.get(it, {}).get("rev", 0) - op.get(it, {}).get("spend", 0))
            for it in set(me) | set(op)}


def window_report(label, games, replay_dir, episodes, raw_path):
    losses = [g for g in games if g["margin"] < -500]
    near = [g for g in games if -500 <= g["margin"] < 0]
    wins = [g for g in games if g["margin"] >= 0]
    print(f"\n{'='*104}\n{label}: {len(games)} attributed games "
          f"(loss {len(losses)}, near {len(near)}, win {len(wins)})  gate: all money_match")
    mc = margin_counts(raw_path)
    if mc:
        print(f"  exact-margin structure over the whole window ({mc['n']} games): "
              f"0 -> {mc['zero']} ({100*mc['zero']/mc['n']:.1f}%), -50 -> {mc['minus50']} "
              f"({100*mc['minus50']/mc['n']:.1f}%), +50 -> {mc['plus50']}, |m|<=60 -> {mc['abs_le60']} "
              f"({100*mc['abs_le60']/mc['n']:.1f}%), median margin {mc['median']:+,.0f}")
    same, n = mirror_stats(replay_dir, episodes)
    print(f"  mirror share (>= {MIRROR_THRESH}/720 identical market steps): {same}/{n} "
          f"({100*same/max(1,n):.1f}% of the selected games)")
    # day trajectory
    days = sorted({int(d) for g in games for d in g["day_gap"]})
    if days:
        print(f"  mean per-day liquid gap: " + " ".join(f"d{d}" for d in days))
        for name, gg in (("losses", losses), ("near", near), ("wins", wins)):
            if not gg:
                continue
            row = [st.mean([g["day_gap"][str(d)] for g in gg if str(d) in g["day_gap"]] or [0]) for d in days]
            first = next((d for d, v in zip(days, row) if v < 0), None)
            print(f"    {name:7} " + " ".join(f"{v:>+7,.0f}" for v in row) + f"   first<0: day {first}")
    # item net by class
    print(f"  item net (my rev-spend) - (opp rev-spend), mean per game:")
    keys = sorted({it for g in games for it in net_items(g)},
                  key=lambda it: st.mean([net_items(g).get(it, 0) for g in losses + near] or [0]))
    print(f"    {'item':12} {'loss':>10} {'near':>10} {'win':>10} {'loss-win':>10}")
    for it in keys:
        row = {c: (st.mean([net_items(g).get(it, 0) for g in gg]) if gg else 0.0)
               for c, gg in (("loss", losses), ("near", near), ("win", wins))}
        print(f"    {it:12} {row['loss']:>+10,.0f} {row['near']:>+10,.0f} {row['win']:>+10,.0f} "
              f"{row['loss']-row['win']:>+10,.0f}")
    # volume vs price for the worst two items in losses+near
    print(f"  volume vs price for the leading deficit items (losses+near):")
    base = losses + near
    for it in keys[:3]:
        if not base:
            continue
        um = uo = pm = po = 0.0
        for g in base:
            me, op = items_of(g, "me"), items_of(g, "opp")
            m, o = me.get(it, {}), op.get(it, {})
            mu, ou = m.get("units", 0), o.get("units", 0)
            um += mu / len(base); uo += ou / len(base)
            pm += ((m.get("rev", 0) / mu) if mu else 0) / len(base)
            po += ((o.get("rev", 0) / ou) if ou else 0) / len(base)
        p_avg, u_avg = (pm + po) / 2, (um + uo) / 2
        print(f"    {it:12} u_me {um:7.1f} u_opp {uo:7.1f} p_me {pm:6.1f} p_opp {po:6.1f} "
              f"vol {(um-uo)*p_avg:>+8,.0f} price {(pm-po)*u_avg:>+8,.0f} net {(um-uo)*p_avg+(pm-po)*u_avg:>+8,.0f}")
    # layer signature
    sig = {k: st.mean([g["structure"][k] for g in games]) for k in
           ("sell_steps", "multi_sell_steps", "wool_sell_steps")}
    wool = st.mean([items_of(g, "me").get("WOOL", {}).get("units", 0) for g in games])
    straw_units = st.mean([items_of(g, "me").get("STRAWBERRY", {}).get("units", 0) for g in games])
    straw_price = st.mean([items_of(g, "me").get("STRAWBERRY", {}).get("avg", 0) for g in games])
    print(f"  layer signature: SELL steps {sig['sell_steps']:.0f}, multi-SELL {sig['multi_sell_steps']:.0f}, "
          f"WOOL-SELL steps {sig['wool_sell_steps']:.0f}, WOOL units {wool:.0f}; "
          f"STRAWBERRY units {straw_units:.0f} at avg price {straw_price:.1f}")
    return {"n": len(games), "loss": len(losses), "near": len(near), "win": len(wins),
            "margins": mc, "mirror": [same, n],
            "day_row": {name: [round(st.mean([g["day_gap"][str(d)] for g in gg if str(d) in g["day_gap"]] or [0]))
                                for d in days] for name, gg in
                        (("loss", losses), ("near", near), ("win", wins)) if gg},
            "days": days, "item": keys, "signature": sig}


def main():
    import os
    which = os.environ.get("T26_ONLY")
    cfg = [
        ("56422944 comp_both, Task-23 sample", "data/replay-attr-newline.json",
         "data/replays", "data/episodes-56422944-raw-t23.json"),
        ("56422944 comp_both, Task-25 games", "data/replay-attr-newline-t25.json",
         "data/replays-t25", "data/episodes-56422944-raw.json"),
        ("56409633 composite, Task-23 sample", "data/replay-attr-composite.json",
         "data/replays", "data/episodes-56409633-raw-t23.json"),
        ("56409633 composite, Task-25 games", "data/replay-attr-composite-t25.json",
         "data/replays-t25", "data/episodes-56409633-raw.json"),
        ("56447790 comp_straw, CURRENT games (Task-26)", "data/replay-attr-straw-t26.json",
         "data/replays-t26", "data/episodes-56447790-raw.json"),
    ]
    if which:
        cfg = [c for c in cfg if which in c[0]]
    out = {}
    for label, attr, rdir, raw in cfg:
        p = ROOT / attr
        if not p.exists():
            print(f"\n[MISSING] {attr}")
            continue
        games = load_games(p)
        # restrict the mirror detector to the episodes in this attribution file
        eps = {str(g["episode"]) for g in games}
        out[label] = window_report(label, games, rdir, eps, ROOT / raw)
    (ROOT / "data" / ("replay-compare-t26.json" if which else "replay-compare-t25.json")).write_text(json.dumps(out, indent=1, default=str))
    print("\nwrote data/replay-compare-t25.json")


if __name__ == "__main__":
    main()
