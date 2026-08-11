# CHANGE_SPEC-action-format — Kaggle Action 格式修复

> **Date**: 2026-08-09
> **Author**: MiniMax (Codex)
> **Based on**: KagricultureEnv v1

## 1. 问题描述

`_action_to_kaggle()` 返回的 action 格式错误，导致 RL agent 的 action 无法生效。

**Bug**: 返回 `[{...}]` (list 包装) 而不是 `{...}` (直接 dict)

## 2. 实验依据

- `debug_final.py` 测试显示：step 后 money 始终 3000 不变
- 直接 Kaggle 测试显示：HIRE action 正常工作 (3000→2999)
- 修复后测试显示：reward 正确计算 (-0.001 per HIRE)

## 3. 改动范围

- 文件: `src/envs/kagriculture_env.py`
- 函数: `_action_to_kaggle()` (第 355-369 行)
- 行数: ~15 行

## 4. 代码改动

```python
# Before:
def _action_to_kaggle(self, action: int) -> str:
    if action == 0:
        return []  # HOLD
    elif action == 1:
        return [{"market": [["HIRE"]]}]  # ❌ 错误：list 包装
    elif action == 2:
        return [{"market": [["SELL", "WHEAT", 1]]}]  # ❌
    elif action == 3:
        return [{"market": [["BUY_PRODUCT", "WHEAT", 1]]}]  # ❌
    elif action == 4:
        return [{"farmer": ["PASS"]}]  # ❌
    else:
        return []

# After:
def _action_to_kaggle(self, action: int) -> str:
    if action == 0:
        return {}  # HOLD
    elif action == 1:
        return {"market": [["HIRE"]]}  # ✅ 正确：直接 dict
    elif action == 2:
        return {"market": [["SELL", "WHEAT", 1]]}  # ✅
    elif action == 3:
        return {"market": [["BUY_PRODUCT", "WHEAT", 1]]}  # ✅
    elif action == 4:
        return {"farmer": ["PASS"]}  # ✅
    else:
        return {}
```

## 5. 预期效果

- Training loss: 下降
- Win rate vs random: 从 0% 提升到 >20%
- Reward signal: 正常计算

## 6. 风险

- **低**
- 回滚方案: 恢复原来的 list 包装格式

## 7. 相关修改

同时修复了 reward scale:
```python
# Before: money_delta / 10000.0  (太小)
# After:  money_delta / 1000.0    (10x 放大)
```
