# Replay 下载方法

本文档介绍如何从 Kaggle 下载 Kagriculture 竞赛的 episode replay 文件。

---

## 方式一：Kaggle CLI（推荐）

### 前置准备

```bash
# 1. 激活 conda 环境
source /opt/anaconda3/etc/profile.d/conda.sh
conda activate kaggle

# 2. 配置 Kaggle API Token（如果尚未配置）
mkdir -p ~/.kaggle
# 将你的 access_token 转换为标准 kaggle.json 格式
echo '{"username":"你的用户名","key":"你的KGAT_xxx"}' > ~/.kaggle/kaggle.json
chmod 600 ~/.kaggle/kaggle.json
```

### 下载 Replay

```bash
# 查看当前提交列表
kaggle competitions submissions kagriculture -c kagriculture

# 下载指定 episode 的 replay
kaggle competitions replay <episode_id>

# 示例：下载 episode 91686895 的 replay
kaggle competitions replay 91686895
# 文件保存至：./episode-91686895-replay.json
```

---

## 方式二：Python API

```python
from kaggle.api.kaggle_api_extended import KaggleApi

api = KaggleApi()
api.authenticate()

# 下载指定 episode 的 replay
api.competition_replay('kagriculture', '<episode_id>')
```

---

## 分析 Replay 文件

下载得到的 replay 是 JSON 文件，可以使用 Python 进行分析：

```python
import json

with open('episode-91686895-replay.json') as f:
    data = json.load(f)

# 查看奖励信息
print('Rewards:', data['rewards'])

# 查看总步数
steps = data['steps']
print(f'Steps: {len(steps)}')

# 逐步分析双方动作
for i in range(min(20, len(steps))):
    p0_action = steps[i][0].get('action')
    p1_action = steps[i][1].get('action')
    print(f'Step {i}: p0={p0_action}, p1={p1_action}')
```

---

## 相关说明

- **Submission ID vs Episode ID**：在 Kaggle 提交列表中，每条提交对应一个 `submissionId`；提交被评测后会产生一个 `episodeId`，用于唯一标识一场对局。
- **Replay 内容**：包含对局的完整步骤记录，包括每一步的观察、动作和奖励，可用于离线分析和调试 agent 行为。
- **典型用途**：当 agent 出现异常行为（如全程 PASS）时，通过下载 replay 分析每一步的输入输出，定位问题根因。
