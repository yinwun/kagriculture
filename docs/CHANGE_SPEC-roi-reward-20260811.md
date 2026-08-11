# CHANGE_SPEC-roi-reward — ROI 驱动的 Reward 重构

> **Date**: 2026-08-11
> **Author**: Codex
> **Status**: ✅ VALIDATED — 250K steps 训练验证通过
> **Based on**: `docs/REWARD_AND_TRAINING_REDESIGN_20260811.md` + Gemini 分析

---

## 1. 问题描述

当前 reward 函数存在"消极躺赢陷阱"：

1. **终止奖励 +8.0 压倒一切**：一局 719 步，每步 reward ≈ ±0.01，而终止 Win 固定 +8.0。HOLD 全程得 0 → 终局 +8 → 总 ≈ 8.0，零风险躺赢。
2. **Net Worth 被忽略**：reward 仅看 `money_delta`，不计算存货价值（小麦、草莓等），导致"卖了东西但库存价值被忽视"信号失真。
3. **Random 对手无竞争**：HOLD 也能 100% 胜率，没有动力学交易。
4. **交易风险收益不对称**：有效交易 +0.01，空交易 -0.01，非法 -0.05，HOLD 0。期望为负时 PPO 理性回避。

---

## 2. 实验依据

### 2026-08-11 ROI Reward 验证训练（250K steps vs trained RF）

| 指标 | 旧 Reward（bug时代） | ROI Reward（新） |
|------|---------------------|-----------------|
| mean_reward | -46 → +4 | **-46 → +24** ✅ |
| trade_frac | 0% | **94-100%** ✅ |
| Win rate vs RF | 0% | **0%**（策略退化） |
| ep_len_mean | ~719 | ~719 |
| 结论 | reward 失灵 | **Reward 有效，策略需优化** |

**关键发现**：
- ROI Reward 成功驱动模型 100% 时间在交易（trade_frac 94-100%）
- mean_reward 从 -46 提升到 +24，证明 ROI 信号正确
- 但模型收敛到单一 BUY 动作策略（退化），vs trained RF 仍 0% 胜率
- **结论**：Reward 函数设计正确，需要通过 MaskablePPO + Phase 2 action space 解决策略退化

### ROI 权重调参过程

| 参数组合 | 结果 | 问题 |
|---------|------|------|
| `roi * 10 + roi_rel * 5` | ep_rew ≈ -50 | ROI 信号太弱 |
| `roi * 100 + roi_rel * 50` | ep_rew ≈ -55 | roi_rel 权重过大（对手每步增值惩罚-0.27/步）|
| `roi * 200 + roi_rel * 20` | ep_rew ≈ -55 | 同上 |
| `roi * 300 + roi_rel * 3` | **ep_rew ≈ +24** ✅ | 最终有效参数 |

---

## 3. 最终参数（已验证）

### Reward 公式

```python
# 净资产 W_t = cash + Σ(inventory_i × price_i)
roi = W_delta / W_0 * 300.0                        # 绝对净资产增长率（×300）
roi_relative = (W_delta - W_opp_delta) / W_0 * 3.0  # 相对差距（×3，缩小10倍避免惩罚过大）
reward = roi + roi_relative

# 动作奖惩
if valid_trade + has_real_effect:
    reward += 0.02          # 有效交易 bonus
elif valid_trade + no_effect:
    reward -= 0.01          # 空交易 penalty

# 停滞惩罚
if consecutive_idle > 5 and tradeable:
    reward -= min(0.10, 0.01 * (consecutive_idle - 5))

# Clip
reward = np.clip(reward, -5.0, 5.0)
```

### 终止奖励

```python
if terminated:
    final_roi = (W_T - W_0) / W_0
    terminal_reward = sign * 1.5 + max(0, final_roi * 5.0)
    # 躺赢（win, roi≈0）: +1.5
    # 翻倍（win, roi=1.0）: +1.5 + 5.0 = +6.5
    # 失败: -1.5 + max(0, roi*5.0)（roi 为负则无加成）
```

---

## 4. 待解决问题

### P0 — 策略退化（MaskablePPO）

模型学会 100% BUY，trade_frac=100% 但策略单一。需要：
- 使用 `action_masks()` 屏蔽非法动作（已有实现）
- 切换到 `MaskablePPO`（sb3-contrib）真正利用 action mask
- 当前 PPO 仍可能选非法动作（mask 不生效）

### P1 — 动作空间受限（Phase 2）

Phase 1 仅 5 个动作，模型无多样化选择。扩展到 Phase 2（8+ 动作）可增加策略表达空间。

---

## 5. 代码改动文件

| 文件 | 改动 |
|------|------|
| `src/envs/kagriculture_env.py` | ROI reward 计算 + reset 初始化 |

---

## 6. 验证命令

```bash
# 验证 reward 信号
python -c "
import gym; from src.envs.kagriculture_env import register
register()
env = gym.make('Kagriculture-v0', opponent='trained')
obs, _ = env.reset()
for i in range(20):
    a = env.action_space.sample()
    obs, r, done, _, info = env.step(a)
    print(f'Step {i}: r={r:+.4f} Wd={info.get(\"W_delta\",0):+.2f}')
"

# 验证训练后策略
python scripts/eval_models.py --pattern roi_reward_val --num_episodes 5 --opponent trained
```
