#!/usr/bin/env python
"""Town signature per seed: the shop draw an agent can see, computed offline.

The town's unlocked shops are a deterministic function of the episode seed
(every 3 days one shop is appended from an rng keyed on the seed), so two episodes
with the same *town signature* present the agent with the same visible world even
though their seeds, rivals and weeds differ.  That makes a town-controlled test of
opponent sensitivity possible on the public top-team corpus.

Usage:
  python scripts/town_signature.py --episodes data/top10streams/episodes.csv \
      --out data/town_signatures.json --jobs 9
"""
import argparse
import json
import multiprocessing as mp
from pathlib import Path

STEPS = 25 * 24  # through the day-24 unlock


def _pass(obs):
    return {"farmer": ["PASS"], "hands": [], "market": []}


def signature(seed):
    from kaggle_environments import make
    env = make("kaggriculture", configuration={"episodeSteps": STEPS, "seed": None}, debug=False)
    env.info["seed"] = int(seed)
    env.run([_pass, _pass])
    seq = []
    prev = None
    for t in range(len(env.steps)):
        o = env.steps[t][0].get("observation")
        if not o:
            continue
        cur = tuple(o["town"]["unlocked_shops"])
        if cur != prev:
            seq.append(list(cur))
            prev = cur
    return int(seed), seq


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--episodes", default="data/top10streams/episodes.csv")
    ap.add_argument("--out", default="data/town_signatures.json")
    ap.add_argument("--jobs", type=int, default=9)
    args = ap.parse_args()

    import pandas as pd
    df = pd.read_csv(args.episodes)
    seeds = sorted({int(s) for s in df.seed.dropna().unique()})
    out_path = Path(args.out)
    cache = json.loads(out_path.read_text()) if out_path.exists() else {}
    todo = [s for s in seeds if str(s) not in cache]
    print(f"{len(seeds)} seeds, {len(todo)} to compute", flush=True)
    if todo:
        with mp.Pool(args.jobs) as pool:
            for i, (seed, seq) in enumerate(pool.imap_unordered(signature, todo, chunksize=4)):
                cache[str(seed)] = seq
                if (i + 1) % 100 == 0:
                    print(f"  {i + 1}/{len(todo)}", flush=True)
                    out_path.write_text(json.dumps(cache))
    out_path.write_text(json.dumps(cache))
    counts = {}
    for s, seq in cache.items():
        counts[len(seq)] = counts.get(len(seq), 0) + 1
    print(f"wrote {out_path} with {len(cache)} signatures; unlock-count histogram {counts}")


if __name__ == "__main__":
    main()
