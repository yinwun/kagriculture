#!/usr/bin/env python
"""Step-wise RL harness for kaggriculture: tape as the behavior policy.

Why this shape
--------------
Learning the whole game from scratch means learning an action space of
(12 units x 20 ops + 10 market orders) from a ~5% baseline.  The tape family is
already strong, so the tractable RL problem is a *residual* one: keep the tape's
action and learn only WHEN to override one unit or add one market order.  That
gives a small discrete action space (~3 per unit + 4 market) on top of a strong
behavior policy, which is exactly what PPO handles well.

What is here
------------
* ``encode``      : observation -> fixed-size feature vector (policy input)
* ``override_menu``: the discrete residual action space
* ``run_episode`` : drives ``env.step`` directly (no env.run overhead), so a game
                    is ~1.5-2.5 s and can be parallelised over 100 cores
* ``--bench``     : measure step-wise throughput
* ``--sanity``    : policy = "always no-op" must reproduce the stock wallet
                    exactly (that is the correctness check for the whole loop)

Usage:
  python scripts/rl_env.py --bench 20
  python scripts/rl_env.py --sanity 3
  python scripts/rl_env.py --record data/bc.jsonl --episodes 4
"""
import argparse
import copy
import json
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
V42 = (ROOT / "data" / "league" /
       "ahmedberatozer_kaggriculture-v42-production-that-fits-the-marke" / "main.py")

PRODUCTS = ["WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON", "EGG", "MILK",
            "WOOL", "FERTILIZER"]
SEEDS = ["WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON"]
ANIMALS = ["GOOSE", "COW", "SHEEP"]
MOVES = {"NORTH": (0, -1), "SOUTH": (0, 1), "EAST": (1, 0), "WEST": (-1, 0)}
WINDOW = {"WHEAT": 4, "CARROT": 3, "MELON": 12, "TOMATO": 8, "STRAWBERRY": 10}
MAXY = {"WHEAT": 6, "CARROT": 4, "MELON": 6, "TOMATO": 4, "STRAWBERRY": 4}
ONGOING = {"TOMATO", "STRAWBERRY"}


def is_ripe(tile, day):
    """Only harvest what the tape would harvest: at the end of the yield window.

    Offering HARVEST whenever yield_units > 0 was catastrophic: wheat starts at 1
    unit, so the policy harvested seedlings and destroyed the crop (measured:
    reward 83,480 -> 0, 440 early harvests).
    """
    crop = tile.get("crop")
    age = day - tile.get("planted_day", day)
    u = tile.get("yield_units") or 0
    if u <= 0:
        return False
    if crop in ONGOING:
        return u >= 2 or age >= WINDOW.get(crop, 10)
    return age >= WINDOW.get(crop, 4) or u >= MAXY.get(crop, 6)


def _get(d, k, default=None):
    return d.get(k, default) if isinstance(d, dict) else getattr(d, k, default)


def build_agent(path=V42, settings_patch=None, tag="base"):
    src = Path(path).read_text()
    if settings_patch:
        import re
        m = re.search(r"_SETTINGS=\{([^}]*)\}", src)
        stock = dict(re.findall(r"'([a-z_]+)':\s*(True|False)", m.group(1)))
        stock = {k: (v == "True") for k, v in stock.items()}
        stock.update(settings_patch)
        src = src[:m.start()] + "_SETTINGS=" + repr(stock) + src[m.end():]
    ns = {"__name__": f"rl_agent_{tag}"}
    exec(compile(src, f"<{tag}>", "exec"), ns)
    return ns["agent"]


