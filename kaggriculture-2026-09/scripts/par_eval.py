#!/usr/bin/env python
"""Parallel paired evaluation harness for the kaggriculture agent family.

One game of two tape agents takes ~2.6 s, and the box has 10 cores, so ~13,800
games/hour are available.  This harness turns that into a controlled experiment:
the SAME seed is the SAME town, so evaluating a candidate against a fixed
opponent on a fixed seed list gives a paired comparison (mean of per-seed
differences, which cancels town luck, unlike the mirror-battle noise).

Candidates are built by patching the production source in memory:
  * ``--settings`` merges a dict onto the stock ``_SETTINGS`` (the controller's
    feature switches),
  * ``--route`` replaces the source ``_router`` with a constant.
Agents are built once per worker and reused across games (the chassis resets its
per-player state when a new game starts at step 0).

Usage:
  python scripts/par_eval.py calibrate --seeds 700-703
  python scripts/par_eval.py sweep-settings --seeds 700-709 --out data/settings_sweep.json
  python scripts/par_eval.py sweep-routes --seeds 700-739 --out data/route_bandit.json
"""
import argparse
import json
import multiprocessing as mp
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
V42 = (ROOT / "data" / "league" /
       "ahmedberatozer_kaggriculture-v42-production-that-fits-the-marke" / "main.py")

_SRC = None
_CACHE = {}


def _read_src():
    global _SRC
    if _SRC is None:
        _SRC = V42.read_text()
    return _SRC


def _patch_settings(src, patch):
    m = re.search(r"_SETTINGS=\{([^}]*)\}", src)
    if not m:
        raise SystemExit("no _SETTINGS found")
    stock = dict(re.findall(r"'([a-z_]+)':\s*(True|False)", m.group(1)))
    stock = {k: (v == "True") for k, v in stock.items()}
    stock.update(patch)
    return src[:m.start()] + "_SETTINGS=" + repr(stock) + src[m.end():], stock


def _patch_route(src, route):
    pat = re.compile(r"def _router\(observation,step,state\):.*?(?=\n_R42_OPENING)", re.S)
    if not pat.search(src):
        raise SystemExit("no _router found")
    new = ("def _router(observation, step, state):\n"
           "    if step >= 648 and not state.get('day27'):\n"
           "        state['route'] = 2\n"
           "        state['day27'] = True\n"
           "        return 2\n"
           f"    return state.get('route') or {route}\n")
    return pat.sub(new + "\n", src, count=1)


_INSTANCE = [0]


def _load_path(path, patch=None, route=None):
    """Build an agent from an arbitrary main.py (opponent pool)."""
    key = (str(path), json.dumps(patch or {}, sort_keys=True), route)
    if key in _CACHE:
        return _CACHE[key]
    src = Path(path).read_text()
    if patch:
        src, _ = _patch_settings(src, patch)
    if route is not None:
        src = _patch_route(src, route)
    ns = {"__name__": "opp_mod"}
    exec(compile(src, f"<opp{key}>", "exec"), ns)
    _CACHE[key] = ns["agent"]
    return _CACHE[key]


def build_agent(settings_patch=None, route=None, fresh=False):
    if fresh:
        _INSTANCE[0] += 1
    key = (json.dumps(settings_patch or {}, sort_keys=True), route,
           _INSTANCE[0] if fresh else 0)
    if key in _CACHE:
        return _CACHE[key]
    src = _read_src()
    if settings_patch:
        src, _ = _patch_settings(src, settings_patch)
    if route is not None:
        src = _patch_route(src, route)
    ns = {"__name__": "agent_mod"}
    exec(compile(src, f"<agent{key}>", "exec"), ns)
    agent = ns["agent"]
    _CACHE[key] = agent
    return agent


_OPP = {}


def _run_series(arg):
    """Worker: play one candidate over a list of seeds against a fixed opponent."""
    from kaggle_environments import make
    cand_id, cand_patch, cand_route, seeds = arg[:4]
    opp_path = arg[4] if len(arg) > 4 else None
    opp_patch = arg[5] if len(arg) > 5 else None
    cand = build_agent(cand_patch, cand_route)
    okey = (str(opp_path), json.dumps(opp_patch or {}, sort_keys=True))
    if okey not in _OPP:
        _OPP[okey] = (build_agent(None, None, fresh=True) if not opp_path
                      else _load_path(opp_path, opp_patch))
    opp = _OPP[okey]
    out = []
    for seed in seeds:
        env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": seed})
        env.run([cand, opp])
        f = env.steps[-1]
        out.append({"seed": seed, "mine": f[0]["reward"] or 0, "theirs": f[1]["reward"] or 0,
                    "shops": list((env.steps[6 * 24][0]["observation"].get("town") or {})
                                  .get("unlocked_shops") or [])})
    return cand_id, out


