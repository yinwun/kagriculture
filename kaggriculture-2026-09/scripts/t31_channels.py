#!/usr/bin/env python
"""Task 30/31: five-channel cash decomposition of the current line's close games.

Per game, per seat, per item, from the instrumented bank-exact re-simulation (shift=1) plus the
replay's own observations:

  CASH (exact, reconciles):  sell revenue per item, purchase cost per item, hire and land costs.
                             gap_money = sum_items [rev_me - cost_me] - [rev_opp - cost_opp]
                                       - (hire+land)_me + (hire+land)_opp
  CHANNEL 1 PRODUCTION       units harvested (proxy: sold + discarded + ending stock - opening stock
                             - bought); capacity proxies: planted tile-days, waterings, animal-days
  CHANNEL 2 SELLING VOLUME   units sold per item
  CHANNEL 3 REALISED PRICE   mean price per unit sold per item (symmetric volume/price split)
  CHANNEL 4 INPUT COST       units bought and cash spent per item (wheat = herd input)
  CHANNEL 5 LOGISTICS        discarded units, and ending unsold stock valued at closing price

The cash channels reconcile exactly (residual reported); production/logistics are the *explanation*
of the volume gaps, not additive, and are reported separately as such.

Usage: python scripts/t31_channels.py --attr data/replay-attr-straw-t30.json --replays data/replays-t30
"""
import argparse, collections, glob, json, statistics as st
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
NP = 24
CROPS = ("WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON")


def hook_log(actions, cfg, seed):
    import kaggle_environments.envs.kaggriculture.kaggriculture as K
    from kaggle_environments import make
    log, cur = [], {}
    orig = (K._process_market, K._commit_unit, K._do_hire, K._do_buy_land, K._drop_inventories_to_shed)

    def pm(state, env):
        o = state[0].observation
        cur["farms"] = o.farms
        cur["step"] = K.get(o, "step", None)
        return orig[0](state, env)

    def seat(farm):
        return next((i for i, f in enumerate(cur.get("farms") or []) if f is farm), -1)

    def commit(op, item, price, farm, private, market, shed_capacity=100):
        pid = seat(farm)
        ok = orig[1](op, item, price, farm, private, market, shed_capacity)
        if ok and op in ("SELL", "BUY_PRODUCT", "BUY_ANIMAL"):
            log.append({"seat": pid, "op": op, "item": str(item), "price": float(price),
                        "step": cur.get("step")})
        return ok

    def hire(farm, private, board_size, mult=1):
        pid, before = seat(farm), float(farm.get("money", 0))
        r = orig[2](farm, private, board_size, mult)
        if float(farm.get("money", 0)) != before:
            log.append({"seat": pid, "op": "HIRE", "item": "HAND",
                        "price": float(farm["money"]) - before, "step": cur.get("step")})
        return r

    def land(farm, board_size):
        pid, before = seat(farm), float(farm.get("money", 0))
        r = orig[3](farm, board_size)
        if float(farm.get("money", 0)) != before:
            log.append({"seat": pid, "op": "LAND", "item": "LAND",
                        "price": float(farm["money"]) - before, "step": cur.get("step")})
        return r

    def drop(private, capacity):
        shed = private.get("shed") or {}
        before = sum(shed.values())
        inv = sum(sum(v for v in (d or {}).values()) for d in (private.get("inventories") or []))
        orig[4](private, capacity)
        d = inv - (sum(shed.values()) - before)
        if d > 0:
            log.append({"seat": -2, "op": "DISCARD", "item": "?", "price": float(d),
                        "step": cur.get("step")})
    K._process_market, K._commit_unit, K._do_hire, K._do_buy_land, K._drop_inventories_to_shed = pm, commit, hire, land, drop
    try:
        env = make("kaggriculture", configuration=cfg, debug=True)
        env.info["seed"] = seed
        env.run([agent(actions, 0), agent(actions, 1)])
        repro = [round(float(env.steps[-1][p]["reward"] or 0)) for p in (0, 1)]
    finally:
        (K._process_market, K._commit_unit, K._do_hire, K._do_buy_land,
         K._drop_inventories_to_shed) = orig
    return log, repro


def agent(actions, seat_, shift=1):
    def a(obs):
        s = obs.get("step") if isinstance(obs, dict) else 0
        s = (s or 0) + shift
        x = actions[s][seat_] if 0 <= s < len(actions) else None
        return x if isinstance(x, dict) else {}
    return a


def stock(obs, seat_):
    priv = obs.get("private") or {}
    tot = collections.Counter()
    for item, n in (priv.get("shed") or {}).items():
        tot[item] += max(0, int(n))
    for inv in (priv.get("inventories") or []):
        for item, n in (inv or {}).items():
            tot[item] += max(0, int(n))
    return tot


