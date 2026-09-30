# Kaggriculture 2026-09 — 项目索引 / Project Index

> **这是本地唯一留存的文件。** 其余全部内容（约 20 GB）已提交到 git 并从本地删除。
> This is the only file kept locally. Everything else (~20 GB) was checked into git and deleted locally.
> 归档日期 / archived: **2026-09-30** · 比赛截止 / deadline: 2026-09-30 23:59 UTC

---

## 1. Git 位置（恢复入口）

| 项目 | 值 |
|---|---|
| 仓库 remote | `https://github.com/yinwun/kagriculture.git` |
| 分支 | `main` |
| **归档路径** | **`kaggriculture-2026-09/`** |
| **提交 commit** | **`e2dac3f27d4c2b606cdc50654004e6e51b983354`**（归档主体 `4ddbcdf` → `dc0dd9a` → `e2dac3f`） |
| 归档体积 | **11 MB / 517 个文件**（本地暂存与远端克隆已 `diff -rq` 逐文件校验一致） |

恢复：

```bash
git clone https://github.com/yinwun/kagriculture.git
cd kagriculture/kaggriculture-2026-09
cat reports/DESIGN-handbook.md        # 从这里开始读
```

> 备注：本机 `/usr/bin/git` 被 Xcode 许可协议挡住（`sudo xcodebuild -license` 未执行）。
> 可用的是直接调用真实二进制：`/Library/Developer/CommandLineTools/usr/bin/git`。

---

## 2. 归档内容清单

| 目录 | 内容 |
|---|---|
| `reports/` | **67 个 md**：`DESIGN-handbook.md`（设计与决策手册，入口）、`REPORT-pi-v78.md`（本轮主报告）、`REPORT-improve-to-2400.md`、`REPORT-frontier-3.md`/`-4.md` 等 60+ 份实验报告 |
| `scripts/` | **170 个脚本**：`lockstep.py`（引擎市场精确复刻）、`ab_duel.py`（配对对战，唯一有效评测仪器）、`t40/t41/t43_*.py`（构建与扫频）、`push_live.py`/`tg_inbox.py`（Telegram 推送与收信）、`submit.py` |
| `data/` | **127 项小数据**：`cmp-track.csv`（分数时间序列）、`leaderboard.json`、`tg-inbox.jsonl`（用户 Telegram 消息）、各次对战/扫频结果 JSON |
| `log/` | **136 个实验日志**（含 `push_live.log` 的完整推送历史） |
| `pkg/` | 早期 `submission-v109.tar.gz` 及其解包 `v109_extract/main.py`（任务起点的参照提交） |
| `misc-md/` | 零星 md：`REPORT.md`、`2026-08-10_session_log.md` |
| `README.md` | 即本索引文件 |

> **注意**：本仓库的 `.gitignore` 会排除 `log/`、`*.tar.gz`、`__pycache__`。
> 上述文件是用 `git add -f` **强制加入**的——若日后有人重建归档，必须同样强制添加，否则 `log/` 与 `pkg/` 会静默丢失（本次已实际发生过一次，靠克隆校验才发现）。

**未归档（体积过大或含密钥，均可重新生成或从 Kaggle 下载）：**

- `data/replays*`（约 15 GB，Kaggle 原始 replay）
- `episode-*-replay.json`（顶层，约 800 MB）
- **`data/telegram.json` — 含 Telegram bot token，安全考虑不提交**
- `.venv/`、构建产物 `data/candidate/*/main.py`（每个约 1.2 MB）

---

## 3. 比赛结果

```
最终  2041.0 分   名次 623/10,208   前 6.10%
峰值  2221.4      （2026-09-29 17:54 UTC，名次 452）
分位线  前1% 2530  |  前5% 2102  |  前10% 1864
```

| ref | 提交时间 | 最终分 | 构建 |
|---|---|---|---|
| **56642424** | 09-28 13:37 | **2041.0** ← 扛分线 | `pi_stack`：V78 公共底座 + 我们的市场层 |
| 56657816 | 09-29 00:54 | 1977.8 | `pi_stack` 副本（保险第二抽） |
| 56627381 | 09-28 03:14 | 1770.5 | 旧 shepherds 底座基线 |
| 56627360 | 09-28 03:13 | 1761.1 | 旧底座 cap24 |

**起点对比**：09-28 早间为 1,842 分 / 名次约 1,620。本轮净提升 **约 +200 分、名次前进约 1,000 名**。

---

## 4. 核心技术结论（供日后复用）

### 4.1 采纳了更强的公共底座（本轮最大收获）

- 扫 12 个候选，唯一清关的是 `leoprovorov/3141592…4197169399`「**Kaggriculture V78 Master Engine**」
- 它比我们原底座每局多 **+1,142 币**（p1 +1,142 t=8.78 60–0；p2 +1,071 t=6.28 56–4）
- 叠上我们的市场层得到 **`pi_stack`**：比原冠军 **+1,666 币/局 ≈ +1.7% 钱包**
  - p1 +1,612（t=+8.91，60–0）／p2 +1,720（t=+8.29，58–2）
  - 分解：底座 +1,109（t=+8.65），我们的层再 **+593**（t=+10.86）
