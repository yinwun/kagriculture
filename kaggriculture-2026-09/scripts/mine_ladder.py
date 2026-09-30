#!/usr/bin/env python
"""Mine public ladder episodes: win rate by opponent-rating band, loss clustering,
margin distribution.  Reads data/episodes-<ref>-raw.json (raw competition_list_episodes).

Usage: python scripts/mine_ladder.py --refs 56409633 56409622 --primary 56409633
"""
import argparse
import collections
import json
import statistics as st
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

BANDS = [(0, 1500), (1500, 1800), (1800, 2100), (2100, 2400), (2400, 2700), (2700, 10 ** 9)]


def band(score):
    if score is None:
        return "unknown"
    for lo, hi in BANDS:
        if lo <= score < hi:
            return f"{lo}-{hi if hi < 10**9 else '+'}"
    return "?"


def load(ref):
    p = ROOT / "data" / f"episodes-{ref}-raw.json"
    return json.loads(p.read_text())


def rows_for(eps, ref, lb):
    out = []
    for ep in eps:
        if ep.get("type") != "EPISODE_TYPE_PUBLIC":
            continue
        agents = ep.get("agents") or []
        if len(agents) != 2:
            continue
        mine = [a for a in agents if str(a.get("submissionId")) == str(ref)]
        if not mine:
            continue
        mine = mine[0]
        opp = [a for a in agents if a is not mine][0]
        if mine.get("reward") is None or opp.get("reward") is None:
            continue
        out.append({"time": str(ep.get("endTime")), "me": float(mine["reward"]),
                    "opp": float(opp["reward"]), "opp_team": opp.get("teamName"),
                    "opp_team_id": opp.get("teamId"), "opp_sub": str(opp.get("submissionId")),
                    "opp_score": lb.get(int(opp.get("teamId") or 0))})
    return sorted(out, key=lambda r: r["time"])