def farm_counts(tiles):
    c = collections.Counter()
    for row in tiles:
        for cell in row:
            if not isinstance(cell, dict):
                continue
            if cell.get("kind") == "PLANT":
                c["CROP_" + str(cell.get("crop"))] += 1
            elif cell.get("kind") in ("PASTURE", "COOP") and cell.get("animal"):
                c["ANIMAL_" + str(cell["animal"])] += 1
    return c


def one_game(path, my_seat):
    d = json.loads(Path(path).read_text())
    steps = d["steps"]
    me, opp = my_seat, 1 - my_seat
    actions = [[steps[t][p].get("action") or {} for p in (0, 1)] for t in range(len(steps))]
    cfg = dict(d.get("configuration") or {}); cfg["seed"] = None
    log, repro = hook_log(actions, cfg, d.get("info", {}).get("seed"))
    gate = repro == [round(float(r)) for r in d["rewards"]]

    def agg(seat_):
        rev = collections.defaultdict(float); units = collections.defaultdict(int)
        cost = collections.defaultdict(float); bu = collections.defaultdict(int)
        hire = land = 0.0
        for e in log:
            if e["seat"] != seat_:
                continue
            if e["op"] == "SELL":
                rev[e["item"]] += e["price"]; units[e["item"]] += 1
            elif e["op"] == "BUY_PRODUCT":
                cost[e["item"]] += e["price"]; bu[e["item"]] += 1
            elif e["op"] == "HIRE":
                hire += -e["price"]
            elif e["op"] == "LAND":
                land += -e["price"]
        return rev, units, cost, bu, hire, land

    R = {s: agg(s) for s in (me, opp)}
    disc = sum(e["price"] for e in log if e["op"] == "DISCARD" and e["seat"] == -2) / 2.0
    disc_me = disc / 2.0  # engine discards both seats' overflow in one pass; report as shared proxy
    o0 = {s: stock(steps[0][s]["observation"], s) for s in (me, opp)}
    oT = {s: stock(steps[-1][s]["observation"], s) for s in (me, opp)}
    prices = dict(steps[-1][me]["observation"]["market"]["prices"])
    # farm side
    farms = {}
    for s in (me, opp):
        cnt = collections.Counter()
        for day in (6, 12, 18, 24):
            t = min(day * NP, len(steps) - 1)
            cnt.update(farm_counts(steps[t][s]["observation"]["farms"][s]["tiles"]))
        farms[s] = cnt
    verbs = collections.Counter()
    for t in range(len(steps) - 1):
        a = actions[t + 1][me]
        for cmd in [a.get("farmer") or []] + list(a.get("hands") or []):
            if isinstance(cmd, list) and cmd:
                verbs[str(cmd[0])] += 1
    return {"gate": gate, "margin": float(d["rewards"][me]) - float(d["rewards"][opp]),
            "log": log, "R": R, "me": me, "disc": disc_me,
            "open": {s: dict(o0[s]) for s in (me, opp)}, "end": {s: dict(oT[s]) for s in (me, opp)},
            "prices": prices, "farms": {s: dict(farms[s]) for s in (me, opp)},
            "verbs": dict(verbs)}