- 构建：`scripts/t40_stack.py`；sha256 `65962e928b071294…`；单步耗时 max 161 ms（`actTimeout` 1 s），**无超时风险**

### 4.2 所有杠杆均已测完并关闭

| 杠杆 | 结论 |
|---|---|
| 我们的层栈（race 卖位搜索 / wool·草莓·牛奶 sell-forward / `forward_drain_mult`） | ✅ 已确认最优：**24.0**（1/2/8/12 更差，48 略差） |
| 底座常数 `_CA_MARGIN` | ✅ 已确认最优：**−22.0**（公开"V79"的 −15 是**退步** −61 t=−3.23） |
| 更新的公共引擎 | ✅ **不存在**（608 竞赛 notebook + 764 场外 kernel，2880 局 duel） |
| 不同的路线数据 | ✅ **不存在**（全部解码回 `54fe156ea7206e38`） |
| 2,400 分 | ❌ **本架构不可达**（见 4.4） |

### 4.3 排名下滑的真正机制（重要）

分数**在提交后 12–28 小时见顶，之后随"线龄"单调衰减**：

| 线龄 | 平均分 |
|---|---|
| ~12–18 h | **2,120–2,158**（峰值） |
| ~30 h | 1,969 |
| ~48 h | 1,887 |
| ~60 h | 1,782 |

实测 550 局：对手比我**晚**提交时我们胜率 **41.8%**（对手均分 2,103）；比我**早**时胜率 **80.3%**（均分 1,781）。
**由于整个前沿跑的是同一份代码，这 300+ 分主要是提交时间的相位差，而非能力差距。**
→ 实践含义：想让分数高，应让跟踪对在截止时刻处于"冲高段"（提交后 12–18 小时），而不是衰减段。

### 4.4 为什么 2,400 不可达（Task 42 的封闭账目）

- 需要胜率从 85% 提到 **96.1%**（91 局里赢 87.4 局）= 每局多赚 **+2,860…+3,306 币**
- 而我们整个市场层栈只值 **+593**——**需要它的 4.8 倍**
- 输的钱在**生产**不在市场：**EGG −1,368 + WHEAT −1,367 = 败局差额的 103%**
- 我们的市场层**即使在败局里也是净正**（WOOL +567、MILK +325）
- 归因方法可信：91/91 replay 复现到美元，渠道账**残差 0.0000**

### 4.5 已证伪 / 不要重试

延迟与价格地板 · 卖投入品（小麦/肥料）· 胡萝卜/番茄/蛋的晚售层 · 羊群替换 · 羊只天数/回合编辑 · 路线重选 · 对手布局预测 · 健壮决策规则 · 从零规划器 plan_v0（0/400 胜）· "多卖"族（边际只值 **0.73 币/单位**）。

---

## 5. 方法论纪律（本轮反复验证有效）

1. **配对对战（`ab_duel.py`，轮换座位）是唯一有效的决策仪器**；对 `starter` 或弱底座调参无效。
2. **不同参数产生逐字节相同的行为 = bug 信号，不是"死旋钮"。**
3. **对照实验必须精确为 0**：重建冠军自身的参数应得到**逐字节相同的 sha 且 Δ 恰好 +0.0**（本轮两次通过）。
4. **换人换面板测出同一个数**才算可信（公开 −15 回滚：我们的扫描 −64.2，独立扫描 −61）。
5. **不要在机器满载时读性能数字**——曾把 836 ms 误判为超时风险，空载复测只有 161 ms。
6. **天梯只跟踪最新 2 个提交**；新提交顶掉**较旧**的那条。投之前必须确认被顶掉的不是扛分线（本轮已验证：56642424 局数 102→103 继续增长）。
7. **自对局钱包不能作为强度证据**（`bronze-going-up` 自对局 151,289 看似很高，实战胜我们 −1,035）。

---

## 6. Telegram 双向通道（已停用）

- bot `@nickylyjbot`；推送 `scripts/push_live.py`（每 25 分钟），收信 `scripts/tg_inbox.py`（长轮询 + 自动应答状态查询）
- **已删除 crontab 定时任务并停止所有后台进程**
- 教训：只做"收信落盘"不够——agent 不是常驻进程，**必须有能唤醒/自动应答的机制**，否则用户发的消息没人读
- 用户经 Telegram 发过 8 条消息，全部记录在归档的 `data/tg-inbox.jsonl`

---

## 7. 后续如需重启

```bash
git clone https://github.com/yinwun/kagriculture.git && cd kagriculture/kaggriculture-2026-09
python -m venv .venv && .venv/bin/pip install kaggle-environments==1.32.7 kaggle
# 引擎版本必须 1.32.7：容器里的 1.29.3 会给出错误的对局结果
.venv/bin/python scripts/ab_duel.py --cand <A>/main.py --base <B>/main.py --seeds <全新面板>
```

**关键环境事实**：`market_price(item, inventory)` 是**仅由库存决定的纯函数**；`_town_consume` 在 `step % 4 == 0` 抽干商店；成交是**逐槽/逐单位 lockstep**，双方看到同一成交前报价；`max_orders=10`；`actTimeout=1s`；observation 的 `market` **只有 `inventory` 和 `prices`，没有 `params`**（市场常数必须硬编码）。