def chunks(seq, n):
    n = max(1, n)
    step = max(1, -(-len(seq) // n))
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


def run_jobs(jobs, procs):
    t0 = time.time()
    with mp.Pool(procs) as pool:
        results = pool.map(_run_series, jobs)
    dt = time.time() - t0
    games = sum(len(r[1]) for r in results)
    print(f"[{games} games in {dt:.0f}s = {3600*games/max(1,dt):,.0f} games/hour]",
          file=sys.stderr, flush=True)
    return dict(results)


def report(base, cand, label):
    """Paired difference of our wallet against the stock agent, per seed."""
    d = [c["mine"] - c["theirs"] for c in cand]
    b = [c["mine"] - c["theirs"] for c in base]
    n = len(d)
    diffs = [d[i] - b[i] for i in range(min(n, len(b)))]
    mean = sum(diffs) / max(1, len(diffs))
    var = sum((x - mean) ** 2 for x in diffs) / max(1, len(diffs) - 1)
    se = (var / max(1, len(diffs))) ** 0.5
    t = mean / se if se else 0.0
    wins = sum(1 for x in diffs if x > 0)
    l = sum(1 for x in diffs if x < 0)
    print(f"  {label:52} delta {mean:+9,.0f}  t={t:+5.2f}  W/L {wins}/{l}  "
          f"mine {sum(c['mine'] for c in cand)/n:9,.0f}")
    return {"label": label, "delta": mean, "t": t, "wins": wins, "losses": l}


SWITCHES = ["hand_align", "weed_repair", "sell_lead", "budget_guard", "room_guard",
            "clamp_sells", "dead_stock", "terminal_liquidation", "front_run"]


def settings_candidates():
    """Single toggles + all-on/all-off + pairwise among the currently-off ones."""
    cands = [("stock", {})]
    for s in SWITCHES:
        cands.append((f"{s}=ON", {s: True}))
        cands.append((f"{s}=OFF", {s: False}))
    cands.append(("ALL_ON", {s: True for s in SWITCHES}))
    cands.append(("ALL_OFF", {s: False for s in SWITCHES}))
    off = ["budget_guard", "room_guard", "clamp_sells", "dead_stock",
           "terminal_liquidation", "front_run"]
    for i in range(len(off)):
        for j in range(i + 1, len(off)):
            cands.append((f"{off[i]}+{off[j]}", {off[i]: True, off[j]: True}))
    return cands


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["calibrate", "sweep-settings", "sweep-routes", "eval", "pool"])
    ap.add_argument("--opponents", default="", help="comma list of main.py paths for pool mode")
    ap.add_argument("--seeds", default="700-703")
    ap.add_argument("--routes", default="all")
    ap.add_argument("--settings", default=None, help="JSON dict patched onto stock")
    ap.add_argument("--out", default=None)
    ap.add_argument("--procs", type=int, default=10)
    ap.add_argument("--chunk", type=int, default=1, help="seeds per job")
    args = ap.parse_args()
    seeds = parse_seeds(args.seeds)

    if args.mode == "calibrate":
        jobs = [(f"stock|{i}", None, None, ch) for i, ch in enumerate(chunks(seeds, args.procs))]
        res = run_jobs(jobs, args.procs)
        base = sorted([r for rows in res.values() for r in rows], key=lambda r: r["seed"])
        for c in base:
            print(f"  seed {c['seed']}: stock {c['mine']:9,.0f} vs stock {c['theirs']:9,.0f} "
                  f"delta {c['mine']-c['theirs']:+9,.0f}")

    elif args.mode == "sweep-settings":
        if args.settings and Path(args.settings).exists():
            spec = json.loads(Path(args.settings).read_text())
            cands = [(c["label"], c.get("patch", {})) for c in spec]
        elif args.settings:
            cands = [("custom", json.loads(args.settings))]
        else:
            cands = settings_candidates()
        # load balance: aim for a few jobs per worker, each running many games so
        # the ~7 s per-process import of kaggle_environments is amortised
        per_cand = max(1, (args.procs * 3) // max(1, len(cands)))
        jobs = []
        for name, patch in cands:
            for i, ch in enumerate(chunks(seeds, per_cand)):
                jobs.append((f"{name}|{i}", patch, None, ch))
        res = run_jobs(jobs, args.procs)
        merged = {}
        for key, rows in res.items():
            merged.setdefault(key.rsplit("|", 1)[0], []).extend(rows)
        base = merged.get("stock")
        if base is None:
            print("no 'stock' candidate in the run; add one to compare")
            return
        rows = []
        print(f"paired vs stock on {len(seeds)} towns "
              f"(stock mean ours {sum(c['mine'] for c in base)/len(base):,.0f}):")
        for name in [n for n, _ in cands] or sorted(merged):
            if name not in merged or name == "stock":
                continue
            rows.append(report(base, sorted(merged[name], key=lambda r: r["seed"]), name))
        if args.out:
            (ROOT / args.out).write_text(json.dumps(
                {"seeds": seeds, "rows": rows,
                 "games": {k: v for k, v in merged.items()}}, indent=1))
            print(f"wrote {args.out}")

    elif args.mode == "sweep-routes":
        if args.routes == "all":
            import base64, zlib
            b = re.search(r"b85decode\('([^']+)'\)", _read_src()).group(1)
            routes = sorted(int(k) for k in
                            json.loads(zlib.decompress(base64.b85decode(b)))["routes"])
        else:
            routes = [int(r) for r in args.routes.split(",")]
        per_route = max(1, (args.procs * 3) // max(1, len(routes)))
        jobs = [(f"{r}|{i}", None, r, ch)
                for r in routes for i, ch in enumerate(chunks(seeds, per_route))]
        res = run_jobs(jobs, args.procs)
        merged = {}
        for key, rows in res.items():
            merged.setdefault(key.rsplit("|", 1)[0], []).extend(rows)
        if args.out:
            (ROOT / args.out).write_text(json.dumps(merged, indent=1))
            print(f"wrote {args.out} ({len(merged)} routes)")

    elif args.mode == "pool":
        # decisive test: the candidate must beat stock on the SAME towns against a
        # POOL of opponents, not only against our own clone
        cand_patch = json.loads(args.settings) if args.settings else {}
        opps = [o for o in args.opponents.split(",") if o.strip()]
        if not opps:
            raise SystemExit("--opponents required")
        per = max(3, (args.procs * 2) // max(1, 2 * len(opps)))
        jobs = []
        for opp in opps:
            for name, patch in (("cand", cand_patch), ("stock", {})):
                for i, ch in enumerate(chunks(seeds, per)):
                    tag = Path(opp).parent.name[-18:]
                    jobs.append((f"{tag}|{name}|{i}", patch, None, ch, opp))
        res = run_jobs(jobs, args.procs)
        by = {}
        for key, rows in res.items():
            opp, name, _i = key.split("|")
            by.setdefault(opp, {}).setdefault(name, []).extend(rows)
        print(f"candidate = {json.dumps(cand_patch)}")
        print(f"{'opponent':20}{'cand mean':>12}{'stock mean':>12}{'delta':>10}{'t':>8}{'W/L':>10}")
        tot = []
        for opp, arms in sorted(by.items()):
            c = sorted(arms.get("cand", []), key=lambda r: r["seed"])
            b = sorted(arms.get("stock", []), key=lambda r: r["seed"])
            if not c or not b:
                continue
            n = min(len(c), len(b))
            diffs = [c[i]["mine"] - b[i]["mine"] for i in range(n)]
            mean = sum(diffs) / n
            var = sum((x - mean) ** 2 for x in diffs) / max(1, n - 1)
            se = (var / n) ** 0.5
            t = mean / se if se else 0.0
            w = sum(1 for x in diffs if x > 0)
            l = sum(1 for x in diffs if x < 0)
            cm = sum(r["mine"] for r in c[:n]) / n
            bm = sum(r["mine"] for r in b[:n]) / n
            print(f"{opp:20}{cm:12,.0f}{bm:12,.0f}{mean:+10,.0f}{t:+8.2f}{f'{w}/{l}':>10}")
            tot.extend(diffs)
        if tot:
            mean = sum(tot) / len(tot)
            var = sum((x - mean) ** 2 for x in tot) / max(1, len(tot) - 1)
            se = (var / len(tot)) ** 0.5
            w = sum(1 for x in tot if x > 0)
            l = sum(1 for x in tot if x < 0)
            print(f"{'OVERALL':20}{'':12}{'':12}{mean:+10,.0f}"
                  f"{(mean/se if se else 0):+8.2f}{f'{w}/{l}':>10}")
        if args.out:
            (ROOT / args.out).write_text(json.dumps(by, indent=1))
            print(f"wrote {args.out}")

    elif args.mode == "eval":
        patch = json.loads(args.settings) if args.settings else None
        half = max(1, args.procs // 2)
        jobs = ([("cand", patch, None, ch) for ch in chunks(seeds, half)]
                + [("stock", None, None, ch) for ch in chunks(seeds, half)])
        res = run_jobs(jobs, args.procs)
        merged = {}
        for key, rows in res.items():
            merged.setdefault(key, []).extend(rows)
        report(merged["stock"], merged["cand"], args.settings or "candidate")


if __name__ == "__main__":
    main()