def mean(xs):
    return st.mean(xs) if xs else 0.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--attr", default="data/replay-attr-straw-t30.json")
    ap.add_argument("--replays", default="data/replays-t30")
    ap.add_argument("--out", default="data/t31-channels.json")
    ap.add_argument("--ref", default="56447790")
    args = ap.parse_args()
    games_attr = json.loads((Path(ROOT) / args.attr).read_text())
    games_attr = next(iter(games_attr.values())) if isinstance(games_attr, dict) else games_attr
    eps = {}
    raw = json.loads((ROOT / "data" / "episodes-{args.ref}-raw.json").read_text())
    for ep in raw:
        ag = ep.get("agents") or []
        mine = [a for a in ag if str(a.get("submissionId")) == args.ref]
        if len(ag) == 2 and mine:
            eps[str(ep["id"])] = int(mine[0].get("index", 0))
    out = []
    for p in sorted(glob.glob(str(ROOT / args.replays / "episode-*-replay.json"))):
        eid = Path(p).name.split("-")[1]
        if eid not in eps:
            continue
        try:
            g = one_game(p, eps[eid])
        except Exception as exc:
            print(f"  {eid} FAILED {type(exc).__name__}"); continue
        if not g["gate"]:
            print(f"  {eid} GATE FAIL"); continue
        g["episode"] = eid
        out.append(g)
    print(f"{len(out)} games attributed with the cash walk")
    cls = {"loss": [g for g in out if g["margin"] < -500],
           "near": [g for g in out if -500 <= g["margin"] < 0],
           "win": [g for g in out if g["margin"] >= 0]}
    items = ["WHEAT", "WOOL", "STRAWBERRY", "MILK", "EGG", "CARROT", "TOMATO", "MELON", "FERTILIZER"]
    summary = {}
    for cname, gg in cls.items():
        if not gg:
            continue
        print(f"\n=== {cname} (n={len(gg)}, mean money margin {mean([g['margin'] for g in gg]):+,.0f}) ===")
        print(f"  {'item':12} {'u_me':>7} {'u_opp':>7} {'p_me':>7} {'p_opp':>7} {'rev_me':>9} {'rev_opp':>9} "
              f"{'vol eff':>9} {'price eff':>10} {'buy_me':>8} {'buy_opp':>8} {'end_me':>7} {'end_opp':>7}")
        vol_tot = price_tot = 0.0
        rowsum = {}
        for it in items:
            um = mean([g["R"][g["me"]][1].get(it, 0) for g in gg])
            uo = mean([g["R"][1 - g["me"]][1].get(it, 0) for g in gg])
            rm = mean([g["R"][g["me"]][0].get(it, 0.0) for g in gg])
            ro = mean([g["R"][1 - g["me"]][0].get(it, 0.0) for g in gg])
            pm = rm / um if um else 0.0
            po = ro / uo if uo else 0.0
            p_avg, u_avg = (pm + po) / 2, (um + uo) / 2
            vol, pr = (um - uo) * p_avg, (pm - po) * u_avg
            vol_tot += vol; price_tot += pr
            bm = mean([g["R"][g["me"]][2].get(it, 0.0) for g in gg])
            bo = mean([g["R"][1 - g["me"]][2].get(it, 0.0) for g in gg])
            em = mean([g["end"][g["me"]].get(it, 0) for g in gg])
            eo = mean([g["end"][1 - g["me"]].get(it, 0) for g in gg])
            rowsum[it] = {"u_me": um, "u_opp": uo, "p_me": pm, "p_opp": po, "rev_me": rm, "rev_opp": ro,
                          "vol": vol, "price": pr, "cost_me": bm, "cost_opp": bo, "end_me": em, "end_opp": eo}
            print(f"  {it:12} {um:>7.1f} {uo:>7.1f} {pm:>7.1f} {po:>7.1f} {rm:>9,.0f} {ro:>9,.0f} "
                  f"{vol:>+9,.0f} {pr:>+10,.0f} {bm:>8,.0f} {bo:>8,.0f} {em:>7.1f} {eo:>7.1f}")
        hire = mean([g["R"][g["me"]][4] - g["R"][1 - g["me"]][4] for g in gg])
        land = mean([g["R"][g["me"]][5] - g["R"][1 - g["me"]][5] for g in gg])
        cash_gap = mean([(sum(g["R"][g["me"]][0].values()) - sum(g["R"][g["me"]][2].values()))
                         - (sum(g["R"][1 - g["me"]][0].values()) - sum(g["R"][1 - g["me"]][2].values()))
                         for g in gg])
        money_gap = mean([g["margin"] for g in gg])
        residual = money_gap - (cash_gap + hire + land)
        print(f"  money gap {money_gap:+,.0f} = market {cash_gap:+,.0f} + hire {hire:+,.0f} + land {land:+,.0f} "
              f"-> residual {residual:+,.0f}")
        print(f"  sell-revenue split: volume {vol_tot:+,.0f}  price {price_tot:+,.0f}   "
              f"discards/game(shared proxy) {mean([g['disc'] for g in gg]):.1f} units")
        print(f"  farm tiles (mean count, day 6/12/18/24 sums): me "
              f"{ {k: round(v/len(gg),1) for k,v in sorted(collections.Counter({kk: sum(g['farms'][g['me']].get(kk,0) for g in gg) for kk in set().union(*[set(g['farms'][g['me']]) for g in gg])}).items())[:6]} }")
        for k in ("HARVEST", "WATER", "PLANT", "FEED", "CARE", "COLLECT_FERTILIZER"):
            pass
        vb = {k: round(mean([g["verbs"].get(k, 0) for g in gg]), 1) for k in
              ("HARVEST", "WATER", "PLANT", "FEED", "CARE", "COLLECT_FERTILIZER", "PASS")}
        print(f"  worker verbs (me): {vb}")
        summary[cname] = {"n": len(gg), "money_gap": money_gap, "market": cash_gap, "hire": hire,
                          "land": land, "residual": residual, "vol_total": vol_tot,
                          "price_total": price_tot, "items": rowsum, "verbs": vb,
                          "discards": mean([g["disc"] for g in gg])}
    (ROOT / args.out).write_text(json.dumps(summary, indent=1, default=str))
    print(f"\nwrote {args.out}")


if __name__ == "__main__":
    main()
