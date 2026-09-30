"""Joint parameterisation + search over the whole economy policy.

Why: every manual change to the from-scratch economy lost to the champion (5 routes,
~50 configs, ~1,900 paired games, all 0/N).  What was never tried is searching the
knobs *jointly*: the champion's edge is a co-adapted combination (portfolio x price
operation x sell timing), and one-at-a-time changes cannot express that -- each single
change breaks an assumption the others rely on.

This script therefore treats plan_v0 as a *parameterised policy* (25 knobs: portfolio
sizes, hire/route parameters, herd cash policy, sell policy, price operation, endgame)
and runs a simple evolution strategy on top of it, with the fitness being the paired
delta against the champion from scripts/plan_duel_sweep.py -- the only instrument that
has been valid all cycle.

Usage:
  python scripts/joint_search.py --smoke                       # 1 generation, 8 evals
  python scripts/joint_search.py --gens 8 --lam 12 --towns 16  # a real run
"""
import argparse
import json
import math
import multiprocessing as mp
import random
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
CHAMPION = str(ROOT / "data" / "tapeopt" / "rgcs" / "main.py")
BEST_FILE = ROOT / "data" / "joint-best.json"
LOG_FILE = ROOT / "data" / "joint-search.jsonl"

# knob -> (low, high, kind).  Current best manual config is the starting point.
SPACE = {
    "hire_mult":            (1.4, 4.5, "f"),
    "plant_scale":          (0.4, 1.6, "f"),
    "animal_scale":         (0.6, 1.8, "f"),
    "sell_batch":           (2.0, 40.0, "i"),
    "claim_slack":          (0.0, 12.0, "i"),
    "age_div":              (2.0, 16.0, "i"),
    "zone_penalty":         (0.0, 6.0, "i"),
    "strip_penalty":        (0.0, 8.0, "i"),
    "pen_min_dist":         (1.0, 2.0, "i"),
    "herd_reserve":         (0.0, 1500.0, "i"),
    "seed_ahead":           (0.0, 2.0, "i"),
    "price_floor_frac":     (0.0, 0.8, "f"),
    "liquidate_day":        (24.0, 99.0, "i"),
    "sell_hold_cash":       (0.0, 4000.0, "i"),
    "feed_buy_mult":        (1.0, 3.0, "f"),
    "early_geese":          (0.0, 4.0, "i"),
    "place_phase_days":     (0.0, 6.0, "i"),
    "prio_collect":         (1.0, 6.0, "i"),
    "prio_water_window":    (1.0, 6.0, "i"),
    "prio_harvest":         (2.0, 8.0, "i"),
    "prio_plant":           (3.0, 9.0, "i"),
    "feed_days":            (2.0, 6.0, "i"),
    "wheat_keep":           (0.0, 60.0, "i"),
    "fert_keep":            (0.0, 8.0, "i"),
    "place_phase_units_early": (1.0, 5.0, "i"),
}
START = {
    "hire_mult": 3.2, "plant_scale": 1.2, "animal_scale": 1.0, "sell_batch": 20,
    "claim_slack": 8, "age_div": 4, "zone_penalty": 2, "strip_penalty": 4,
    "pen_min_dist": 1, "herd_reserve": 400, "seed_ahead": 1, "price_floor_frac": 0.0,
    "liquidate_day": 99, "sell_hold_cash": 0, "feed_buy_mult": 1.0, "early_geese": 0,
    "place_phase_days": 2, "prio_collect": 2, "prio_water_window": 3, "prio_harvest": 6,
    "prio_plant": 7, "feed_days": 3, "wheat_keep": 8, "fert_keep": 2,
    "place_phase_units_early": 3,
}
FIXED = {"market_mode": "auto", "sell_order": "ratio", "preempt_max_prio": -1,
         "herd_cash_gate": 1, "portfolio": "rank1", "place_phase_hours": 0,
         "place_phase_units": 2}


def clamp(name, v):
    lo, hi, kind = SPACE[name]
    v = max(lo, min(hi, v))
    return int(round(v)) if kind == "i" else float(v)


def to_params(vec):
    p = dict(FIXED)
    for name, v in zip(SPACE, vec):
        p[name] = clamp(name, v)
    return p


def to_vec(params):
    return [float(params.get(n, START[n])) for n in SPACE]


_CACHE = {}


