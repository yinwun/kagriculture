# 数据管理

> 本文档说明 Kagriculture 每日数据的下载、更新和使用

---

## 1. 数据概述

### 1.1 数据来源

- **来源**: Kaggle Dataset `kaggle/kaggriculture-episodes-index`
- **内容**: 每天的 episode replay JSON 文件
- **格式**: ZIP 压缩包，每天约 400-570 MB

### 1.2 数据存储位置

```
/data/app/sandbox/kaggle/kg-rl/data/
├── kaggriculture-episodes-2026-07-30.zip  (314 MB)
├── kaggriculture-episodes-2026-07-31.zip  (570 MB)
├── kaggriculture-episodes-2026-08-01.zip  (559 MB)
├── ...
└── kaggriculture-episodes-2026-08-08.zip  (405 MB)  ← 最新
```

### 1.3 数据规模

| 日期 | 大小 | Episode 数量 |
|------|------|--------------|
| 2026-07-30 | 314 MB | ~864 |
| 2026-07-31 | 570 MB | ~928 |
| 2026-08-01 | 559 MB | ~864 |
| 2026-08-02 | 489 MB | ~864 |
| 2026-08-08 | 405 MB | ~864 |

---

## 2. 数据下载

### 2.1 手动下载

```bash
# 使用 Kaggle API 下载最新数据
kaggle datasets download -d kaggle/kaggriculture-episodes-index -p /data/app/sandbox/kaggle/kg-rl/data/ --unzip
```

### 2.2 自动下载脚本

```python
#!/usr/bin/env python3
"""每日数据下载脚本"""

import subprocess
import datetime
from pathlib import Path

DATA_DIR = Path("/data/app/sandbox/kaggle/kg-rl/data")
LOG_FILE = DATA_DIR / "download.log"

def download_latest():
    """下载最新的每日数据"""
    today = datetime.date.today()
    slug = f"kaggriculture-episodes-{today.isoformat()}"
    
    zip_path = DATA_DIR / f"{slug}.zip"
    
    if zip_path.exists():
        print(f"Already downloaded: {zip_path.name}")
        return
    
    try:
        # 下载
        subprocess.run([
            "kaggle", "datasets", "download",
            "-d", f"kaggle/{slug}",
            "-p", str(DATA_DIR),
            "--unzip"
        ], check=True)
        
        # 记录日志
        with open(LOG_FILE, "a") as f:
            f.write(f"{today}: Downloaded {slug}\n")
        
        print(f"Downloaded: {slug}")
    
    except subprocess.CalledProcessError as e:
        print(f"Download failed: {e}")

if __name__ == "__main__":
    download_latest()
```

### 2.3 Crontab 定时任务

```bash
# 每天早上 6 点自动下载
0 6 * * * /usr/bin/python3 /data/app/sandbox/kaggle/kg-rl/scripts/download_daily.py >> /data/app/sandbox/kaggle/kg-rl/logs/download.log 2>&1
```

---

## 3. 数据解压与分析

### 3.1 解压单个文件

```bash
cd /data/app/sandbox/kaggle/kg-rl/data
unzip -o kaggriculture-episodes-2026-08-08.zip -d extracted/2026-08-08/
```

### 3.2 解压后结构

```
extracted/2026-08-08/
├── episode-000001-replay.json
├── episode-000002-replay.json
├── ...
└── episode-000864-replay.json
```

### 3.3 Episode 文件格式

```python
{
    "id": 89950852,
    "rewards": [118654.0, 120108.0],  # 两个玩家的最终金钱
    "steps": 720,  # 步数
    "specification": {...},
    "info": {
        "Agents": [{"Name": "nickyl"}, {"Name": "nickyl"}],
        "EpisodeId": 89950852,
        "TeamNames": ["nickyl", "nickyl"],
    }
}
```

---

## 4. 数据使用

### 4.1 用于 RL Training

```python
from kg_rl.data import EpisodeDataset

# 加载所有 episode
dataset = EpisodeDataset("/data/app/sandbox/kaggle/kg-rl/data/extracted/")

# 获取 episode
episode = dataset.get_episode("2026-08-08", episode_id=89950852)

# 分析
print(f"Player 0 money: {episode.rewards[0]}")
print(f"Player 1 money: {episode.rewards[1]}")
print(f"Winner: {0 if episode.rewards[0] > episode.rewards[1] else 1}")
```

### 4.2 用于 Imitation Learning

```python
from kg_rl.data import EpisodeDataset, BehaviorCloningDataset

# 加载 expert episodes
dataset = EpisodeDataset("/data/app/sandbox/kaggle/kg-rl/data/extracted/")

# 过滤 top player 的 episodes
top_episodes = dataset.filter_by_score(min_score=2500)

# 转换为 BC 格式
bc_dataset = BehaviorCloningDataset(top_episodes)

# 用于 BC 训练
for obs, action in bc_dataset:
    ...
```

### 4.3 用于 Evaluation

```python
from kg_rl.eval import evaluate_on_replays

# 在历史 episode 上评估
results = evaluate_on_replays(
    agent=trained_agent,
    replay_dir="/data/app/sandbox/kaggle/kg-rl/data/extracted/",
    n_episodes=100,
)

print(f"Win rate: {results[win_rate]:.2%}")
print(f"Avg money: {results[avg_money]:.0f}")
```

---

