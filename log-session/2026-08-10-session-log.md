
## Replay 下载方法 (2026-08-10 更新)

### 方式1: Kaggle CLI (推荐)
```bash
# 激活 conda 环境
source /opt/anaconda3/etc/profile.d/conda.sh
conda activate kaggle

# 查看提交列表
kaggle competitions submissions kagriculture -c kagriculture

# 下载指定 episode 的 replay
kaggle competitions replay <episode_id>

# 示例: 下载 episode 91686895 的 replay
kaggle competitions replay 91686895
# 下载到: ./episode-91686895-replay.json
```

### 方式2: Python API
```python
from kaggle.api.kaggle_api_extended import KaggleApi
api = KaggleApi()
api.authenticate()
api.competition_replay('kagriculture', '<episode_id>')
```

### 分析 Replay
```python
import json
with open('episode-91686895-replay.json') as f:
    data = json.load(f)

print('Rewards:', data['rewards'])
steps = data['steps']
print(f'Steps: {len(steps)}')

# 分析每一步的动作
for i in range(min(20, len(steps))):
    p0_action = steps[i][0].get('action')
    p1_action = steps[i][1].get('action')
    print(f'Step {i}: p0={p0_action}, p1={p1_action}')
```

### 最新提交分析 (2026-08-10)
- **Submission ID**: 55410260
- **Episode ID**: 91686895
- **最终比分**: [3000.0, 41686.0] - 我们输了
- **问题**: agent 每步都在执行 `{'farmer': ['PASS'], 'hands': [], 'market': []}` - 完全没有动作
- **原因**: main.py 动作映射失败，模型输出没有正确转换成 Kagriculture 动作格式

### Kaggle API Token 配置
```bash
# 本机 conda kaggle 环境的 token 位置
cat ~/.kaggle/access_token  # 显示: KGAT_xxxxx

# 复制为标准 kaggle.json 格式 (用户名随意，key 用 access_token)
mkdir -p ~/.kaggle
echo '{"username":"nickyl","key":"KGAT_ef9111a7b9ef9ac1c23de4f44c7155bd"}' > ~/.kaggle/kaggle.json
chmod 600 ~/.kaggle/kaggle.json
```
