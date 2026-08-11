# ROI Reward — 250K Steps 评估报告

## 训练信息
- 训练时间：2026-08-11 08:36 ~ 09:14（~38 min）
- 模型：models/roi_reward_val.zip
- Steps：251,904
- 对手：trained RF
- Reward：ROI (roi*300 + roi_rel*3)

## eval_models.py 评估结果

### vs trained RF（10 episodes）
| Model | Trade % | Safe % | Win rate |
|-------|---------|--------|----------|
| roi_reward_val | **97.5%** | 2.5% | **0%** |
- action={BUY:7010, PASS:180} — 100% BUY，极少量 PASS

### vs random（10 episodes）
| Model | Trade % | Safe % | Win rate |
|-------|---------|--------|----------|
| roi_reward_val | **100%** | 0% | **100%** |
- action={BUY:7190} — 100% BUY

## 结论
- ✅ Reward 函数有效：trade_frac 从 0% → 97%
- ✅ mean_reward 从 -46 → +43
- ❌ 策略退化：100% BUY 单一动作，从不 SELL
- ❌ vs trained RF：0% 胜率
