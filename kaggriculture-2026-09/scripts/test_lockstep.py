#!/usr/bin/env python
"""Validate `scripts/lockstep.py` against the real kaggriculture engine.

Two independent checks, both run against `kaggle_environments` 1.32.7 in-process:

A. PRICE MODEL.  Every observation carries both `market.inventory` and
   `market.prices`.  For every step x every product of a real 720-step game,
   `lockstep.market_price(item, inventory[item])` must reproduce `prices[item]`
   exactly.  (The observation has no `market.params`, see the probe below.)

B. CLEARING.  For random order pairs we reset a real env, overwrite the market
   inventory and both sheds with the trial's starting state, step the env once
   with those orders as the two players' actions, and compare the engine's money
   delta and final inventory against `lockstep.clear()`.

Usage:  .venv/bin/python scripts/test_lockstep.py [--trials 400] [--seed 7]
"""
from __future__ import annotations

import argparse
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import lockstep  # noqa: E402

PRODUCTS = list(lockstep.PRODUCTS)
CHAMPION = ROOT / "data" / "tapeopt" / "rgcs" / "main.py"


def _load_agent(path):
    ns = {"__name__": "probe_mod"}
    exec(compile(Path(path).read_text(), str(path), "exec"), ns)
    return ns["agent"]


# --------------------------------------------------------------------------- A
def check_prices(seed=9000, verbose=True):
    """market_price must reproduce the observation's own `prices` on every step."""
    from kaggle_environments import make

    seen_params = set()
    steps_seen = 0
    checks = 0
    bad = []
    agent = _load_agent(CHAMPION)

    def wrap(player):
        def fn(obs):
            seen_params.update((obs.get("market") or {}).keys())
            inv = (obs.get("market") or {}).get("inventory") or {}
            prices = (obs.get("market") or {}).get("prices") or {}
            nonlocal checks
            for item in PRODUCTS:
                if item not in inv or item not in prices:
                    continue
                checks += 1
                got = lockstep.market_price(item, int(inv[item]))
                if got != int(prices[item]):
                    bad.append((int(obs.get("step", -1)), item, int(inv[item]),
                                int(prices[item]), got))
            return agent(obs)
        return fn

    env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": seed})
    env.run([wrap(0), wrap(1)])
    steps_seen = len(env.steps)
    if verbose:
        print(f"A. price model: {checks} checks over {steps_seen} steps x 2 players "
              f"(seed {seed}) -> mismatches {len(bad)}")
        print(f"   observation market keys seen: {sorted(seen_params)}")
        if bad:
            for r in bad[:10]:
                print("   MISMATCH", r)
    return checks, bad


# --------------------------------------------------------------------------- B
def _random_orders(rng, item_pool, n_max=6, q_max=25):
    ops = ["SELL", "SELL", "SELL", "BUY_SEED", "BUY_ANIMAL", "BUY_PRODUCT", "HIRE", "BUY_LAND"]
    out = []
    for _ in range(rng.randint(0, n_max)):
        op = rng.choice(ops)
        if op == "HIRE":
            out.append(["HIRE"])
            continue
        if op == "BUY_LAND":
            out.append(["BUY_LAND"])
            continue
        item = rng.choice(item_pool[op])
        n = rng.choice([0, 1, 2, 3, 5, 8, 15, q_max])
        out.append([op, item, n])
    # occasional malformed order, to exercise the abort path
    if rng.random() < 0.25:
        k = rng.randrange(len(out) + 1) if out else 0
        junk = rng.choice([["SELL"], ["SELL", "WHEAT"], ["BOGUS"], [], ["SELL", "WHEAT", "x"],
                           ["SELL", "NOPE", 4], ["BUY_PRODUCT", "MILK", 3], "junk"])
        out.insert(k, junk)
    return out


def _inject(env, inv0, shed0, shed1):
    obs = env.state[0].observation
    for item in PRODUCTS:
        obs.market.inventory[item] = int(inv0[item])
    for item in PRODUCTS:
        env.state[0].observation.private.shed[item] = int(shed0.get(item, 0))
        env.state[1].observation.private.shed[item] = int(shed1.get(item, 0))
    # a real market always has consistent prices; the engine does not use them for
    # clearing, but a mismatch would be a smell, so refresh them by hand.
    for item in PRODUCTS:
        obs.market.prices[item] = lockstep.market_price(item, int(inv0[item]))


