# KG-RL Project Context

## 目标
开发 Kagriculture 比赛的 RL Agent (PPO)，目标是进入 Top 5。

## 远程服务器访问

| 属性 | 值 |
|------|-----|
| 主机名 | nlv100 |
| IP 地址 | 192.168.1.101 |
| 用户名 | (默认) |
| 工作目录 | /data/app/sandbox/kaggle/kg-rl |
| 日志文件 | /data/app/sandbox/kaggle/kg-rl/log-session.md |
| Conda 环境 | kaggle |

### SSH 连接
```bash
ssh nlv100
# 或
ssh 192.168.1.101
```

### Conda 环境激活
```bash
source /opt/anaconda3/etc/profile.d/conda.sh
conda activate kaggle
```

## 项目结构
```
/data/app/sandbox/kaggle/kg-rl/
├── main.py              # 提交用 inference 代码
├── src/
│   ├── envs/
│   │   └── kagriculture_env.py  # Gymnasium 环境封装
│   └── algos/
│       └── ppo.py       # PPO 算法
├── models/
│   ├── ppo_v4_short.zip # 训练好的模型
│   └── policy_np.npz    # 导出给 main.py 的权重
├── pkg/
│   └── submission-*.tar.gz  # 提交包
├── scripts/
│   ├── train.py         # 训练脚本
│   └── export.py        # 模型导出脚本
└── log/
    └── 2026-08-10_*.log # 训练日志
```

## 当前状态

### 已完成
- PPO 训练环境搭建 ✅
- Action space 定义 (5 个 market 动作) ✅
- 动作合法性检查 + 惩罚机制 ✅
- 对手模型训练 (RF based on replay data) ✅

### 问题
- **main.py 动作映射失败** - agent 每步都在 PASS，没有执行任何有意义的动作
- 最新提交比分: [3000.0, 41686.0] - 输了

### 待修复
1. 检查 main.py 的 `_action_to_kaggle()` 函数
2. 验证模型权重是否正确导出
3. 确认 action ID 到 Kagriculture 动作格式的映射

## 训练命令
```bash
cd /data/app/sandbox/kaggle/kg-rl
source /opt/anaconda3/etc/profile.d/conda.sh
conda activate kaggle

# 短训练 (2.5M steps)
python scripts/train.py --total_timesteps 2500000 --opponent trained --save_freq 50000

# 训练日志
tail -f log/2026-08-10_*.log
```

## 提交命令
```bash
cd /data/app/sandbox/kaggle/kg-rl
python scripts/export.py --model_path models/ppo_v4_short

# 打包
tar -czf pkg/submission-ppo-v4-short.tar.gz main.py policy_np.npz

# 提交
kaggle competitions submit kagriculture -f pkg/submission-ppo-v4-short.tar.gz -m "PPO v4 short training"
```

## Replay 下载
```bash
kaggle competitions replay <episode_id>
# 例: kaggle competitions replay 91686895
```

## Kaggle API Token
- 位置: `~/.kaggle/kaggle.json`
- 格式: `{"username":"nickyl","key":"KGAT_xxx"}`
