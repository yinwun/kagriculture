#!/usr/bin/env python
"""Push the live kaggriculture ladder state to Telegram.

Runs from crontab every 30 minutes, independent of any chat session:
  */30 * * * * cd /path/to/kg-rl && .venv/bin/python scripts/push_live.py >> log/push_live.log 2>&1

It reports the two numbers that decide the final pair:
  * our score / rank / distance to the top-1|5|10 % cutoffs, and
  * for each of our recent submission lines: score, games, win %, mean opponent
    score, and the win rate in the 2200-2500 opponent band (the band where the
    drain-mult builds and shep_straw disagree, so its sample size is what settles
    whether the drain-mult chain survives on the ladder).

Config: data/telegram.json  {"token": "123:ABC", "chat_id": 123456}
`chat_id` is resolved automatically from getUpdates the first time (send the bot
any message first) and cached back into the file.
"""
import json
import statistics as st
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CFG = ROOT / "data" / "telegram.json"
STATE = ROOT / "data" / "push-state.json"
CSV = ROOT / "data" / "cmp-track.csv"
STATUS = ROOT / "data" / "live-status.md"

# description keyword -> label, MOST SPECIFIC FIRST.  Keys MUST be lowercase: the caller
# lowercases the description before matching (that is why the uppercase "x24" once matched
# ARM B's "... x1-vs-x24 ..." and relabelled shep_straw as cap24).
LABELS = [("pi-v78 dup", "pi_stack2"),        # 2nd instance of the same build (insurance draw)
          ("pi-v78", "pi_stack"),            # 56642424 - frontier V78 base + our layers (current best)
          ("final arm a", "cap24"),          # 56627360 - drain multiplier x24 arm
          ("final arm b", "shep_straw"),     # 56627381 - x1 baseline arm
          ("x8", "cap8"), ("x2", "cap2"),
          ("strongest measured build", "shep_straw"), ("tracked-pair reset", "shep_straw"),
          ("four-layer", "shep_milk"), ("shep_milk", "shep_milk")]
BAND_LO, BAND_HI = 2200.0, 2500.0


def tg(method, token, **kw):
    url = f"https://api.telegram.org/bot{token}/{method}"
    data = urllib.parse.urlencode(kw).encode() if kw else None
    req = urllib.request.Request(url, data=data)
    with urllib.request.urlopen(req, timeout=25) as r:
        return json.load(r)


def load_cfg():
    cfg = json.loads(CFG.read_text()) if CFG.exists() else {}
    if not cfg.get("chat_id") and cfg.get("token"):
        ups = tg("getUpdates", cfg["token"])
        for u in ups.get("result", []):
            for k in ("message", "edited_message", "channel_post"):
                chat = (u.get(k) or {}).get("chat") or {}
                if chat.get("id"):
                    cfg["chat_id"] = chat["id"]
                    cfg["chat_name"] = chat.get("first_name") or chat.get("title") or ""
                    CFG.write_text(json.dumps(cfg, indent=1))
                    break
            if cfg.get("chat_id"):
                break
    return cfg


def api():
    from kaggle.api.kaggle_api_extended import KaggleApi
    for _ in range(6):
        try:
            a = KaggleApi()
            a.authenticate()
            return a
        except Exception:
            time.sleep(4)
    raise SystemExit("kaggle auth failed")


def collect():
    api_ = api()
    board = json.loads((ROOT / "data" / "leaderboard.json").read_text())
    board = [r for r in board if r.get("score")]
    ranked = sorted(board, key=lambda r: -float(r["score"]))
    scores = sorted((float(r["score"]) for r in ranked), reverse=True)
    n = len(scores)
    me = next((r for r in ranked if r.get("teamName") == "nickyl"), None)
    lb = {e["teamId"]: float(e["score"]) for e in json.loads((ROOT / "data" / "leaderboard.json").read_text())
          if e.get("score")}
    cut = {p: scores[int(p * n)] for p in (0.01, 0.05, 0.10)}

    subs = [s.to_dict() for s in api_.competition_submissions("kaggriculture")][:6]
    lines = []
    for d in subs:
        desc = (d.get("description") or "").lower()
        label = next((lab for key, lab in LABELS if key in desc), None)
        if not label:
            continue
        ref = d.get("ref")
        rec = []  # (endTime, win, opp_score)
        try:
            eps = [e.to_dict() for e in api_.competition_list_episodes(ref)]
        except Exception:
            eps = []
        for ep in eps:
            if ep.get("type") != "EPISODE_TYPE_PUBLIC":
                continue
            ags = ep.get("agents") or []
            if len(ags) != 2:
                continue
            m = [x for x in ags if x.get("submissionId") == ref]
            if not m:
                continue
            m = m[0]
            o = [x for x in ags if x is not m][0]
            if m.get("reward") is None or o.get("reward") is None:
                continue
            rec.append((str(ep.get("endTime")), m["reward"] > o["reward"], lb.get(o.get("teamId"))))
        rec.sort()
        n_g = len(rec)
        wins = sum(1 for _, w, _ in rec if w)
        opps = [sc for _, _, sc in rec if sc]
        band = [(sc, w) for _, w, sc in rec if sc and BAND_LO <= sc < BAND_HI]
        def wrate(k):
            tail = rec[-k:] if k else rec
            if not tail:
                return (0, 0.0, 0.0)
            ww = sum(1 for _, w, _ in tail if w)
            oo = [sc for _, _, sc in tail if sc]
            return (len(tail), 100*ww/len(tail), st.mean(oo) if oo else 0.0)
        g10, wr10, opp10 = wrate(10)
        g20, wr20, opp20 = wrate(20)
        lines.append({
            "label": label, "ref": ref, "score": d.get("publicScore"),
            "games": n_g, "wins": wins,
            "win_pct": (100 * wins / n_g) if n_g else 0,
            "opp_mean": st.mean(opps) if opps else 0,
            "band_games": len(band), "band_wins": sum(1 for _, w in band if w),
            "band_pct": (100 * sum(1 for _, w in band if w) / len(band)) if band else 0,
            "wr10": wr10, "wr20": wr20, "opp20": opp20,
        })
    # keep the newest submission per label
    dedup = {}
    for row in lines:
        dedup.setdefault(row["label"], row)
    return {
        "utc": datetime.now(timezone.utc).strftime("%m-%d %H:%M"),
        "me": float(me["score"]) if me else None,
        "rank": (ranked.index(me) + 1) if me else None,
        "total": n, "cut": cut, "lines": list(dedup.values()),
    }


