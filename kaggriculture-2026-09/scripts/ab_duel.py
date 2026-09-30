#!/usr/bin/env python
"""Paired A/B duel between two agent main.py files, seat-balanced.

The same seed is the same town, so playing candidate and baseline on the same seed
list gives a paired comparison; playing each seed twice with the seats swapped
cancels the engine's documented seat-0 advantage.  Per seed we report
    delta = mean(cand_wallet - base_wallet over the two seat assignments)
and the t-statistic of those per-seed deltas (the town is the unit of analysis).

Mechanistic counters (commands by verb, idle share, market orders) are collected
from the recorded actions so a wallet change can be explained by what changed.

Usage:
  python scripts/ab_duel.py --cand data/tapeopt/idlefill/main.py \
      --base data/tapeopt/rgcs/main.py --seeds 9000-9199 --out data/night-A-idlefill.json
"""
import argparse
import collections
import json
import multiprocessing as mp
import sys
import time
from pathlib import Path

MOVE = {"NORTH", "SOUTH", "EAST", "WEST"}
_COUNTERS = ("PASS", "WATER", "HARVEST", "PLANT", "FEED", "CARE", "COLLECT_FERTILIZER",
             "FERTILIZE", "PICKUP", "PLACE", "DIG", "DROP", "BUILD_PASTURE",
             "BUILD_COOP")


def _load(path):
    src = Path(path).read_text()
    ns = {"__name__": "duel_mod"}
    exec(compile(src, str(path), "exec"), ns)
    return ns


def _diagnostics(ns):
    """Additive instrumentation hook: read non-zero internal counters if the build exposes them.

    Never raises and never alters the duel: a build without these attributes yields {}."""
    d = {}
    try:
        for k, v in dict(ns["_IMPL"].chassis.diagnostics).items():
            if v:
                d[k] = d.get(k, 0) + int(v)
    except Exception:
        pass
    try:
        r = ns.get("_RACE_REPORT")
        if isinstance(r, dict):
            for k, v in r.items():
                if isinstance(v, (int, float)) and v:
                    d["RACE_" + k] = d.get("RACE_" + k, 0) + int(v)
    except Exception:
        pass
    return d


def _counters(env, seat):
    c = collections.Counter()
    for t in range(len(env.steps)):
        entry = env.steps[t][seat]
        a = entry.get("action") or {}
        for cmd in [a.get("farmer") or []] + list(a.get("hands") or []):
            if isinstance(cmd, list) and cmd:
                v = cmd[0]
                if v in MOVE:
                    c["MOVE"] += 1
                else:
                    c[v] += 1
                    c["CMD"] += 1
        for m in (a.get("market") or []):
            if isinstance(m, list) and m:
                c["MKT_" + m[0]] += 1
    return dict(c)


def _probe(inner, box):
    """Count agent exceptions per seat.

    Needed because a raising agent does NOT show up in `status`: the engine substitutes
    a fallback action, the episode still ends DONE and `err` stays 0 -- a composite
    variant that raised on every step scored exactly its 3,000 starting coins while
    reporting err=0.  Re-raises so behaviour is unchanged.
    """
    def wrap(obs, *a, **k):
        try:
            return inner(obs, *a, **k)
        except BaseException as exc:  # noqa: BLE001
            box["n"] = box.get("n", 0) + 1
            box.setdefault("last", f"{type(exc).__name__}: {exc}"[:160])
            raise
    return wrap


def _job(arg):
    cand_path, base_path, seeds = arg
    from kaggle_environments import make
    cand_ns = _load(cand_path)
    base_ns = _load(base_path)
    cbox, bbox = {}, {}
    cand = _probe(cand_ns["agent"], cbox)
    base = _probe(base_ns["agent"], bbox)
    out = []
    for seed in seeds:
        for cand_seat in (0, 1):
            env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": seed})
            agents = [cand, base] if cand_seat == 0 else [base, cand]
            env.run(agents)
            f = env.steps[-1]
            rec = {"seed": seed, "cand_seat": cand_seat,
                   "cand": f[cand_seat]["reward"] or 0,
                   "base": f[1 - cand_seat]["reward"] or 0,
                   "status": [str(env.steps[-1][i].get("status")) for i in (0, 1)]}
            rec["cm"] = _counters(env, cand_seat)
            rec["bm"] = _counters(env, 1 - cand_seat)
            rec["cdiag"] = _diagnostics(cand_ns)
            rec["bdiag"] = _diagnostics(base_ns)
            rec["cbox"] = dict(cbox)
            rec["bbox"] = dict(bbox)
            out.append(rec)
    return out


