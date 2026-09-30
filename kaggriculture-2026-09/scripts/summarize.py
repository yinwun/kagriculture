#!/usr/bin/env python
"""Aggregate nickyl's kaggriculture submission + episode record into win/loss stats.

Reads:
  data/submissions.csv     (from `kaggle competitions submissions -c kaggriculture --csv`)
  data/episodes/<id>.json  (from scripts/fetch_episodes.py)
Writes:
  data/summary.json
  data/episodes.csv
"""
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TEAM = "nickyl"


def load_episodes():
    out = []
    for path in sorted((ROOT / "data" / "episodes").glob("*.json")):
        for ep in json.loads(path.read_text()):
            ep["_submission"] = int(path.stem)
            out.append(ep)
    # an episode can be listed under both of my submissions if I played myself
    dedup = {}
    for ep in out:
        dedup.setdefault(ep["id"], ep)
    return out, list(dedup.values())


def outcome(ep, submission_id):
    """Return (result, my_reward, opp_reward, opponent, opp_submission) or None."""
    agents = ep.get("agents") or []
    if len(agents) != 2:
        return None
    mine = [a for a in agents if a.get("teamName") == TEAM or a.get("submissionId") == submission_id]
    if not mine:
        return None
    me = max(mine, key=lambda a: a.get("submissionId") == submission_id)
    others = [a for a in agents if a is not me]
    if not others:
        return None
    opp = others[0]
    if me.get("reward") is None or opp.get("reward") is None:
        return None
    if me["reward"] > opp["reward"]:
        res = "win"
    elif me["reward"] < opp["reward"]:
        res = "loss"
    else:
        res = "tie"
    return res, me["reward"], opp["reward"], opp.get("teamName"), opp.get("submissionId")


def main():
    rows = list(csv.DictReader(open(ROOT / "data" / "submissions.csv")))
    all_eps, unique_eps = load_episodes()

    per_sub = {}
    detail = []
    for row in rows:
        sid = int(row["ref"])
        if not row["status"].endswith("COMPLETE"):
            per_sub[sid] = {"status": "ERROR"}
            continue
        eps = [e for e in all_eps if e["_submission"] == sid]
        counter = Counter()
        rewards = []
        for ep in eps:
            got = outcome(ep, sid)
            if got is None:
                counter["unscored"] += 1
                continue
            res, my_r, opp_r, opp_name, opp_sid = got
            counter[res] += 1
            rewards.append(my_r)
            detail.append(
                {
                    "episode_id": ep["id"],
                    "submission": sid,
                    "file": row["fileName"],
                    "date": row["date"],
                    "public_score": row["publicScore"],
                    "result": res,
                    "my_reward": my_r,
                    "opp_reward": opp_r,
                    "opponent": opp_name,
                    "opp_submission": opp_sid,
                    "state": ep.get("state"),
                    "type": ep.get("type"),
                    "end_time": ep.get("endTime"),
                }
            )
        per_sub[sid] = {
            "status": "COMPLETE",
            "file": row["fileName"],
            "date": row["date"],
            "public_score": row["publicScore"],
            "episodes": len(eps),
            "wins": counter["win"],
            "losses": counter["loss"],
            "ties": counter["tie"],
            "unscored": counter["unscored"],
            "win_rate": round(counter["win"] / max(1, counter["win"] + counter["loss"] + counter["tie"]), 4),
            "avg_reward": round(sum(rewards) / len(rewards), 1) if rewards else None,
        }

    # Validation episodes are self-play (both agents are my own bot), so they are not
    # ladder games and must not pollute the win/loss record.
    validation = [d for d in detail if d["type"] == "EPISODE_TYPE_VALIDATION"]
    ladder = [d for d in detail if d["type"] != "EPISODE_TYPE_VALIDATION"]
    counts = Counter(d["result"] for d in ladder)
    vcounts = Counter(d["result"] for d in validation)

    by_day = defaultdict(Counter)
    for d in ladder:
        by_day[d["end_time"][:10]][d["result"]] += 1

    summary = {
        "team": TEAM,
        "submissions_total": len(rows),
        "submissions_complete": sum(1 for r in rows if r["status"].endswith("COMPLETE")),
        "submissions_error": sum(1 for r in rows if r["status"].endswith("ERROR")),
        "submissions_with_episodes": sum(1 for v in per_sub.values() if v.get("episodes")),
        "episode_records_all": len(detail),
        "episode_records_unique": len({d["episode_id"] for d in detail}),
        "ladder_episodes": len(ladder),
        "validation_episodes": len(validation),
        "validation_wins": vcounts["win"],
        "validation_losses": vcounts["loss"],
        "validation_ties": vcounts["tie"],
        "wins": counts["win"],
        "losses": counts["loss"],
        "ties": counts["tie"],
        "win_rate_incl_ties": round(counts["win"] / max(1, len(ladder)), 4),
        "win_rate_excl_ties": round(counts["win"] / max(1, counts["win"] + counts["loss"]), 4),
        "episodes_vs_self": sum(1 for d in ladder if d["opponent"] == TEAM),
        "unique_opponents": len({d["opponent"] for d in ladder if d["opponent"] != TEAM}),
        "first_submission": min(r["date"] for r in rows),
        "last_submission": max(r["date"] for r in rows),
        "daily": {
            day: {"n": sum(c.values()), **{k: c[k] for k in ("win", "loss", "tie")}}
            for day, c in sorted(by_day.items())
        },
    }
    (ROOT / "data" / "summary.json").write_text(json.dumps({"summary": summary, "per_submission": per_sub}, indent=1))

    with open(ROOT / "data" / "episodes.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(detail[0].keys()))
        w.writeheader()
        w.writerows(detail)

    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