def check_clearing(trials=400, seed=7, verbose=True):
    from kaggle_environments import make

    rng = random.Random(seed)
    item_pool = {
        "SELL": PRODUCTS,
        "BUY_SEED": list(lockstep.CROPS),
        "BUY_ANIMAL": list(lockstep.ANIMALS),
        "BUY_PRODUCT": list(lockstep.BUYABLE_PRODUCTS),
    }
    fails = []
    for t in range(trials):
        e_seed = rng.randrange(0, 10 ** 6)
        env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": e_seed})
        env.reset()
        # run a few steps so the env is out of the "day 0 hour 0" corner but still
        # before any town consumption or end-of-day refresh.
        env.step([{"farmer": ["PASS"], "hands": [], "market": []},
                  {"farmer": ["PASS"], "hands": [], "market": []}])
        env.step([{"farmer": ["PASS"], "hands": [], "market": []},
                  {"farmer": ["PASS"], "hands": [], "market": []}])

        inv0 = {i: rng.choice([9900, 9990, 10000, 10000, 10050, 10120, 20000]) for i in PRODUCTS}
        if rng.random() < 0.4:
            inv0[rng.choice(PRODUCTS)] = rng.choice([10000, 10000, 10020])
        shed0 = {i: 0 for i in PRODUCTS}
        shed1 = {i: 0 for i in PRODUCTS}
        for i in PRODUCTS:
            if rng.random() < 0.5:
                shed0[i] = rng.choice([0, 1, 3, 12, 40])
            if rng.random() < 0.5:
                shed1[i] = rng.choice([0, 1, 3, 12, 40])
        money0 = float(rng.choice([3000, 3000, 20000]))
        money1 = float(rng.choice([3000, 3000, 20000]))
        _inject(env, inv0, shed0, shed1)
        env.state[0].observation.farms[0]["money"] = money0
        env.state[0].observation.farms[1]["money"] = money1

        o0 = _random_orders(rng, item_pool)
        o1 = _random_orders(rng, item_pool)
        if rng.random() < 0.5:      # bias towards pure SELL-vs-SELL race cases
            o0 = [o for o in o0 if isinstance(o, list) and o and o[0] == "SELL"]
            o1 = [o for o in o1 if isinstance(o, list) and o and o[0] == "SELL"]
            if rng.random() < 0.5:
                o0 = [["SELL", it, rng.choice([1, 4, 9, 20])]
                      for it in rng.sample(PRODUCTS, rng.randint(0, 3))]
            if rng.random() < 0.5:
                o1 = [["SELL", it, rng.choice([1, 4, 9, 20])]
                      for it in rng.sample(PRODUCTS, rng.randint(0, 3))]

        exp = lockstep.clear(o0, o1, inv0, (shed0, shed1),
                             money=(money0, money1), hires_today=(0, 0), quadrants=(1, 1))
        env.step([{"farmer": ["PASS"], "hands": [], "market": o0},
                  {"farmer": ["PASS"], "hands": [], "market": o1}])
        obs = env.state[0].observation
        got_money = [float(obs.farms[0]["money"]), float(obs.farms[1]["money"])]
        got_inv = {i: int(obs.market.inventory[i]) for i in PRODUCTS}
        got_shed = [{i: int(env.state[p].observation.private.shed[i]) for i in PRODUCTS}
                    for p in (0, 1)]

        errs = []
        for p in (0, 1):
            if abs(exp["money"][p] - got_money[p]) > 1e-9:
                errs.append(f"money[{p}] exp {exp['money'][p]} got {got_money[p]}")
        for i in PRODUCTS:
            if exp["inv"][i] != got_inv[i]:
                errs.append(f"inv[{i}] exp {exp['inv'][i]} got {got_inv[i]}")
            for p in (0, 1):
                if exp["shed"][p][i] != got_shed[p][i]:
                    errs.append(f"shed[{p}][{i}] exp {exp['shed'][p][i]} got {got_shed[p][i]}")
        if errs:
            fails.append({"trial": t, "seed": e_seed, "orders": [o0, o1],
                          "inv0": inv0, "shed0": shed0, "shed1": shed1, "errs": errs[:8]})
    if verbose:
        print(f"B. clearing: {trials} random trials -> failures {len(fails)}")
        for f in fails[:5]:
            print("   FAIL", f["trial"], f["errs"])
            print("        orders", f["orders"])
    return trials, fails