def chunks(seq, n):
    step = max(1, -(-len(seq) // max(1, n)))
    return [seq[i:i + step] for i in range(0, len(seq), step)]


def parse_seeds(spec):
    out = []
    for part in spec.split(","):
        if "-" in part:
            a, b = part.split("-")
            out.extend(range(int(a), int(b) + 1))
        else:
            out.append(int(part))
    return out


def stats(diffs):
    n = len(diffs)
    mean = sum(diffs) / n
    var = sum((x - mean) ** 2 for x in diffs) / (n - 1) if n > 1 else 0.0
    se = (var / n) ** 0.5
    return mean, (mean / se if se else 0.0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cand", required=True)
    ap.add_argument("--base", required=True)
    ap.add_argument("--seeds", default="9000-9199")
    ap.add_argument("--procs", type=int, default=10)
    ap.add_argument("--out", default=None)
    ap.add_argument("--label", default=None)
    args = ap.parse_args()

    seeds = parse_seeds(args.seeds)
    jobs = [(args.cand, args.base, ch) for ch in chunks(seeds, args.procs * 2)]
    t0 = time.time()
    with mp.Pool(args.procs) as pool:
        res = pool.map(_job, jobs)
    recs = [r for sub in res for r in sub]
    dt = time.time() - t0
    games = len(recs)
    print(f"[{games} games in {dt:.0f}s = {3600*games/max(1,dt):,.0f} games/hour]", file=sys.stderr)

    per_seed = collections.defaultdict(list)
    for r in recs:
        per_seed[r["seed"]].append(r)
    diffs, cw, bw, errs = [], 0, 0, 0
    cm_tot, bm_tot = collections.Counter(), collections.Counter()
    cdiag_tot, bdiag_tot = collections.Counter(), collections.Counter()
    for seed, rs in sorted(per_seed.items()):
        d = [x["cand"] - x["base"] for x in rs]
        diffs.append(sum(d) / len(d))
        for x in rs:
            cw += x["cand"] > x["base"]
            bw += x["cand"] < x["base"]
            errs += sum(1 for s in x["status"] if s != "DONE")
            cm_tot.update(x["cm"])
            bm_tot.update(x["bm"])
            cdiag_tot.update(x.get("cdiag") or {})
            bdiag_tot.update(x.get("bdiag") or {})
    mean, t = stats(diffs)
    cand_mean = sum(r["cand"] for r in recs) / games
    base_mean = sum(r["base"] for r in recs) / games
    label = args.label or Path(args.cand).parent.name
    print(f"{label:22s} vs {Path(args.base).parent.name:14s} "
          f"delta {mean:+9,.0f}  t={t:+5.2f}  W/L {cw}/{bw}  "
          f"wallet {cand_mean:9,.0f} vs {base_mean:9,.0f}  err={errs}")
    lines = []
    for k in _COUNTERS + ("MOVE", "CMD"):
        c, b = cm_tot.get(k, 0), bm_tot.get(k, 0)
        if c or b:
            lines.append(f"   {k:20s} {c:8d} vs {b:8d}  ({c-b:+d})")
    print("\n".join(lines))
    tot_c = cm_tot.get("CMD", 0) + cm_tot.get("MOVE", 0, )
    tot_b = bm_tot.get("CMD", 0) + bm_tot.get("MOVE", 0)
    if tot_c and tot_b:
        print(f"   idle share           {100*cm_tot.get('PASS',0)/ (tot_c):6.2f}% vs "
              f"{100*bm_tot.get('PASS',0)/ (tot_b):6.2f}%")
    if cdiag_tot or bdiag_tot:
        print(f"   internal counters    cand={dict(cdiag_tot) or '{}'} base={dict(bdiag_tot) or '{}'}")
    exc_c = sum((x.get("cbox") or {}).get("n", 0) for x in recs)
    exc_b = sum((x.get("bbox") or {}).get("n", 0) for x in recs)
    if exc_c or exc_b:
        last_c = next(((x.get("cbox") or {}).get("last") for x in recs
                       if (x.get("cbox") or {}).get("last")), "")
        last_b = next(((x.get("bbox") or {}).get("last") for x in recs
                       if (x.get("bbox") or {}).get("last")), "")
        print(f"   AGENT EXCEPTIONS     cand={exc_c} ({last_c})  base={exc_b} ({last_b})")
    out = {"label": label, "cand": args.cand, "base": args.base, "seeds": [min(seeds), max(seeds)],
           "games": games, "delta": mean, "t": t, "wins": cw, "losses": bw,
           "cand_wallet": cand_mean, "base_wallet": base_mean, "errors": errs,
           "cand_exceptions": exc_c, "base_exceptions": exc_b,
           "cand_mech": dict(cm_tot), "base_mech": dict(bm_tot),
           "cand_diag": dict(cdiag_tot), "base_diag": dict(bdiag_tot),
           "per_seed": [{"seed": s, "delta": d, "n": len(per_seed[s])}
                        for s, d in zip(sorted(per_seed), diffs)]}
    if args.out:
        Path(args.out).write_text(json.dumps(out, indent=1))
        print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