# ---------------------------------------------------------------- features
def encode(obs, player):
    """Compact, bounded feature vector: global farm state + per-unit state."""
    f = obs["farms"][player]
    priv = obs.get("private") or {}
    tiles = f["tiles"]
    counts = {p: 0 for p in PRODUCTS}
    shed = priv.get("shed") or {}
    seeds = priv.get("seeds") or {}
    prices = (obs.get("market") or {}).get("prices") or {}
    plants = {c: 0 for c in SEEDS}
    animals = {a: 0 for a in ANIMALS}
    empty = weed = struct_ = locked = 0
    unwatered = infen = mature = 0
    for row in tiles:
        for t in row:
            if t == "LOCKED":
                locked += 1
                continue
            if t is None:
                empty += 1
                continue
            if t == "WEED":
                weed += 1
                continue
            if isinstance(t, dict) and t.get("kind") == "PLANT":
                plants[t.get("crop", "WHEAT")] = plants.get(t.get("crop", "WHEAT"), 0) + 1
                age = obs.get("day", 0) - t.get("planted_day", 0)
                if not t.get("watered_today"):
                    unwatered += 1
                w = WINDOW.get(t.get("crop"), 4)
                ws = (w + 1) // 2
                if ws <= age <= w and (t.get("fertilized_until_day", -1) or -1) < obs.get("day", 0):
                    infen += 1
                if (t.get("yield_units") or 0) > 0 and age >= w:
                    mature += 1
            elif isinstance(t, dict) and "animal" in t:
                animals[t["animal"]] = animals.get(t["animal"], 0) + 1
            elif isinstance(t, dict) and t.get("kind") in ("COOP", "PASTURE"):
                struct_ += 1
    v = [obs.get("day", 0) / 29.0, (obs.get("hour", 0)) / 23.0,
         float(f.get("money") or 0) / 50000.0,
         int(f.get("hires_today") or 0) / 12.0,
         len(f.get("hands") or []) / 12.0,
         len(f.get("unlocked_quadrants") or []) / 4.0]
    v += [float(prices.get(p) or 0) / 300.0 for p in PRODUCTS]
    v += [float(shed.get(p) or 0) / 50.0 for p in PRODUCTS]
    v += [float(seeds.get(s) or 0) / 20.0 for s in SEEDS]
    v += [plants[c] / 25.0 for c in SEEDS]
    v += [animals[a] / 10.0 for a in ANIMALS]
    v += [empty / 25.0, weed / 25.0, struct_ / 25.0, locked / 100.0,
          unwatered / 25.0, infen / 25.0, mature / 25.0]
    # our own units
    units = [[tuple(f.get("farmer") or (4, 4))] + [tuple(h) for h in (f.get("hands") or [])]][0]
    invs = priv.get("inventories") or [{}]
    for i in range(12):
        if i < len(units):
            x, y = units[i]
            inv = invs[i] if i < len(invs) else {}
            carry = sum(inv.get(p, 0) for p in PRODUCTS)
            v += [1.0, x / 9.0, y / 9.0, carry / 10.0, inv.get("WHEAT", 0) / 10.0,
                  inv.get("FERTILIZER", 0) / 10.0]
        else:
            v += [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
    return np.asarray(v, dtype=np.float32)


FEATURE_DIM = 6 + len(PRODUCTS) * 2 + len(SEEDS) * 2 + len(ANIMALS) + 7 + 12 * 6


# ------------------------------------------------------------ action space
def override_menu(obs, player, base_action, pass_only=False):
    """Candidate residual overrides; index 0 is always 'keep the tape action'."""
    menu = [("none", None)]
    f = obs["farms"][player]
    tiles = f["tiles"]
    units = [tuple(f.get("farmer") or (4, 4))] + [tuple(h) for h in (f.get("hands") or [])]
    priv = obs.get("private") or {}
    invs = priv.get("inventories") or [{}]
    shed = priv.get("shed") or {}
    day = obs.get("day", 0)
    need = []
    for y in range(len(tiles)):
        for x in range(len(tiles[y])):
            t = tiles[y][x]
            if isinstance(t, dict) and t.get("kind") == "PLANT" and not t.get("watered_today"):
                w = WINDOW.get(t.get("crop"), 4)
                age = day - t.get("planted_day", day)
                if (t.get("consecutive_unwatered") or 0) >= 1 or (not t.get("ongoing") and
                                                                  (w + 1) // 2 <= age <= w):
                    need.append((x, y))
    tape_cmds = [base_action.get("farmer")] + list(base_action.get("hands") or [])
    for i, pos in enumerate(units):
        t = tiles[pos[1]][pos[0]] if 0 <= pos[1] < len(tiles) and 0 <= pos[0] < len(tiles[0]) else None
        # never override a step where the tape walks: replacing a move desynchronises
        # the script for the rest of the day (its later moves are positional)
        cmd = tape_cmds[i] if i < len(tape_cmds) else None
        if isinstance(cmd, list) and cmd and cmd[0] in MOVES:
            continue
        if pass_only:
            # strongest safety: only touch turns the tape itself leaves idle, so
            # nothing in its chain (pickup -> plant -> drop -> place) is displaced
            if not (isinstance(cmd, list) and cmd and cmd[0] == "PASS"):
                continue
        if isinstance(t, dict) and t.get("kind") == "PLANT" and not t.get("watered_today"):
            menu.append((f"u{i}_water_here", ("WATER_HERE", i)))
        if isinstance(t, dict) and is_ripe(t, day):
            menu.append((f"u{i}_harvest_here", ("HARVEST_HERE", i)))
        # NOTE: deliberately no movement overrides.  The tape is a SCRIPT
        # whose every move is relative to where the unit stands, so sending a
        # unit elsewhere desynchronises it for the rest of the day (measured:
        # override rate 4% -> 11% cost 97,000 coins on the yardstick).
        # Position-preserving ops (water/harvest/feed/care/collect) are safe.
        inv = invs[i] if i < len(invs) else {}
        if isinstance(t, dict) and "animal" in t:
            # FEED is omitted: it only consumes wheat (measured -1,699 over 3 seeds)
            # and the tape already feeds on schedule.
            if not t.get("cared_today"):
                menu.append((f"u{i}_care", ("CARE_HERE", i)))
            if t.get("fertilizer_available"):
                menu.append((f"u{i}_collect", ("COLLECT_HERE", i)))
    # NOTE: market overrides (HIRE / SELL) are deliberately absent.  Dumping a shed
    # stack collapses the shared market price: measured, random overrides WITH
    # market actions cost 76-98k per game while the same policy without them was
    # neutral (-219/+242/-236/+185).

    return menu


# Measured solo effects (always-on, 3 seeds): hold-half -52,745 | hold-all -94,683
# | +50% -529 | +100% -809 | hire+1 -93,345 | hire-1 -65,956.
# So the only non-destructive market action is *selling more*; holding starves the
# tape's own plan (the shed is capacity-capped) and the hire actions shift the
# tape's hand-slot mapping / fib cost curve.
MARKET_MENU = [
    ("keep", None),            # the tape's orders untouched
    ("sell_x125", 1.25),
    ("sell_x150", 1.5),        # push 50% more into this window
    ("sell_x200", 2.0),
]


def market_menu(obs, player, base_action):
    """Market-only residual actions.

    Unit-level overrides were measured to be either useless (+0: watering and
    caring are things the tape does anyway that day) or destructive (early
    harvest 0, path changes -97k), so the learnable space is the market layer --
    where the session's evidence says the money actually swings (38% revenue
    spread between identical agents, 53k game-to-game, price cliffs).
    """
    orders = [o for o in (base_action.get("market") or []) if isinstance(o, list) and o]
    sells = [o for o in orders if o[0] == "SELL" and len(o) >= 3 and int(o[2] or 0) > 0]
    hires = [o for o in orders if o[0] == "HIRE"]
    menu = [MARKET_MENU[0]]
    if sells:
        menu.extend(MARKET_MENU[1:])
    return menu


def apply_market_override(action, choice, obs, player, menu):
    """Scale the tape's SELL quantities / adjust its HIRE orders. Never adds stock."""
    if choice <= 0 or choice >= len(menu):
        return action
    tag = menu[choice][1]
    a = copy.deepcopy(action)
    orders = list(a.get("market") or [])
    if isinstance(tag, float):
        out = []
        for o in orders:
            if o and o[0] == "SELL" and len(o) >= 3 and int(o[2] or 0) > 0:
                q = int(round(int(o[2]) * tag))
                if q > 0:
                    out.append(["SELL", o[1], q])
            else:
                out.append(o)
        a["market"] = out
    elif tag == "HIRE_PLUS":
        a["market"] = orders + [["HIRE"]]
    elif tag == "HIRE_MINUS":
        dropped = False
        out = []
        for o in orders:
            if not dropped and o and o[0] == "HIRE":
                dropped = True
                continue
            out.append(o)
        a["market"] = out
    return a


def apply_override(action, choice, obs, player, menu):
    """Return a copy of the tape action with the chosen override applied."""
    import copy as _copy
    if choice == 0 or choice >= len(menu):
        return action
    kind = menu[choice][1]
    a = _copy.deepcopy(action)
    units = [tuple(obs["farms"][player].get("farmer") or (4, 4))] + \
            [tuple(h) for h in (obs["farms"][player].get("hands") or [])]
    op, u = kind[0], kind[1]
    if op == "HIRE":
        a["market"] = (a.get("market") or []) + [["HIRE"]]
        return a
    if op == "SELL":
        qty = (obs.get("private") or {}).get("shed", {}).get(u, 0)
        if qty:
            a["market"] = (a.get("market") or []) + [["SELL", u, qty]]
        return a
    if u is None or u >= len(units):
        return a
    cmd = None
    if op.endswith("_HERE"):
        cmd = {"WATER_HERE": ["WATER"], "HARVEST_HERE": ["HARVEST"],
               "FEED_HERE": ["FEED"], "CARE_HERE": ["CARE"],
               "COLLECT_HERE": ["COLLECT_FERTILIZER"]}[op]
    elif op == "GOTO_WATER":
        tgt = kind[2]
        d = MOVES
        dx, dy = tgt[0] - units[u][0], tgt[1] - units[u][1]
        if dx:
            cmd = ["EAST" if dx > 0 else "WEST"]
        elif dy:
            cmd = ["SOUTH" if dy > 0 else "NORTH"]
    if cmd is None:
        return a
    if u == 0:
        a["farmer"] = cmd
    else:
        hands = list(a.get("hands") or [])
        while len(hands) < u:
            hands.append(["PASS"])
        hands[u - 1] = cmd
        a["hands"] = hands
    return a


# ----------------------------------------------------------------- rollout
def run_episode(policy, seed, opponent_path=None, opponent_settings=None,
                record=False, config=None):
    """Drive env.step directly. policy(obs, player, base_action, menu) -> int."""
    import copy as _copy
    from kaggle_environments import make
    env = make("kaggriculture", configuration=config or {"episodeSteps": 720, "seed": seed})
    us = build_agent(V42, None, f"rl_us_{seed % 7}")
    them = build_agent(opponent_path or V42, opponent_settings, f"rl_them_{seed % 5}")
    env.reset()
    traj = []
    while not env.done:
        # hand the agents an isolated copy, exactly like env.run does: passing the
        # live observation lets an agent mutate engine state and the game diverges
        # (measured: 176,155 vs the true 83,480 on seed 700)
        obs0 = env.steps[-1][0]["observation"]
        obs1 = env.steps[-1][1]["observation"]
        c0 = _copy.deepcopy(obs0)
        c1 = _copy.deepcopy(obs1)
        # env.run stamps observation["player"] before calling each agent; the raw
        # step-wise observations do NOT, so seat 1 acted as if it were seat 0 and
        # scored exactly its 3,000 starting coins (measured divergence at step 0)
        # the raw step-wise observations only carry "step" for seat 0; env.run
        # stamps both, and V42 does int(observation["step"]) -> a missing key makes
        # every seat-1 action fall back to PASS (it scored exactly 3,000)
        turn = len(env.steps) - 1
        c0["player"] = 0
        c1["player"] = 1
        c0["step"] = turn
        c1["step"] = turn
        base0 = us(c0)
        base1 = them(c1)
        menu = override_menu(c0, 0, base0, pass_only=True)  # safe default
        feats = encode(c0, 0)
        pick = policy(feats, obs0, 0, base0, menu) if policy else 0
        a0 = apply_override(base0, pick, c0, 0, menu)
        if record:
            traj.append({"f": feats.tolist(), "choice": int(pick),
                         "menu": [m[0] for m in menu], "step": int(env.steps[-1][0]["observation"].get("step", 0))})
        env.step([a0, base1])
    final = env.steps[-1]
    reward = final[0]["reward"] or 0
    return {"reward": reward, "opp": final[1]["reward"] or 0,
            "status": final[0]["status"], "traj": traj}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bench", type=int, default=0)
    ap.add_argument("--sanity", type=int, default=0)
    ap.add_argument("--record", default=None)
    ap.add_argument("--episodes", type=int, default=4)
    ap.add_argument("--seed", type=int, default=700)
    ap.add_argument("--opponent", default=None)
    ap.add_argument("--settings", default=None)
    args = ap.parse_args()

    if args.bench:
        t0 = time.time()
        for i in range(args.bench):
            r = run_episode(None, args.seed + i)
        dt = time.time() - t0
        print(f"{args.bench} step-wise games in {dt:.1f}s = {3600*args.bench/dt:,.0f} games/hour/core")
        print(f"feature dim {FEATURE_DIM} | last reward {r['reward']:,.0f}")
        return

    if args.sanity:
        patch = json.loads(args.settings) if args.settings else None
        for i in range(args.sanity):
            seed = args.seed + i
            r = run_episode(None, seed)
            from kaggle_environments import make
            env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": seed})
            env.run([build_agent(V42, patch, "s1"), build_agent(V42, patch, "s2")])
            stock = env.steps[-1][0]["reward"] or 0
            print(f"seed {seed}: harness {r['reward']:,.0f} vs env.run {stock:,.0f} "
                  f"{'OK' if abs(r['reward']-stock) < 1 else 'MISMATCH'}")
        return

    if args.record:
        out = Path(args.record)
        out.parent.mkdir(parents=True, exist_ok=True)
        with out.open("w") as fh:
            for i in range(args.episodes):
                r = run_episode(None, args.seed + i, args.opponent, None, record=True)
                for row in r["traj"]:
                    fh.write(json.dumps(row) + "\n")
                print(f"seed {args.seed+i}: reward {r['reward']:,.0f} steps {len(r['traj'])}")
        print(f"wrote {out}")


if __name__ == "__main__":
    main()
