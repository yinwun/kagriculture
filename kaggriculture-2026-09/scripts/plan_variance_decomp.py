#!/usr/bin/env python
"""How much of a top agent's plan is decided by the town, and how much by the rival?

The substitution experiment cannot be run on replays alone (a recorded stream goes
stale the moment the world moves), so we run the licensed version on the public
top-team corpus: hold the *visible world* fixed by grouping episodes into town
classes (the shop draw through the day-3/day-6 unlock window, recomputed per seed
by scripts/town_signature.py) and see

  1. how much of the final farm's variance lives BETWEEN town classes
     (world-driven) versus WITHIN them (rival / path driven), with a permutation
     p-value for the between-class share, and
  2. whether, inside a town class, the plan still tracks the rival (opponent bank).

Usage:
  python scripts/plan_variance_decomp.py --dataset data/top10streams --team カワシギ
  python scripts/plan_variance_decomp.py --dataset data/top10streams --through 2
"""
import argparse
import collections
import json
import random
from pathlib import Path

import pandas as pd

TOKENS = ("WH", "ST", "PACO", "PASH", "PAGO", "PA", ".", "#")


def board_vector(s):
    body, _, quads = s.partition("/")
    tiles = [t for row in body.split("|") for t in row.split(",")]
    v = collections.Counter(tiles)
    out = {f"n_{t}": v.get(t, 0) for t in ("WH", "ST", "PACO", "PASH", "PAGO", ".")}
    out["n_quad"] = len([q for q in quads.split(",") if q])
    return out


def spearman(a, b):
    pairs = [(x, y) for x, y in zip(a, b) if x is not None and y is not None]
    n = len(pairs)
    if n < 6:
        return None
    ra = _rank([x for x, _ in pairs])
    rb = _rank([y for _, y in pairs])
    ma, mb = sum(ra) / n, sum(rb) / n
    num = sum((x - ma) * (y - mb) for x, y in zip(ra, rb))
    da = sum((x - ma) ** 2 for x in ra) ** 0.5
    db = sum((y - mb) ** 2 for y in rb) ** 0.5
    return num / (da * db) if da and db else None


def _rank(xs):
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


def between_share(values, labels):
    """Fraction of total variance that is between-group (eta squared)."""
    n = len(values)
    if n < 2:
        return 0.0
    m = sum(values) / n
    tot = sum((v - m) ** 2 for v in values)
    if tot == 0:
        return 0.0
    groups = collections.defaultdict(list)
    for v, l in zip(values, labels):
        groups[l].append(v)
    betw = sum(len(g) * (sum(g) / len(g) - m) ** 2 for g in groups.values())
    return betw / tot


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", default="data/top10streams")
    ap.add_argument("--signatures", default="data/town_signatures.json")
    ap.add_argument("--through", type=int, default=2,
                    help="number of shop unlocks that define the town class (2 = through day 6)")
    ap.add_argument("--perms", type=int, default=300)
    ap.add_argument("--team", default=None)
    args = ap.parse_args()

    ep = pd.read_csv(Path(args.dataset) / "episodes.csv")
    bd = pd.read_csv(Path(args.dataset) / "boards.csv")
    df = ep.merge(bd[["submission", "episode_id", "board"]], on=["submission", "episode_id"])
    df = df[df.turns == 720]
    sigs = json.loads(Path(args.signatures).read_text())

    def town_class(seed):
        s = sigs.get(str(int(seed)))
        if not s:
            return None
        seq = s[min(args.through, len(s)) - 1] if args.through > 0 else []
        return tuple(sorted(seq))

    df["tclass"] = [town_class(s) for s in df.seed]
    df = df[df.tclass.notna()]

    teams = [args.team] if args.team else sorted(df.team.unique())
    rng = random.Random(0)
    descs = [f"n_{t}" for t in ("WH", "ST", "PACO", "PASH", "PAGO")] + ["n_quad"]

    print(f"town class = shop draw through unlock #{args.through}   "
          f"(episodes: {len(df)}, classes: {df.tclass.nunique()})")
    print(f"{'team':30s} {'eps':>4s} {'cls':>4s} | " +
          "  ".join(f"{d[2:]:>11s}" for d in descs) + "   | rival rho (n_pairs)")
    rows = []
    for team in teams:
        g = df[df.team == team].drop_duplicates(subset=["episode_id"])
        if len(g) < 20:
            continue
        vecs = [board_vector(b) for b in g.board]
        labels = list(g.tclass)
        opp = list(g.opponent_bank)
        shares = []
        for d in descs:
            vals = [v[d] for v in vecs]
            obs = between_share(vals, labels)
            null = []
            for _ in range(args.perms):
                sh = labels[:]
                rng.shuffle(sh)
                null.append(between_share(vals, sh))
            p = (sum(1 for x in null if x >= obs) + 1) / (len(null) + 1)
            shares.append((d, obs, p))
        line = "  ".join(f"{obs:6.2f}{'*' if p < 0.05 else ' '}{'':4s}" for _, obs, p in shares)
        # within-class rival tracking: residualise both by class mean, then correlate
        rhos = []
        for d in descs:
            vals = [v[d] for v in vecs]
            by = collections.defaultdict(list)
            for v, l in zip(vals, labels):
                by[l].append(v)
            mean = {l: sum(vs) / len(vs) for l, vs in by.items()}
            res = [v - mean[l] for v, l in zip(vals, labels)]
            r = spearman(res, opp)
            if r is not None:
                rhos.append((d, r, len(vals)))
        best = max(rhos, key=lambda t: abs(t[1]), default=None)
        print(f"{team[:30]:30s} {len(g):4d} {len(set(labels)):4d} | {line} | "
              f"{best[0][2:] if best else '-':>8s} {best[1]:+.2f}" if best else "")
        rows.append({"team": team, "eps": len(g), "classes": len(set(labels)),
                     "between": {d: {"share": o, "p": p} for d, o, p in shares},
                     "rival_rho_best": best})
    print("\ncolumns = share of that descriptor's variance explained by the TOWN CLASS")
    print("(* = permutation p < 0.05).  'rival rho' = within-class correlation of the")
    print("most rival-sensitive descriptor with the opponent's final bank (world held fixed).")
    Path("data/plan_variance_decomp.json").write_text(json.dumps(rows, indent=1, default=str))
    print("wrote data/plan_variance_decomp.json")


if __name__ == "__main__":
    main()
