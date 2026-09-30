# v109 到顶诊断 + 优化方案

生成: 2026-09-12 14:00 | 引擎校验: 天梯 `module_version=1.32.7` == 本地 `kaggle-environments 1.32.7`,
配置 15 项逐项一致 ⇒ **本地对局与天梯引擎级等价**。

## 1. 诊断:v109 已到顶(不是局数问题)

| 时间 (UTC) | v109 分数 |
| --- | --- |
| 09-11 12:20 提交 → 09-12 04:20 | 2160.7 |
| 09-12 04:51 | 2176.9 |
| 09-12 05:32 | 2180.6 |

分数还在涨,但**速率在衰减**。更关键的是最近 20 局质量崩塌:

| 局面区间 | 胜率 | 对手均分 | 平均分差 |
| --- | --- | --- | --- |
| 61-80 | 85% | 2,075 | +5,721 |
| 81-100 | 90% | 2,130 | +5,708 |
| 101-120 | 90% | 2,290 | +6,435 |
| **121-140** | **60%** | **2,172**(停滞) | **+573** |

对手质量不再上升 = 匹配系统认为它就值这个分。近 80 局分档:

- 对 ≥2600: **2胜7负 (28.6%)**
- 对 2400-2600: 6胜2负
- 对 2200-2400: 8胜4负
- 对 2000-2200: 30胜2负 (91%)
- 对 <2000: 95%

**结论:天花板约 2200-2300,离 2500 差 200-300 分,靠继续跑追不回来。**

## 2. 根因:代码在同族里落后

v109 = 公开 `herd-safe-2700` + 20 行改动,磁带 (`actions.json`) 与 0909 家族**逐字节相同**。
而公开生态从 09-09 到 09-12 一直在迭代 router 规则。

本地 10-agent 联赛(每 agent 54 局,同种子确定性):

| agent | 胜率 | 平均金币 | 对 v109 |
| --- | --- | --- | --- |
| **v37** (今天最新) | **94.4%** | 115,762 | **20:0** |
| v36-guarded | 81.5% | 114,787 | 29:1 |
| 0911-simple (yhay81) | 64.8% | 111,686 | 63:37 |
| **v109 (你的)** | **53.7%** | 101,780 | — |
| herd-safe-2700 (v109 母版) | 53.7% | 101,829 | 50:50 |
| prvsiyan | 37.0% | 101,136 | v109 100:0 |
| 0909-base | 18.5% | 84,228 | v109 100:0 |
| aurax7-reactive | 14.8% | 88,494 | v109 100:0 |
| nusrati | 0.0% | 83,764 | v109 100:0 |

**独立验证收获**:V37 相对 V36 只多了一个 "finite-harvest wheat/carrot input planner",
作者在 notebook 里写 *"New independent confirmation is required"* —— 我们实测
**V37 vs V36 = 18:1**,确认这个改动有效。

## 3. 方案:两个槽位一起换

现状槽位(最新 2 个):

| 顺序 | submission | 提交时间 | 分数 | 状态 |
| --- | --- | --- | --- | --- |
| 最新 | v94-final | 09-11 14:23 | 1837.5 | 躺平 |
| 第 2 | **v109** | 09-11 12:20 | 2180.6 | 到顶 |

⚠️ 因为 v94-final 比 v109 更新,**提交任何新包都会先踢掉 v109**,躺平的 v94-final 反而留下。
所以要提交 **2 次**才能把两个槽位都换成强 agent:

1. `kaggle competitions submit kaggriculture -f submission_competitive_v37.tar.gz -m "v37"`
   → 槽位变成 {v37, v94-final},v109 被踢
2. `kaggle competitions submit kaggriculture -f submission.tar.gz -m "0911-simple"`
   → 槽位变成 {0911, v37},v94-final 被踢

结果:两个槽位都是本地压制 v109 的新 agent,且 0911 的作者用同族代码稳定在 **2745**。

## 4. 之后的持续优化循环

- **筛选器**:本地联赛 2.3 秒/局(`scripts/league.py`),天梯 5 次/天 是预算
- **显著性要求**:至少 30 局。实测 10 局会翻转 —— V36 vs 0911 在 10 局是 6:4(像 V36 赢),
  30 局是 12:30(实际 0911 赢)
- **下一步优化点**(按证据强度):
  1. 扩展 V37 的 finite-harvest input planner(已验证 +)
  2. 终局卖出窗口(你 V108 那条线)做参数扫描,别再拍脑袋
  3. nusrati 式"公开特征学习路由"(它的 model.json 是决策树,在 step 144/648 选磁带)
  4. 磁带本身 —— 整个公开家族共用同一份,这是**共同天花板**(yhay81 现实上限 ~2745),
     想突破需要新磁带

## 5. 已验证的前提(可复现)

```bash
# 引擎/配置一致性
.venv/bin/python -c "import kaggle_environments;print(kaggle_environments.__version__)"   # 1.32.7
# 自包含性:两个包解出后只有 main.py,本地跑 status=DONE,1.5s/局,~185k vs starter
tar -tzf data/league/more-yield/submission_competitive_v37.tar.gz   # main.py
tar -tzf data/nb_0911_build/submission.tar.gz                       # main.py
```

产物:`data/league_full.json`(联赛矩阵)、`data/league_baseline.json`、
`scripts/league.py`、`scripts/ab_isolated.py`(进程隔离版 A/B)。