# --------------------------------------------------------------------------- C
def check_selfconsistency(trials=300, seed=11, verbose=True):
    """`clear_item` (the layer's fast path) must equal `clear` on SELL-only lists.

    With SELL-only orders the clearing is exactly separable per item (a price is a
    pure function of that item's own inventory, and a shed is per player), so
    summing `clear_item` over items must reproduce `clear`'s joint revenue.
    """
    rng = random.Random(seed)
    bad = 0
    nslots = 6
    for _ in range(trials):
        o0, o1 = [], []
        for _k in range(rng.randint(1, 5)):
            o0.append(["SELL", rng.choice(PRODUCTS), rng.randint(1, 12)])
        for _k in range(rng.randint(1, 5)):
            o1.append(["SELL", rng.choice(PRODUCTS), rng.randint(1, 12)])
        inv0 = {i: rng.choice([9990, 10000, 10000, 10040]) for i in PRODUCTS}
        stock = {i: rng.choice([4, 12, 40]) for i in PRODUCTS}
        exp = lockstep.clear(o0, o1, inv0, (dict(stock), dict(stock)))
        tot = [0.0, 0.0]
        for item in PRODUCTS:
            me = lockstep.sell_schedule(o0, item, nslots)
            th = lockstep.sell_schedule(o1, item, nslots)
            if not me and not th:
                continue
            r0, r1, _st, _inv = lockstep.clear_item(me, th, item, inv0[item],
                                                    stock[item], stock[item])
            tot[0] += r0
            tot[1] += r1
        if abs(tot[0] - exp["rev"][0]) > 1e-9 or abs(tot[1] - exp["rev"][1]) > 1e-9:
            bad += 1
            if verbose and bad <= 5:
                print("   FASTPATH MISMATCH", o0, o1, tot, exp["rev"])
    if verbose:
        print(f"C. clear_item vs clear (per-item decomposition): {trials} trials "
              f"-> mismatches {bad}")
    return trials, bad


def check_real_games(seeds=(9000, 9001), verbose=True):
    """End-to-end: replay every step of a real champion game and match money exactly.

    This exercises the replica on the champion's own order lists -- HIRE,
    BUY_PRODUCT, BUY_SEED, BUY_ANIMAL, multi-slot SELL lots -- against the money the
    engine actually produced, with the shed taken at market time (see
    scripts/race_trace.py for why the raw observation shed is not enough).
    """
    import race_trace as rt

    total, mism = 0, 0
    details = []
    for seed in seeds:
        trace, final = rt.record(seed, [str(CHAMPION), str(CHAMPION)])
        steps = sorted(set(trace[0]) & set(trace[1]))
        m = 0
        for s in steps:
            if s + 1 not in trace[0] or s + 1 not in trace[1]:
                continue
            r = rt.replay_step(trace, s)
            for p in (0, 1):
                total += 1
                if abs(r["money"][p] - trace[p][s + 1]["money"]) > 1e-9:
                    m += 1
        mism += m
        details.append((seed, final, len(steps), m))
        if verbose:
            print(f"D. real game seed {seed}: final {final}, {len(steps)} steps, "
                  f"money mismatches {m}")
    if verbose:
        print(f"   total {total} player-steps replayed, mismatches {mism}")
    return total, mism


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--trials", type=int, default=400)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--skip-price", action="store_true")
    ap.add_argument("--skip-games", action="store_true")
    args = ap.parse_args()

    ok = True
    if not args.skip_price:
        checks, bad = check_prices()
        ok &= (len(bad) == 0 and checks > 0)
    n, fails = check_clearing(trials=args.trials, seed=args.seed)
    ok &= (len(fails) == 0)
    n2, bad2 = check_selfconsistency()
    ok &= (bad2 == 0)
    if not args.skip_games:
        _n3, bad3 = check_real_games()
        ok &= (bad3 == 0)
    print("RESULT:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
