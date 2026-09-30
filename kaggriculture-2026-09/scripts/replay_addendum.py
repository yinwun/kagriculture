#!/usr/bin/env python
"""Task-23 addendum: are the deficit items LOSS-SPECIFIC (vs the same in wins), do
losses cluster on the day-6 shop tuple, and is the farm side different?

Reads data/replay-attr-*.json (instrumented attribution) + data/replays/*.json (for the
day-6 shop tuple, which needs no engine) and the episode manifests for opponent data.
"""
import collections
import glob
import json
import statistics as st
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NP = 24
TRAIN = ("PLANT", "WATER", "HARVEST", "FEED", "CARE", "COLLECT_FERTILIZER", "PLACE", "PICKUP", "DROP")


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


def verbs(g):
    c = collections.Counter()
    for d, v in (g.get("verbs_by_day") or {}).items():
        for k, n in v.items():
            c[k] += n
    return c


SHOPMAP = None


def build_shopmap():
    """Episode UUID -> day-6 shop tuple per seat.

    Gotcha: a replay's top-level `id` is a UUID string; the numeric episode id lives in
    `info.EpisodeId`.  Keying the shop lookup on the replay `id` silently returned None."""
    m = {}
    for p in glob.glob(str(ROOT / "data" / "replays" / "episode-*-replay.json")):
        try:
            d = json.loads(Path(p).read_text())
            seats = {}
            for s in (0, 1):
                seats[s] = tuple(sorted(d["steps"][6 * NP][s]["observation"]["town"]["unlocked_shops"]))
            m[d.get("id")] = seats
        except Exception:
            continue
    return m


def shops_for(eid, seat):
    global SHOPMAP
    if SHOPMAP is None:
        SHOPMAP = build_shopmap()
    seats = SHOPMAP.get(eid)
    return None if seats is None else seats.get(seat)


def main():
    files = {"56422944": "data/replay-attr-newline.json", "56409633": "data/replay-attr-composite.json"}
    summary = {}
    for ref, f in files.items():
        p = ROOT / f
        if not p.exists():
            continue
        games = json.loads(p.read_text())
        if isinstance(games, dict):
            games = next(iter(games.values()))
        games = [g for g in games if g.get("money_match")]
        classes = {"loss": [g for g in games if g["margin"] < -500],
                   "near": [g for g in games if -500 <= g["margin"] < 0],
                   "win": [g for g in games if g["margin"] >= 0]}
        print(f"\n{'='*100}\nref {ref}: {len(games)} games "
              f"(loss {len(classes['loss'])}, near {len(classes['near'])}, win {len(classes['win'])})")
        # ---- item net by outcome class
        allitems = sorted({it for g in games for it in net_items(g)},
                          key=lambda it: st.mean([net_items(g).get(it, 0) for g in classes["loss"] + classes["near"]] or [0]))
        print(f"  {'item':12} " + " ".join(f"{c:>12}" for c in ("loss", "near", "win"))
              + "   loss-vs-win")
        tab = {}
        for it in allitems:
            row = {}
            for c, gg in classes.items():
                vals = [net_items(g).get(it, 0) for g in gg]
                row[c] = st.mean(vals) if vals else 0.0
            tab[it] = row
            print(f"  {it:12} {row['loss']:>+12,.0f} {row['near']:>+12,.0f} {row['win']:>+12,.0f} "
                  f"{row['loss']-row['win']:>+13,.0f}")
        # ---- worker verbs by class (farm-side / herd-branch proxy)
        print(f"\n  farm-side verbs per game (mean): "
              + " ".join(f"{v:>9}" for v in TRAIN) + f" {'PASS':>9}")
        vtab = {}
        for c, gg in classes.items():
            cc = collections.Counter()
            for g in gg:
                cc.update(verbs(g))
            vtab[c] = {v: (cc.get(v, 0) / len(gg) if gg else 0) for v in TRAIN}
            vtab[c]["PASS"] = cc.get("PASS", 0) / len(gg) if gg else 0
            print(f"  {c:12} " + " ".join(f"{vtab[c][v]:>9.0f}" for v in TRAIN) + f" {vtab[c]['PASS']:>9.0f}")
        # ---- day-6 shop tuple by class
        print("\n  day-6 shop tuple distribution (town tuple; RNG is shared with play, so endogenous):")
        stab = {}
        for c, gg in classes.items():
            cnt = collections.Counter()
            for g in gg:
                s = shops_for(g["episode"], g.get("my_seat", 0))
                cnt[s] += 1
            stab[c] = {str(k): v for k, v in cnt.items()}
            top = ", ".join(f"{k}x{v}" for k, v in cnt.most_common(3))
            print(f"    {c:6} n={len(gg):3}: {top}")
        # ---- early vs late gap split
        print("\n  gap at day 9 / day 13 / day 19 / day 29 (mean, from day_worth):")
        for c, gg in classes.items():
            if not gg:
                continue
            row = []
            for d in (9, 13, 19, 29):
                vals = [g["day_gap"][str(d)] for g in gg if str(d) in g["day_gap"]]
                row.append(st.mean(vals) if vals else 0)
            print(f"    {c:6} " + " ".join(f"{v:>+9,.0f}" for v in row))
        summary[ref] = {"n": {c: len(gg) for c, gg in classes.items()}, "items": tab,
                        "verbs": vtab, "shops": stab}
    (ROOT / "data" / "replay-addendum.json").write_text(json.dumps(summary, indent=1, default=str))
    print("\nwrote data/replay-addendum.json")


if __name__ == "__main__":
    main()