def _eval_job(arg):
    global _CACHE
    idx, vec, seeds, opp = arg
    import plan_v0
    from kaggle_environments import make
    params = to_params(vec)
    # cache the opponent agent per worker: exec'ing the 300 KB champion source on
    # every job was what made an evaluation take minutes instead of ~30 seconds
    if "champ" not in _CACHE:
        ns = {"__name__": "opp_champ"}
        exec(compile(Path(opp).read_text(), opp, "exec"), ns)
        _CACHE["champ"] = ns["agent"]
    champ = _CACHE["champ"]
    out = []
    for seed in seeds:
        for seat in (0, 1):
            pl = plan_v0.PlanV0(params=params)

            def cand(obs, configuration=None, _p=pl):
                return _p.act(obs)

            agents = [cand, champ] if seat == 0 else [champ, cand]
            env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": seed})
            env.run(agents)
            f = env.steps[-1]
            out.append({"seed": seed,
                        "delta": float(f[seat]["reward"] or 0) - float(f[1 - seat]["reward"] or 0),
                        "status": str(f[seat]["status"]),
                        "cand": float(f[seat]["reward"] or 0)})
    return idx, out


def fitness_batch(vecs, seeds, procs, chunks=8):
    """Evaluate a whole generation in ONE pool: startup cost dominates otherwise."""
    groups = [seeds[i::chunks] for i in range(chunks)]
    jobs = [(i, v, g, CHAMPION) for i, v in enumerate(vecs) for g in groups if g]
    with mp.Pool(procs) as pool:
        res = pool.map(_eval_job, jobs)
    per = {}
    for idx, rows in res:
        per.setdefault(idx, []).extend(rows)
    out = []
    for i in range(len(vecs)):
        rows = per.get(i, [])
        by_seed = {}
        for r in rows:
            by_seed.setdefault(r["seed"], []).append(r["delta"])
        d = [statistics.mean(v) for v in by_seed.values()]
        mean = statistics.mean(d) if d else 0.0
        var = statistics.variance(d) if len(d) > 1 else 0.0
        t = mean / (math.sqrt(var / len(d)) if var and d else 1.0)
        out.append((mean, t,
                    statistics.mean(r["cand"] for r in rows) if rows else 0.0,
                    sum(1 for r in rows if r["status"] != "DONE")))
    return out


def fitness(vec, seeds, procs, chunks=4):
    """Single-vector evaluation (used for the incumbent at generation 0)."""
    return fitness_batch([vec], seeds, procs, chunks=chunks)[0]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--gens", type=int, default=4)
    ap.add_argument("--lam", type=int, default=10, help="samples per generation")
    ap.add_argument("--sigma", type=float, default=0.25, help="step as a fraction of range")
    ap.add_argument("--towns", type=int, default=16)
    ap.add_argument("--procs", type=int, default=10)
    ap.add_argument("--start-seed", type=int, default=9000)
    ap.add_argument("--smoke", action="store_true")
    args = ap.parse_args()
    if args.smoke:
        args.gens, args.lam, args.towns = 1, 8, 12

    seeds = list(range(args.start_seed, args.start_seed + args.towns))
    vec = to_vec(json.loads(BEST_FILE.read_text())["params"]) if BEST_FILE.exists() else to_vec(START)
    rng = random.Random(20260918)
    best_fit, best_t, best_w, errs = fitness(vec, seeds, args.procs)
    print(f"generation 0 (incumbent): delta {best_fit:+,.0f} t={best_t:+.2f} wallet {best_w:,.0f} err={errs}",
          flush=True)
    log = {"gen": 0, "delta": best_fit, "t": best_t, "wallet": best_w,
           "params": to_params(vec), "at": time.strftime("%Y-%m-%dT%H:%M:%S")}
    with open(LOG_FILE, "a") as fh:
        fh.write(json.dumps(log) + "\n")

    for gen in range(1, args.gens + 1):
        cands = []
        for _ in range(args.lam):
            v = [clamp(n, x + rng.gauss(0, args.sigma * (SPACE[n][1] - SPACE[n][0])))
                 for n, x in zip(SPACE, vec)]
            cands.append(v)
        results = fitness_batch(cands, seeds, args.procs)
        for i, (v, (m, t, w, e)) in enumerate(zip(cands, results)):
            print(f"  gen {gen} cand {i:2d}: delta {m:+,.0f} t={t:+.2f} wallet {w:,.0f} err={e}",
                  flush=True)
            with open(LOG_FILE, "a") as fh:
                fh.write(json.dumps({"gen": gen, "cand": i, "delta": m, "t": t, "wallet": w,
                                     "params": to_params(v),
                                     "at": time.strftime("%Y-%m-%dT%H:%M:%S")}) + "\n")
            if m > best_fit:
                best_fit, best_t, best_w, vec = m, t, w, v
                BEST_FILE.write_text(json.dumps({"params": to_params(vec), "delta": m, "t": t},
                                                indent=1))
                print(f"    -> new best {m:+,.0f} (t={t:+.2f}) saved to {BEST_FILE.name}",
                      flush=True)
        args.sigma *= 0.8
    print(f"\nfinal best delta {best_fit:+,.0f} t={best_t:+.2f} wallet {best_w:,.0f}")
    print(json.dumps(to_params(vec), indent=1, sort_keys=True))


if __name__ == "__main__":
    main()