def render(d):
    try:
        prev = json.loads(STATE.read_text()) if STATE.exists() else {}
    except Exception:
        prev = {}
    move = ""
    if prev.get("me") is not None and d["me"] is not None and abs(d["me"] - prev["me"]) >= 50:
        move = f" ⚠️{'+' if d['me']>prev['me'] else ''}{d['me']-prev['me']:.0f}"
    out = [f"[KG] {d['utc']} UTC"]
    if d["me"]:
        out.append(f"me {d['me']:.1f} rank {d['rank']}/{d['total']}{move} | "
                   f"d1% {d['me']-d['cut'][0.01]:+.0f} d5% {d['me']-d['cut'][0.05]:+.0f} "
                   f"d10% {d['me']-d['cut'][0.10]:+.0f}")
    out.append(f"cut 1% {d['cut'][0.01]:.0f} 5% {d['cut'][0.05]:.0f} 10% {d['cut'][0.10]:.0f}")
    out.append("-- lines (wr10/wr20 = last-10/20 win%, d = change vs prev sample) --")
    prevlines = {x.get("label"): x for x in (prev.get("lines") or [])}
    for L in sorted(d["lines"], key=lambda x: -(float(x["score"] or 0))):
        pl = prevlines.get(L["label"]) or {}
        d20 = (L["wr20"] - pl["wr20"]) if (pl.get("wr20") is not None and L.get("wr20") is not None) else 0.0
        d10 = (L["wr10"] - pl["wr10"]) if (pl.get("wr10") is not None and L.get("wr10") is not None) else 0.0
        arrow = "up" if d20 > 3 else ("DOWN" if d20 < -3 else "flat")
        # a just-submitted instance has no score yet: render it as NEW instead of crashing
        if L.get("score") is None or L.get("wr20") is None:
            out.append(f"{L['label']:10s} {'NEW':>7} {L.get('games') or 0:>4}g "
                       f"(awaiting first episodes) ref={L.get('ref')}")
            continue
        out.append(f"{L['label']:10s} {L['score']:>7} {L['games']:>4}g "
                   f"wr20 {L['wr20']:>3.0f}%({d20:+.0f}) wr10 {L['wr10']:>3.0f}%({d10:+.0f}) "
                   f"opp20 {L['opp20']:>5.0f} [{arrow}]")
    no = not any(L["band_games"] >= 20 for L in d["lines"])
    out.append(f"verdict: 2200+ band samples {'<20 -> UNDECIDED' if no else '>=20 -> compare'}")
    return "\n".join(out), d


def main():
    cfg = load_cfg()
    if not cfg.get("token") or not cfg.get("chat_id"):
        raise SystemExit("telegram.json needs token + chat_id (send the bot a message first)")
    # refresh the leaderboard snapshot first, otherwise the push reports a stale board
    import subprocess
    try:
        subprocess.run([sys.executable, str(ROOT / "scripts" / "fetch_leaderboard.py")],
                       capture_output=True, timeout=240)
    except Exception as exc:  # noqa: BLE001
        print(f"leaderboard refresh failed: {type(exc).__name__}", file=sys.stderr)
    import os
    prev_ts = 0.0
    if STATE.exists():
        try:
            prev_ts = float(json.loads(STATE.read_text()).get("ts") or 0)
        except Exception:
            prev_ts = 0.0
    if not os.environ.get("PUSH_FORCE") and prev_ts and (time.time() - prev_ts) < 1500:
        print("skip: last push < 25 min ago")
        return 0
    d = collect()
    text, d = render(d)
    tg("sendMessage", cfg["token"], chat_id=cfg["chat_id"], text=text)
    STATE.write_text(json.dumps({"me": d["me"], "rank": d["rank"], "utc": d["utc"],
                                 "ts": time.time(), "lines": d["lines"]}))
    wr = ROOT / "data" / "wr-track.csv"
    if not wr.exists():
        wr.write_text("utc,label,score,games,wr10,wr20,opp20\n")
    with wr.open("a") as fh:
        for L in d["lines"]:
            fh.write(f"{d['utc']},{L['label']},{L['score']},{L['games']},"
                     f"{L['wr10']:.1f},{L['wr20']:.1f},{L['opp20']:.0f}\n")
    STATUS.write_text("```\n" + text + "\n```\n")
    row = f"{datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M')},{d['me']:.1f},{d['rank']},{d['total']}," \
          f"{d['cut'][0.01]:.0f},{d['cut'][0.05]:.0f},{d['cut'][0.10]:.0f}"
    with CSV.open("a") as fh:
        fh.write(row + "\n")
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
