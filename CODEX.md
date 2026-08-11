

## Submission 打包方式 (2026-08-10)

### 正确方式
1. cp models/policy_np.npz .
2. tar -czf pkg/submission.tar.gz main.py policy_np.npz
3. rm policy_np.npz

### 结构
- main.py (numpy inference, 无外部依赖)
- policy_np.npz (numpy 权重)

### 依赖
- 仅 numpy

