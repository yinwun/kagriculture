#!/usr/bin/env python
"""Per-tile farm composition by day, from the replay (no engine needed).

Distinguishes "we planted fewer strawberries" (mix) from "we sold them worse" (timing):
the replay's farms[p].tiles at each day boundary gives every tile's kind/crop/animal.
"""
import collections, glob, json, statistics as st
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
NP = 24
CROPS = ("WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON")
ANIMALS = ("SHEEP", "COW", "GOOSE")

def load_games(ref):
    g = json.loads((ROOT / "data" / f"replay-attr-{'newline' if ref=='56422944' else 'composite'}.json").read_text())
    return next(iter(g.values())) if isinstance(g, dict) else g

def tiles_at(d, seat, day):
    t = 6 * NP + NP * day         # hmm: day*24, use min(day*24,719)
    t = min(day * NP, len(d["steps"]) - 1)
    farms = d["steps"][t][seat]["observation"]["farms"]
    return farms[seat]["tiles"]

def count(tiles):
    c = collections.Counter()
    for row in tiles:
        for cell in row:
            if not isinstance(cell, dict):
                continue
            k = cell.get("kind")
            if k == "PLANT":
                c["CROP_" + str(cell.get("crop"))] += 1
            elif k == "PASTURE":
                a = cell.get("animal")
                if a:
                    c["ANIMAL_" + str(a)] += 1
                else:
                    c["PASTURE_EMPTY"] += 1
            elif k == "COOP":
                a = cell.get("animal")
                c["COOP_" + str(a)] += 1 if a else 0
                if not a:
                    c["COOP_EMPTY"] += 1
            elif k == "WEED":
                c["WEED"] += 1
            elif k == "LOCKED":
                c["LOCKED"] += 1
    return c

def main():
    for ref, lbl in (("56422944", "new line"), ("56409633", "composite")):
        games = [g for g in load_games(ref) if g.get("money_match")]
        reps = {}
        for p in glob.glob(str(ROOT / "data" / "replays" / "episode-*-replay.json")):
            d = json.loads(Path(p).read_text())
            reps[d.get("id")] = d
        cls = {"loss": [g for g in games if g["margin"] < -500],
               "near": [g for g in games if -500 <= g["margin"] < 0],
               "win": [g for g in games if g["margin"] >= 0]}
        keys = ["CROP_STRAWBERRY", "CROP_MELON", "CROP_WHEAT", "CROP_TOMATO", "CROP_CARROT",
                "ANIMAL_SHEEP", "ANIMAL_COW", "ANIMAL_GOOSE", "WEED"]
        print(f"\n=== {lbl} ref {ref}: tiles by class, mean count per day (day 6/12/18/24) ===")
        print(f"  {'class':6} {'n':>3} " + " ".join(f"{k.replace('CROP_','').replace('ANIMAL_','')[:9]:>9}" for k in keys))
        for c, gg in cls.items():
            if not gg:
                continue
            rows = collections.defaultdict(list)
            for g in gg:
                d = reps.get(g["episode"])
                if d is None:
                    continue
                for day in (6, 12, 18, 24):
                    t = min(day * NP, len(d["steps"]) - 1)
                    me = count(d["steps"][t][g["my_seat"]]["observation"]["farms"][g["my_seat"]]["tiles"])
                    op = count(d["steps"][t][1 - g["my_seat"]]["observation"]["farms"][1 - g["my_seat"]]["tiles"])
                    for k in keys:
                        rows[k].append(me.get(k, 0) - op.get(k, 0))
            print(f"  {c:6} {len(gg):>3} " + " ".join(f"{st.mean(rows[k]):>+9.1f}" for k in keys))
if __name__ == "__main__":
    main()
