# CHANGE_SPEC-roi-reward — ROI 驱动的 Reward 重构

> **Date**: 2026-08-11
> **Author**: Codex
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

- `logs/2026-08-11-model-eval-analysis.md`：所有模型的 trade_frac 与训练时长负相关，后期模型 0% 交易
- `eval_reports/` 中 iter_01_20260811_054021 和 073857 的 trade_frac=1.0 但对手是 random，胜率 100% 来自躺赢
- Gemini 分析确认：终止奖励与单步奖励量级失衡（+8.0 vs ±0.01），价值网络被 +8.0 支配

---

## 3. 改动范围

| 文件 | 改动内容 |
|------|---------|
| `src/envs/kagriculture_env.py` | Reward 计算逻辑重构 + reset 初始化 |

### 3.1 Reward 计算（`_compute_reward`）

**Before**:
```python
reward = (agent_d - 0.4 * opp_d) / 10000.0
if is_valid and has_real_trade_effect:
    reward += 0.01
if is_trade_action and is_valid and not has_real_trade_effect:
    reward -= 0.01
if consecutive_safe > 5 and tradeable:
    reward -= min(0.10, 0.01 * (n - 5))
```

**After**:
```python
# 净资产 W_t = cash + Σ(inventory_i * price_i)
# W_delta = W_t - W_prev（绝对增值）
# W_opp_delta = W_opp_t - W_opp_prev（对手增值）
# roi = W_delta / W_initial

reward = roi * 10.0 + (W_delta - 0.4 * W_opp_delta) / W_initial * 5.0
# 有效交易：+0.02
# 空交易：-0.01
# 停滞惩罚：不变
```

### 3.2 终止奖励（`step()`）

**Before**:
```python
if terminated:
    if won: reward += 8.0
    else:   reward -= 4.0
```

**After**:
```python
if terminated:
    final_roi = (W_t - self._initial_W) / (self._initial_W + 1e-8)
    sign = 1 if W_t > W_opp_t else -1
    terminal_reward = sign * 1.5 + max(0, final_roi * 5.0)
    reward += terminal_reward
```

### 3.3 reset()

新增：
```python
self._initial_W = W_t   # 记录初始净资产
self._prev_W = W_t
self._prev_W_opp = W_opp_t
self._consecutive_idle = 0
```

---

## 4. 预期效果

| 指标 | 改动前 | 改动后（预期） |
|------|--------|--------------|
| trade_frac | 0% (vs random 时 0~6.5%) | 30%~60% |
| HOLD/PASS 占比 | 90%+ | <50% |
| 终局 ROI 影响权重 | ~0（+8.0 固定） | 40%+（躺赢最多 +1.5） |
| Net Worth 追踪 | 仅 money | money + inventory × price |

---

## 5. 风险

| 风险 | 级别 | 回滚方案 |
|------|------|---------|
| ROI 归一化分母 W_0 为 0 | 低 | 加 1e-8 |
| 终止奖励缩小后 PPO 不收敛 | 中 | 监控 eval win_rate，若 <20% 回滚到 +6/-3 |
| 存货价格为 0 时 W_t 计算异常 | 低 | price 为 0 时跳过该品类的 inventory 计算 |

---

## 6. 验证方法

```python
# 1. 手动验证 W_t 计算
env = gym.make("Kagriculture-v0")
obs, _ = env.reset()
# 手动检查 W_t = money + sum(shed_i * price_i)

# 2. 验证 ROI reward 在交易时有信号
# money=1000, wheat=10, price=50 → W=1500
# 下一SELL后 money=1050, wheat=5 → W=1300 → W_delta=-200 → roi<0（合理）

# 3. 验证终止奖励
# 躺赢 W_T≈W_0 → final_roi≈0 → +1.5 分
# 翻倍 W_T=2*W_0 → final_roi=1.0 → +6.5 分
```
