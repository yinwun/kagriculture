#!/usr/bin/env python
"""Render data/summary.json + data/submissions.csv into REPORT.md."""
import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
data = json.loads((ROOT / "data" / "summary.json").read_text())
s = data["summary"]
per = data["per_submission"]
rows = list(csv.DictReader(open(ROOT / "data" / "submissions.csv")))

by_id = {int(r["ref"]): r for r in rows}
ladder_wr = f"{s['win_rate_incl_ties'] * 100:.2f}%"
decisive_wr = f"{s['win_rate_excl_ties'] * 100:.2f}%"

complete = sorted(
    [(k, v) for k, v in per.items() if v.get("status") == "COMPLETE"],
    key=lambda kv: kv[1]["date"],
    reverse=True,
)

lines = []
A = lines.append
A("# Kaggriculture 提交与战绩报告")
A("")
A(f"- 队伍: `{s['team']}` | 生成时间: 本地抓取自 Kaggle API")
A(f"- 提交窗口: {s['first_submission'][:16]} → {s['last_submission'][:16]}")
A("")
A("## 1. 提交次数")
A("")
A(f"| 指标 | 数值 |")
A(f"| --- | --- |")
A(f"| 总提交次数 | **{s['submissions_total']}** |")
A(f"| 成功 (COMPLETE, 有分数) | **{s['submissions_complete']}** |")
A(f"| 失败 (ERROR, 验证局跑挂) | **{s['submissions_error']}** |")
A(f"| 提交成功率 | {s['submissions_complete'] / s['submissions_total'] * 100:.1f}% |")
A("")
A("## 2. 对局胜负 (ladder episodes)")
A("")
A("| 指标 | 数值 |")
A("| --- | --- |")
A(f"| 排位对局总数 | **{s['ladder_episodes']}** |")
A(f"| 胜利 | **{s['wins']}** |")
A(f"| 失败 | **{s['losses']}** |")
A(f"| 平局 | **{s['ties']}** |")
A(f"| 胜率 (含平局) | **{ladder_wr}** |")
A(f"| 胜率 (仅决胜局, 不含平局) | **{decisive_wr}** |")
A(f"| 不同对手数 | {s['unique_opponents']} |")
A(f"| 验证局 (自我对局, 不计入胜负) | {s['validation_episodes']} "
  f"(W{s['validation_wins']}/L{s['validation_losses']}/T{s['validation_ties']}) |")
A("")
A("## 3. 每日战绩 (最近 14 天)")
A("")
A("| 日期 | 对局 | 胜 | 负 | 平 | 胜率 |")
A("| --- | --- | --- | --- | --- | --- |")
for day, c in list(s["daily"].items())[-14:]:
    wr = c["win"] / c["n"] * 100 if c["n"] else 0
    A(f"| {day} | {c['n']} | {c['win']} | {c['loss']} | {c['tie']} | {wr:.1f}% |")
A("")
A("## 4. 各次提交明细 (最新在前)")
A("")
A("| submission_id | 文件 | 时间 | public score | 对局 | 胜 | 负 | 平 | 胜率 |")
A("| --- | --- | --- | --- | --- | --- | --- | --- | --- |")
for k, v in complete:
    A(
        f"| {k} | {v['file']} | {v['date'][:16]} | {v['public_score']} | {v['episodes']} | "
        f"{v['wins']} | {v['losses']} | {v['ties']} | {v['win_rate'] * 100:.1f}% |"
    )
A("")
A("## 5. 失败的提交 (ERROR)")
A("")
A("| submission_id | 文件 | 时间 |")
A("| --- | --- | --- |")
for r in rows:
    if r["status"].endswith("ERROR"):
        A(f"| {r['ref']} | {r['fileName']} | {r['date'][:16]} |")
A("")
A("## 6. 当前生效的提交 (只有最新 2 个被追踪/计入最终榜)")
A("")
for k, v in complete[:2]:
    A(f"- `{k}` {v['file']} — score {v['public_score']}, 对局 {v['episodes']}, "
      f"胜率 {v['win_rate'] * 100:.1f}%")
A("")
A("## 7. 排行榜位置")
A("")
rank = None
try:
    import time

    from kaggle.api.kaggle_api_extended import KaggleApi

    api = KaggleApi()
    for attempt in range(1, 7):
        try:
            api.authenticate()
            resp = api.competitions_list(search="kaggriculture")
            break
        except Exception:  # noqa: BLE001 - flaky API/proxy resets
            if attempt == 6:
                raise
            time.sleep(3 * attempt)
    for entry in getattr(resp, "competitions", None) or []:
        d = entry.to_dict() if hasattr(entry, "to_dict") else dict(entry)
        if "kaggriculture" in str(d.get("ref", "")):
            rank = d
            break
except Exception as exc:  # noqa: BLE001 - report still renders without rank
    A(f"(排行榜查询失败: {type(exc).__name__}: {exc})")
    A("")
if rank:
    A(f"- 队伍排名: **{rank.get('userRank')}** / {rank.get('teamCount')} 支队伍")
    A(f"- 已加入比赛: {rank.get('userHasEntered')} | 截止: {rank.get('deadline')}")
    A("")
best = max(complete, key=lambda kv: float(kv[1]["public_score"]))
A(f"历史最佳 public score: **{best[1]['public_score']}** (`{best[0]}` {best[1]['file']}, {best[1]['date'][:16]})")
A("")
A("## 数据来源 / 复现")
A("")
A("- `kaggle competitions submissions -c kaggriculture --csv` → `data/submissions.csv`")
A("- `kaggle competitions episodes <submission_id>` → `data/episodes/<id>.json`")
A("- 胜负判定: 同一 episode 内 `agents[].reward`(赛季结束时的金币)对比, 多者为胜, 相等为平")
A("- 汇总脚本: `scripts/fetch_episodes.py` → `scripts/summarize.py` → 本报告")

(ROOT / "REPORT.md").write_text("\n".join(lines) + "\n")
print("\n".join(lines[:20]))
print("...")
print("written REPORT.md")
