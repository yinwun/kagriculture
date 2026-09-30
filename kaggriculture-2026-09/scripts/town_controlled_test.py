#!/usr/bin/env python
"""Town-controlled test of opponent sensitivity, using public top-team episodes.

The substitution experiment we want ("re-run rank-1 against a different opponent on
the same seed") needs the agent's *policy*, which replays do not give: a recorded
action stream replayed against a new opponent goes stale within a step.  Kaggle's
own data offers the licensed version of the same experiment instead: the corpus
contains **the same team on the same seed in more than one episode**, against
different opponents.  Same seed => the same town draw, so the world is held fixed
and the rival is the only thing that moved.

If a team's plan is a template that reads the world and its own farm (not the
rival), then:
    within-seed pairs (rival varies, town fixed)  -> nearly identical final farms
    across-seed pairs (town and rival both vary)  -> clearly different farms
If the team conditions on the rival, the first group stops being identical.

Usage:
  python scripts/town_controlled_test.py --dataset data/top10streams
  python scripts/town_controlled_test.py --dataset data/top10streams --team カワシギ
"""
import argparse
import collections
import itertools
import json
import random
from pathlib import Path

import pandas as pd


def parse_board(s):
    """'WH,.,.,...|...|.../NE,NW' -> (tiles tuple of tokens, quads tuple)."""
    body, _, quads = s.partition("/")
    tiles = tuple(t for row in body.split("|") for t in row.split(","))
    return tiles, tuple(quads.split(",")) if quads else ()


def agreement(a, b):
    """Fraction of matching tiles over the union length (boards are same size)."""
    n = max(len(a), len(b))
    return sum(1 for x, y in zip(a, b) if x == y) / n if n else 0.0


def pairs_within(group):
    return list(itertools.combinations(group, 2))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", default="data/top10streams")
    ap.add_argument("--team", default=None)
    ap.add_argument("--signatures", default="data/town_signatures.json")
    ap.add_argument("--max-across", type=int, default=4000)
    ap.add_argument("--perms", type=int, default=200)
    args = ap.parse_args()

    ep = pd.read_csv(Path(args.dataset) / "episodes.csv")
    bd = pd.read_csv(Path(args.dataset) / "boards.csv")
    df = ep.merge(bd[["submission", "episode_id", "board"]], on=["submission", "episode_id"])
    df = df[df.turns == 720]
    if args.team:
        df = df[df.team == args.team]

    sig_path = Path(args.signatures)
    sigs = json.loads(sig_path.read_text()) if sig_path.exists() else {}

    def town_of(seed):
        s = sigs.get(str(int(seed)))
        return tuple(tuple(x) for x in s) if s else None

    rng = random.Random(0)
    print(f"{'team':32s} {'eps':>4s} {'towns':>6s} | {'same-town pairs':>15s} {'ident':>6s} {'agree':>6s}"
          f" | {'diff-town pairs':>16s} {'ident':>6s} {'agree':>6s} | {'p':>6s}")
    rows = []
    for team, g in df.groupby("team"):
        g = g.drop_duplicates(subset=["episode_id"])
        recs = {r.episode_id: parse_board(r.board)[0] for r in g.itertuples()}
        opp = dict(zip(g.episode_id, g.opponent))
        town = {r.episode_id: town_of(r.seed) for r in g.itertuples()}

        by_town = collections.defaultdict(list)
        for i, t in town.items():
            if t is not None:
                by_town[t].append(i)
        within = [(a, b) for ids in by_town.values() for a, b in pairs_within(ids)
                  if opp[a] != opp[b]]
        ids = list(recs)
        across = []
        if len(ids) > 1:
            for _ in range(min(args.max_across, len(ids) * 4)):
                a, b = rng.sample(ids, 2)
                if town[a] is not None and town[b] is not None and town[a] != town[b]:
                    across.append((a, b))

        def stats(pairs):
            if not pairs:
                return None
            ident = sum(1 for a, b in pairs if recs[a] == recs[b]) / len(pairs)
            agree = sum(agreement(recs[a], recs[b]) for a, b in pairs) / len(pairs)
            return ident, agree, len(pairs)

        w, ac = stats(within), stats(across)
        # permutation: shuffle town labels within the team, recompute the gap
        gap = (w[1] - ac[1]) if (w and ac) else None
        pval = None
        if w and ac and args.perms:
            all_ids = [i for i in ids if town[i] is not None]
            all_pairs = [(a, b) for a in all_ids for b in all_ids if a < b][:20000]
            obs = w[1] - ac[1]
            null = []
            labels = [town[i] for i in all_ids]
            for _ in range(args.perms):
                rng.shuffle(labels)
                lab = dict(zip(all_ids, labels))
                same = [agreement(recs[a], recs[b]) for a, b in all_pairs if lab[a] == lab[b]]
                diff = [agreement(recs[a], recs[b]) for a, b in all_pairs if lab[a] != lab[b]]
                if same and diff:
                    null.append(sum(same) / len(same) - sum(diff) / len(diff))
            pval = (sum(1 for x in null if x >= obs) + 1) / (len(null) + 1) if null else None

        fmt = lambda s: (f"{s[0]:6.3f} {s[1]:6.3f}" if s else f"{'-':>6s} {'-':>6s}")
        print(f"{team[:32]:32s} {len(recs):4d} {len(by_town):6d} | {(w[2] if w else 0):15d} {fmt(w)}"
              f" | {(ac[2] if ac else 0):16d} {fmt(ac)} | "
              f"{(f'{pval:.3f}' if pval is not None else '-'):>6s}")
        rows.append({"team": team, "eps": len(recs), "towns": len(by_town),
                     "within": w, "across": ac, "gap": gap, "perm_p": pval,
                     "mean_bank": float(g.bank.mean())})

    print("\nreading: same-town pairs hold the visible world fixed (identical shop draw)")
    print("and vary only the rival.  High 'agree' there + low p => the plan ignores the rival.")
    Path("data/town_controlled.json").write_text(json.dumps(rows, indent=1, default=str))
    print("wrote data/town_controlled.json")


if __name__ == "__main__":
    main()
