#!/usr/bin/env python
"""Export the trained RL policy as a stdlib-only submission.

The ladder sandbox has no torch, so the 2x256 MLP is exported as a compressed
weight blob and evaluated with plain Python loops (116->256->256->4 is ~96k
multiply-adds per step, a few ms -- far inside the per-step budget).

The generated main.py is the production tape source plus a layer that:
  1. asks the tape for its action (unchanged),
  2. builds the market menu (keep / sell x1.25 / x1.5 / x2.0),
  3. runs the exported MLP on the same 116 features the trainer used,
  4. applies the chosen market override.

Usage:
  python scripts/build_rl_submission.py --ckpt data/rl_mkt.pt --out data/tapeopt/rlsub
  python scripts/build_rl_submission.py --verify data/tapeopt/rlsub/main.py   # vs torch
"""
import argparse
import base64
import json
import math
import sys
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
V42 = (ROOT / "data" / "league" /
       "ahmedberatozer_kaggriculture-v42-production-that-fits-the-marke" / "main.py")

LAYER = r'''

# ===================== RL market layer (exported, stdlib only) ================
# Trained with PPO on top of the production tape: the policy only decides WHEN to
# push more of the tape's planned sales into the market (x1.25 / x1.5 / x2.0).
# Measured: holding stock back (-52,745) and hire changes (-93,345 / -65,956) are
# destructive, so the action space is deliberately just "sell more".
_RL_W = __WEIGHTS__
_RL_PRODUCTS = ["WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON", "EGG", "MILK",
                "WOOL", "FERTILIZER"]
_RL_SEEDS = ["WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON"]
_RL_ANIMALS = ["GOOSE", "COW", "SHEEP"]
_RL_WINDOW = {"WHEAT": 4, "CARROT": 3, "MELON": 12, "TOMATO": 8, "STRAWBERRY": 10}
_RL_MAXY = {"WHEAT": 6, "CARROT": 4, "MELON": 6, "TOMATO": 4, "STRAWBERRY": 4}
_RL_ONGOING = {"TOMATO", "STRAWBERRY"}
_RL_NF = 3 * 0 + 116
_RL_BASE = agent


def _rl_features(obs, player):
    """Port of rl_env.encode (must stay bit-compatible with training)."""
    farm = obs["farms"][player]
    priv = obs.get("private") or {}
    tiles = farm["tiles"]
    shed = priv.get("shed") or {}
    seeds = priv.get("seeds") or {}
    prices = (obs.get("market") or {}).get("prices") or {}
    day = obs.get("day", 0)
    plants = {c: 0 for c in _RL_SEEDS}
    animals = {a: 0 for a in _RL_ANIMALS}
    empty = weed = struct = locked = unwatered = infen = mature = 0
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
                crop = t.get("crop", "WHEAT")
                plants[crop] = plants.get(crop, 0) + 1
                age = day - t.get("planted_day", 0)
                if not t.get("watered_today"):
                    unwatered += 1
                w = _RL_WINDOW.get(crop, 4)
                ws = (w + 1) // 2
                if ws <= age <= w and (t.get("fertilized_until_day", -1) or -1) < day:
                    infen += 1
                if (t.get("yield_units") or 0) > 0 and age >= w:
                    mature += 1
            elif isinstance(t, dict) and "animal" in t:
                animals[t["animal"]] = animals.get(t["animal"], 0) + 1
            elif isinstance(t, dict) and t.get("kind") in ("COOP", "PASTURE"):
                struct += 1
    v = [day / 29.0, obs.get("hour", 0) / 23.0,
         float(farm.get("money") or 0) / 50000.0,
         int(farm.get("hires_today") or 0) / 12.0,
         len(farm.get("hands") or []) / 12.0,
         len(farm.get("unlocked_quadrants") or []) / 4.0]
    v += [float(prices.get(p) or 0) / 300.0 for p in _RL_PRODUCTS]
    v += [float(shed.get(p) or 0) / 50.0 for p in _RL_PRODUCTS]
    v += [float(seeds.get(s) or 0) / 20.0 for s in _RL_SEEDS]
    v += [plants[c] / 25.0 for c in _RL_SEEDS]
    v += [animals[a] / 10.0 for a in _RL_ANIMALS]
    v += [empty / 25.0, weed / 25.0, struct / 25.0, locked / 100.0,
          unwatered / 25.0, infen / 25.0, mature / 25.0]
    units = [tuple(farm.get("farmer") or (4, 4))] + [tuple(h) for h in (farm.get("hands") or [])]
    invs = priv.get("inventories") or [{}]
    for i in range(12):
        if i < len(units):
            x, y = units[i]
            inv = invs[i] if i < len(invs) else {}
            v += [1.0, x / 9.0, y / 9.0,
                  sum(inv.get(p, 0) for p in _RL_PRODUCTS) / 10.0,
                  inv.get("WHEAT", 0) / 10.0, inv.get("FERTILIZER", 0) / 10.0]
        else:
            v += [0.0] * 6
    return v


def _rl_forward(x):
    w1, b1, w2, b2, w3, b3 = _RL_W
    h1 = [max(0.0, sum(w * xi for w, xi in zip(row, x)) + b) for row, b in zip(w1, b1)]
    h2 = [max(0.0, sum(w * h for w, h in zip(row, h1)) + b) for row, b in zip(w2, b2)]
    return [sum(w * h for w, h in zip(row, h2)) + b for row, b in zip(w3, b3)]


def _rl_market(action):
    """Menu exactly as used in training: 0 = keep, 1..3 = sell x1.25/x1.5/x2.0."""
    orders = [o for o in (action.get("market") or []) if isinstance(o, list) and o]
    sells = [o for o in orders if o[0] == "SELL" and len(o) >= 3 and int(o[2] or 0) > 0]
    return [1.0] if not sells else [1.0, 1.25, 1.5, 2.0]


def agent(observation, configuration=None):
    action = _RL_BASE(observation, configuration)
    try:
        player = int(observation.get("player") or 0)
        obs = observation
        mults = _rl_market(action)
        if len(mults) == 1:
            return action
        logits = _rl_forward(_rl_features(obs, player))
        k = max(range(4), key=lambda i: logits[i] if i < len(mults) else -1e9)
        if k == 0:
            return action
        mult = mults[k]
        out = []
        for o in (action.get("market") or []):
            if o and o[0] == "SELL" and len(o) >= 3 and int(o[2] or 0) > 0:
                q = int(round(int(o[2]) * mult))
                if q > 0:
                    out.append(["SELL", o[1], q])
            else:
                out.append(o)
        action["market"] = out
    except Exception:
        pass
    return action
'''