def report(ref, rows, label):
    n = len(rows)
    w = sum(1 for r in rows if r["me"] > r["opp"])
    l = sum(1 for r in rows if r["me"] < r["opp"])
    t = n - w - l
    marg = [r["me"] - r["opp"] for r in rows]
    print(f"\n{'='*100}\n{label}  ref {ref}: {n} games  W/L/T {w}/{l}/{t}  win {100*w/n:.1f}%  "
          f"margin mean {st.mean(marg):+,.0f} median {st.median(marg):+,.0f}")
    q = st.quantiles(marg, n=10) if n >= 10 else []
    if q:
        print(f"  margin deciles: p10 {q[0]:+,.0f}  p25(approx) {st.quantiles(marg,n=4)[0]:+,.0f}  "
              f"p50 {st.median(marg):+,.0f}  p75 {st.quantiles(marg,n=4)[2]:+,.0f}  p90 {q[-1]:+,.0f}  "
              f"min {min(marg):+,.0f}  max {max(marg):+,.0f}")
    # ---- by opponent rating band
    print(f"\n  {'opp band':>12} {'n':>4} {'W-L-T':>9} {'win%':>6} {'margin mean':>12} {'margin med':>11} "
          f"{'my reward mean':>15}")
    by = collections.defaultdict(list)
    for r in rows:
        by[band(r["opp_score"])].append(r)
    order = [f"{lo}-{hi if hi < 10**9 else '+'}" for lo, hi in BANDS] + ["unknown"]
    for b in order:
        rs = by.get(b)
        if not rs:
            continue
        ww = sum(1 for r in rs if r["me"] > r["opp"])
        ll = sum(1 for r in rs if r["me"] < r["opp"])
        tt = len(rs) - ww - ll
        mm = [r["me"] - r["opp"] for r in rs]
        print(f"  {b:>12} {len(rs):>4} {f'{ww}-{ll}-{tt}':>9} {100*ww/len(rs):>5.1f}% "
              f"{st.mean(mm):>+12,.0f} {st.median(mm):>+11,.0f} "
              f"{st.mean([r['me'] for r in rs]):>15,.0f}")
    # ---- loss clustering
    losses = [r for r in rows if r["me"] < r["opp"]]
    print(f"\n  LOSS CLUSTERING ({len(losses)} losses = {100*len(losses)/n:.1f}% of games)")
    if losses:
        lb_by = collections.Counter(band(r["opp_score"]) for r in losses)
        print("    by opp rating band: " + "  ".join(f"{b}:{c}" for b, c in
              sorted(lb_by.items(), key=lambda kv: order.index(kv[0]))))
        print("    loss margin: mean {:+,.0f} median {:+,.0f} min {:+,.0f} max {:+,.0f}".format(
            st.mean([r["opp"] - r["me"] for r in losses]),
            st.median([r["opp"] - r["me"] for r in losses]),
            min(r["opp"] - r["me"] for r in losses),
            max(r["opp"] - r["me"] for r in losses)))
        # is the loss a collapse (our reward far below our norm) or a shootout?
        med_me = st.median([r["me"] for r in rows])
        low = [r for r in losses if r["me"] < med_me * 0.9]
        print(f"    our reward on losses: mean {st.mean([r['me'] for r in losses]):,.0f} "
              f"vs our median reward {med_me:,.0f}  ->  "
              f"{len(low)}/{len(losses)} losses at our reward < 90% of median (collapses), "
              f"{len(losses)-len(low)} at/above (out-scored)")
        cc = collections.Counter((r["opp_team"], r["opp_score"]) for r in losses)
        multi = [(k, v) for k, v in cc.most_common() if v > 1]
        print("    repeats among losses: " + (", ".join(f"{k[0]}({k[1]})x{v}" for k, v in multi) or "none"))
        print("    losses in order of margin (worst first):")
        for r in sorted(losses, key=lambda r: r["me"] - r["opp"])[:12]:
            print(f"      {r['time'][:16]}  me {r['me']:>8,.0f}  opp {r['opp']:>8,.0f}  "
                  f"{r['opp'] - r['me']:>+8,.0f}  {str(r['opp_team'])[:24]:24} rating {r['opp_score']} "
                  f"sub {r['opp_sub']}")
    # ---- time trend (quartiles of the run)
    if n >= 8:
        k = n // 4
        print("\n  time trend (4 equal chunks by time):")
        for i in range(4):
            chunk = rows[i*k:(i+1)*k] if i < 3 else rows[3*k:]
            ww = sum(1 for r in chunk if r["me"] > r["opp"])
            ll = sum(1 for r in chunk if r["me"] < r["opp"])
            print(f"    chunk {i+1} ({chunk[0]['time'][:16]} .. {chunk[-1]['time'][:16]})  "
                  f"n={len(chunk)} W-L {ww}-{ll} win {100*ww/len(chunk):.0f}%  "
                  f"margin mean {st.mean([r['me']-r['opp'] for r in chunk]):+,.0f}")
    return {"ref": ref, "label": label, "games": n, "wins": w, "losses": l, "ties": t,
            "win_rate": w / n, "margin_mean": st.mean(marg), "margin_median": st.median(marg),
            "by_band": {b: {"n": len(rs), "wins": sum(1 for r in rs if r["me"] > r["opp"]),
                            "losses": sum(1 for r in rs if r["me"] < r["opp"]),
                            "margin_mean": st.mean([r["me"] - r["opp"] for r in rs])}
                        for b, rs in by.items()},
            "rows": rows}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--refs", nargs="+", required=True)
    ap.add_argument("--labels", nargs="*", default=None)
    args = ap.parse_args()
    lb = {int(r["teamId"]): float(r["score"]) for r in json.loads(
        (ROOT / "data" / "leaderboard.json").read_text()) if r.get("score")}
    labels = args.labels or [str(r) for r in args.refs]
    out = {}
    for ref, label in zip(args.refs, labels):
        rows = rows_for(load(ref), ref, lb)
        out[str(ref)] = report(ref, rows, label)
    (ROOT / "data" / "ladder-mine.json").write_text(json.dumps(out, indent=1, default=str))
    print("\nwrote data/ladder-mine.json")
    # cross-ref: which opponents beat more than one of our refs
    beats = collections.defaultdict(set)
    for ref, d in out.items():
        for r in d["rows"]:
            if r["me"] < r["opp"]:
                beats[str(r["opp_team"])].add(d["label"])
    shared = {k: sorted(v) for k, v in beats.items() if len(v) > 1}
    print(f"\nopponents that beat more than one of our refs: {json.dumps(shared, indent=1)}")


if __name__ == "__main__":
    main()
