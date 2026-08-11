# CODEX — Kagriculture 项目知识库

> 本文件是 Codex 的项目知识库，包含本地/远程环境配置、编码工作流、提交规范等核心信息。
> **每次对话开始时应优先阅读此文件。**

---

# 环境总览

| 环境 | 主机 | 工作目录 | 主要职责 |
|------|------|---------|---------|
| **本地** | Mac 本机 | `/Users/nickyl/Developer/Sandbox/kagriculture/` | 代码开发、提交 Kaggle、文档编辑 |
| **远程** | `nlv100` (192.168.1.101) | `/data/app/sandbox/kaggle/kg-rl/` | 模型训练、生成评估报告 |

---

# 本地环境

## Conda 环境

| 属性 | 值 |
|------|-----|
| 环境名 | `kaggle` |
| 激活命令 | `source /opt/anaconda3/etc/profile.d/conda.sh && conda activate kaggle` |

> ⚠️ 激活后 `kaggle` CLI 才在 PATH 中可用。

## Kaggle API Token

| 属性 | 值 |
|------|-----|
| 配置文件 | `~/.kaggle/kaggle.json` |
| 格式 | `{"username":"nickyl","key":"KGAT_xxx"}` |
| Token 来源 | `~/.kaggle/access_token`（格式：`KGAT_xxx`） |

## 本地目录结构

```
/Users/nickyl/Developer/Sandbox/kagriculture/
├── CODEX.md                        # 本文件
├── docs/                           # 文档（本地编辑）
│   ├── replay-download-guide.md    # Replay 下载指南
│   └── WORKFLOW.md                 # 编码工作流规范
├── pkg/                            # 提交包（从远程复制至此）
├── log-session/                    # Session 日志（本地追加）
└── eval_reports/                  # 评估报告（从远程同步）
```

## 本地 Session 日志

| 属性 | 值 |
|------|-----|
| 路径 | `/Users/nickyl/Developer/Sandbox/kagriculture/log-session/` |
| 内容格式 | `yyyy-mm-dd hhMMss : content` |
| 文件名格式 | `2026-08-10-session-log.md` |
| 写入规则 | 每天一个文件，内容追加 |

## 本地操作清单

| 操作 | 是否在本地执行 | 说明 |
|------|:------------:|------|
| 代码开发 / 修改 | ✅ | 在本地进行 |
| Kaggle 提交 | ✅ | **只能在本地执行** |
| Session 日志写入 | ✅ | 追加到 `log-session/` |
| Replay 下载 | ✅ | 用 Kaggle CLI 在本地下载 |
| 文档编辑 | ✅ | 编辑 `docs/` 下的 md 文件 |
| 打包提交产物 | ❌ | 在远程服务器执行 |
| 模型训练 | ❌ | 在远程 `nlv100` 执行 |
| 评估报告同步 | ✅ | 从远程 rsync 到本地 |

---

# 远程服务器（nlv100）

## 连接信息

| 属性 | 值 |
|------|-----|
| 主机名 | `nlv100` |
| IP 地址 | `192.168.1.101` |
| SSH 命令 | `ssh nlv100` 或 `ssh 192.168.1.101` |
| Conda 环境 | `kaggle` |
| 工作目录 | `/data/app/sandbox/kaggle/kg-rl` |

## 远程目录结构

```
/data/app/sandbox/kaggle/kg-rl/
├── main.py                        # Agent 入口（推理用）
├── policy_np.npz                  # 模型权重
├── src/                           # 源代码
├── scripts/                       # 训练脚本
├── log/                           # 训练日志（TensorBoard 等）
├── eval_reports/                  # 评估报告 HTML/JSON
├── docs/                          # 项目文档
├── pkg/                           # 打包后的提交包
└── models/                       # 模型权重（.zip, .joblib）
```

---

# 编码工作流

详见 `/Users/nickyl/Developer/Sandbox/kagriculture/docs/WORKFLOW.md`。

**核心流程**：代码修改 → Code Review → 修复问题 → 本地评估 → 通过后提交。

---

# Replay 下载指南

详见 `/Users/nickyl/Developer/Sandbox/kagriculture/docs/replay-download-guide.md`。

---

# 提交规范

> ⚠️ **Kaggle 提交只能在本地进行，远程服务器不允许提交。**

## 完整流程

```
远程服务器                  本地 Mac
     │                          │
     │  1. 打包训练产物           │
     │  → pkg/submission-*.tar.gz│
     │                          │
     │  2. 复制到本地             │
     │  → /Users/nickyl/Developer/Sandbox/kagriculture/pkg/
     │                          │
     │                          │  3. 激活 conda 环境
     │                          │  source /opt/anaconda3/etc/profile.d/conda.sh
     │                          │  conda activate kaggle
     │                          │
     │                          │  4. 提交到 Kaggle
     │                          │  cd /Users/nickyl/Developer/Sandbox/kagriculture/pkg/
     │                          │  kaggle competitions submit -c kagriculture \\
     │                          │    -f <package_name> -m "<commit_message>"
```

## 提交命令

```bash
# 激活 conda 环境
source /opt/anaconda3/etc/profile.d/conda.sh
conda activate kaggle

# 切换到包目录
cd /Users/nickyl/Developer/Sandbox/kagriculture/pkg/

# 提交
kaggle competitions submit -c kagriculture -f <package_name> -m "<commit_message>"
```

---

# 评估报告同步

## 从远程同步 eval_reports

```bash
# 同步整个 eval_reports 目录到本地
rsync -av --progress \
  192.168.1.101:/data/app/sandbox/kaggle/kg-rl/eval_reports/ \
  /Users/nickyl/Developer/Sandbox/kagriculture/eval_reports/
```

## 同步单个模型评估结果

```bash
# 例如同步最新的 ROI reward 验证结果
rsync -av --progress \
  192.168.1.101:/data/app/sandbox/kaggle/kg-rl/eval_reports/iter_01_20260811_075528/ \
  /Users/nickyl/Developer/Sandbox/kagriculture/eval_reports/
```

## 每个 eval 目录的结构

```
iter_01_20260811_075528/     ← iteration 目录
├── summary.json               ← trade_frac, win_rate, action_counts
├── episodes.json              ← 每局详细 reward/action 数据
├── replay.html              ← 可视化 replay（可浏览器打开）
├── report.html              ← HTML 报告摘要
├── replays/                  ← per-episode JSON（Kaggle 格式）
├── model.zip                ← SB3 训练好的模型
├── policy_np.npz            ← numpy 格式权重（Kaggle 提交用）
└── train_log/
    ├── train.stdout         ← 完整训练日志
    └── train_eval.csv        ← eval 曲线数据
```

---

# 训练规范

详见 `/Users/nickyl/Developer/Sandbox/kagriculture/docs/WORKFLOW.md` 中的训练代码规范章节。

> ⚠️ 注意：`docs/TRAINING_SPEC.md` 文件尚未创建，如有需要应先创建该文档再进行相关训练开发。