## 5. 数据预处理

### 5.1 Episode 解析

```python
class EpisodeParser:
    """解析 episode JSON 文件"""
    
    def parse(self, json_path: Path) -> dict:
        with open(json_path) as f:
            data = json.load(f)
        
        return {
            "id": data["id"],
            "rewards": data["rewards"],
            "steps": len(data["steps"]),
            "winner": 0 if data["rewards"][0] > data["rewards"][1] else 1,
            "margin": abs(data["rewards"][0] - data["rewards"][1]),
        }
    
    def parse_step(self, step_data: list) -> dict:
        """解析单个 step"""
        # step_data 包含两个玩家的 obs
        return {
            "player_0_obs": step_data[0]["observation"],
            "player_1_obs": step_data[1]["observation"],
            "player_0_reward": step_data[0].get("reward", 0),
            "player_1_reward": step_data[1].get("reward", 0),
        }
```

### 5.2 特征提取

```python
from kg_rl.data import FeatureExtractor

extractor = FeatureExtractor()

# 从 episode 提取特征
for step in episode.steps():
    obs = step["player_0_obs"]
    
    features = extractor.extract(obs)
    # features = {
    #     "money": float,
    #     "wheat_price": float,
    #     "wheat_inventory": int,
    #     ...
    # }
```

---

## 6. 数据管理脚本

### 6.1 脚本列表

```
scripts/
├── download_daily.py       # 下载每日数据
├── extract_all.py         # 解压所有数据
├── analyze_episodes.py    # 分析 episode
├── build_bc_dataset.py    # 构建 BC 数据集
└── export_for_training.py # 导出训练数据
```

### 6.2 download_daily.py

```python
#!/usr/bin/env python3
"""每日数据下载"""

import subprocess
import sys
from pathlib import Path
from datetime import datetime, timedelta

DATA_DIR = Path("/data/app/sandbox/kaggle/kg-rl/data")

def get_latest_slug():
    """获取最新的 dataset slug"""
    # 从 Kaggle API 获取最新可用 slug
    result = subprocess.run(
        ["kaggle", "datasets", "files", "kaggle/kaggriculture-episodes-index"],
        capture_output=True, text=True
    )
    # 解析输出获取最新日期
    ...

def download(slug: str):
    zip_path = DATA_DIR / f"{slug}.zip"
    if zip_path.exists():
        print(f"Already exists: {zip_path.name}")
        return
    
    print(f"Downloading {slug}...")
    subprocess.run([
        "kaggle", "datasets", "download",
        "-d", f"kaggle/{slug}",
        "-p", str(DATA_DIR),
    ], check=True)
    print(f"Downloaded: {zip_path.name}")

if __name__ == "__main__":
    slug = get_latest_slug()
    if slug:
        download(slug)
    else:
        print("Failed to get latest slug")
        sys.exit(1)
```

---

## 7. 存储空间管理

### 7.1 当前使用

```
/data/app/sandbox/kaggle/kg-rl/data/
├── Raw ZIP files: ~4 GB
└── Extracted: ~20 GB (如果全部解压)
```

### 7.2 保留策略

| 数据类型 | 保留时间 | 说明 |
|----------|-----------|------|
| 最新 7 天 | 永久 | 用于训练 |
| 最新 30 天 | 永久 | 用于分析 |
| 30 天以前 | 可选删除 | 如果空间不足 |

### 7.3 清理脚本

```python
#!/usr/bin/env python3
"""清理旧数据"""

from pathlib import Path
from datetime import datetime, timedelta

DATA_DIR = Path("/data/app/sandbox/kaggle/kg-rl/data")
KEEP_DAYS = 30

def cleanup():
    cutoff = datetime.now() - timedelta(days=KEEP_DAYS)
    
    for zip_file in DATA_DIR.glob("kaggriculture-episodes-*.zip"):
        date_str = zip_file.stem.replace("kaggriculture-episodes-", "")
        try:
            file_date = datetime.strptime(date_str, "%Y-%m-%d")
            if file_date < cutoff:
                print(f"Deleting {zip_file.name}...")
                zip_file.unlink()
        except ValueError:
            print(f"Skipping {zip_file.name}")

if __name__ == "__main__":
    cleanup()
```

---

## 8. 数据用于 Self-Play 对手池

### 8.1 从历史数据提取对手策略

```python
from kg_rl.opponent import OpponentPool

# 从历史 episode 构建对手池
pool = OpponentPool()

for date in ["2026-08-01", "2026-08-02", ...]:
    for episode in load_episodes(date):
        # 提取对手的行为
        opponent_behavior = extract_behavior(episode)
        pool.add(opponent_behavior, score=episode.reward)
```

### 8.2 在 RL 训练中使用对手池

```python
from kg_rl.algos import PPOWithOpponents

agent = PPOWithOpponents(
    policy=MultiHeadPolicy,
    opponent_pool=opponent_pool,
)

# 训练时随机对战不同对手
agent.learn(total_timesteps=10_000_000)
```

---

## 9. 相关文档

- [DESIGN-SPEC.md](./01-DESIGN-SPEC.md) — 总体设计
- [Orbit Wars 1st Place](https://github.com/IsaiahPressman/kaggle-orbit-wars) — 参考实现

---

## 10. 更新日志

| 日期 | 内容 |
|------|------|
| 2026-08-09 | 初始化文档 |