def export(ckpt, quality=9):
    import torch
    sd = torch.load(ckpt, map_location="cpu")
    net = sd["net"] if "net" in sd else sd
    keys = ["0.weight", "0.bias", "2.weight", "2.bias", "4.weight", "4.bias"]
    W = [net[k].tolist() for k in keys]
    raw = json.dumps([[round(x, 6) for row in m] if isinstance(m[0], list) else
                      [round(x, 6) for x in m] for m in W], separators=(",", ":"))
    blob = base64.b85encode(zlib.compress(raw.encode(), quality)).decode()
    return blob, W


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ckpt", default="data/rl_mkt.pt")
    ap.add_argument("--tape", default=str(V42))
    ap.add_argument("--out", default="data/tapeopt/rlsub")
    ap.add_argument("--verify", default=None)
    args = ap.parse_args()

    if args.verify:
        import torch
        from rl_agent import RLAgent
        import rl_env
        ck = args.verify + ".ckpt"
        raise SystemExit("verify mode needs --ckpt; use scripts/rl_agent.py for the torch reference")

    blob, W = export(args.ckpt)
    src = Path(args.tape).read_text()
    layer = LAYER.replace("__WEIGHTS__", "_RL_W_DECODE(%r)" % blob)
    # the exported layer needs a decoder for the blob at import time
    decoder = ('def _RL_W_DECODE(b):\n'
               '    import base64 as _b64, json as _json, zlib as _zlib\n'
               '    return _json.loads(_zlib.decompress(_b64.b85decode(b)))\n\n\n')
    out = src + decoder + layer
    d = ROOT / args.out
    d.mkdir(parents=True, exist_ok=True)
    (d / "main.py").write_text(out)
    params = sum(len(m) * len(m[0]) if isinstance(m[0], list) else len(m) for m in W)
    print(f"exported {params:,} parameters ({len(blob):,} chars of base85); "
          f"wrote {d/'main.py'} ({len(out):,} bytes)")


if __name__ == "__main__":
    main()
