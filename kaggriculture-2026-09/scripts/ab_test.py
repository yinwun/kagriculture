#!/usr/bin/env python
"""Local A/B harness for kaggriculture agents.

Two modes:
  paired  - same seed, same opponent: isolate the quality of agent A vs agent B
            (run [A, opp] and [B, opp] with one seed, compare their banks)
  h2h     - put A and B in the same game and see who wins

Usage:
  python scripts/ab_test.py paired A/main.py B/main.py --opponent starter --seeds 20
  python scripts/ab_test.py h2h A/main.py B/main.py --seeds 20
"""
import argparse
import os
import statistics
import time

from kaggle_environments import make


def resolve(p):
    return p if p in ("starter", "random", "pass") else os.path.abspath(p)


def run_one(a, b, seed):
    env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": seed})
    env.run([a, b])
    f = env.steps[-1]
    return f[0]["reward"], f[1]["reward"], f[0]["status"], f[1]["status"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["paired", "h2h"])
    ap.add_argument("agent_a")
    ap.add_argument("agent_b")
    ap.add_argument("--opponent", default="starter", help="paired mode opponent")
    ap.add_argument("--seeds", type=int, default=20)
    ap.add_argument("--start", type=int, default=1000)
    args = ap.parse_args()

    A, B = resolve(args.agent_a), resolve(args.agent_b)
    t0 = time.time()

    if args.mode == "h2h":
        aw = bw = 0
        diffs = []
        print(f"h2h: A={os.path.basename(os.path.dirname(A))}  B={os.path.basename(os.path.dirname(B))}")
        for i in range(args.seeds):
            seed = args.start + i
            a, b, sa, sb = run_one(A, B, seed)
            aw += a > b
            bw += b > a
            diffs.append(a - b)
            print(f"  seed {seed}: A={a:>9,.0f} B={b:>9,.0f} {'A' if a > b else 'B' if b > a else 'tie'}"
                  f"   (status {sa}/{sb})")
        print(f"\nA wins {aw}/{args.seeds}, B wins {bw}/{args.seeds}")
        print(f"mean bank diff (A-B): {statistics.mean(diffs):+,.0f}")
    else:
        pa, pb = [], []
        wins_a = wins_b = 0
        print(f"paired vs {args.opponent}: A={A}  B={B}")
        for i in range(args.seeds):
            seed = args.start + i
            a1, o1, _, _ = run_one(A, args.opponent, seed)
            b1, o2, _, _ = run_one(B, args.opponent, seed)
            pa.append(a1)
            pb.append(b1)
            wins_a += a1 > o1
            wins_b += b1 > o2
            print(f"  seed {seed}: A={a1:>9,.0f} B={b1:>9,.0f}  diff={a1 - b1:>+9,.0f}  "
                  f"(opp={o1:,.0f}/{o2:,.0f})")
        diffs = [x - y for x, y in zip(pa, pb)]
        better = sum(1 for d in diffs if d > 0)
        print(f"\nmean A={statistics.mean(pa):,.0f}  mean B={statistics.mean(pb):,.0f}")
        print(f"mean diff (A-B) = {statistics.mean(diffs):+,.0f}   median = {statistics.median(diffs):+,.0f}")
        print(f"A better on {better}/{args.seeds} seeds; win vs {args.opponent}: A {wins_a}/{args.seeds}, B {wins_b}/{args.seeds}")
        if len(diffs) > 1:
            sd = statistics.stdev(diffs)
            se = sd / len(diffs) ** 0.5
            print(f"stdev {sd:,.0f}, stderr {se:,.0f}  -> t ≈ {statistics.mean(diffs) / se:.2f}")

    print(f"elapsed {time.time() - t0:.1f}s")


if __name__ == "__main__":
    main()
