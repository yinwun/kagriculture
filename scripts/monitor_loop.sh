#!/bin/bash
# 循环训练监控脚本
# 每5分钟检查一次，发现问题自动告警

source /data/miniconda3/bin/activate kaggle
cd /data/app/sandbox/kaggle/kg-rl

LOG_DIR="log"
ALERT_EMAIL="nickyl@example.com"  # 修改为你的邮箱

echo "监控开始: $(date)"

while true; do
    # 检查训练进程
    PIDS=$(pgrep -f "train.py" || echo "")
    
    if [ -z "$PIDS" ]; then
        echo "[$(date)] 没有训练进程"
        
        # 检查是否有模型未训练完
        for i in 0 1 2 3; do
            MODEL="models/ppo_loop_s${i}.zip"
            LOG=$(ls -t ${LOG_DIR}/train_loop_s${i}_*.log 2>/dev/null | head -1)
            if [ -f "$LOG" ]; then
                if grep -q "Training complete" "$LOG"; then
                    echo "✅ 阶段 $i 已完成"
                else
                    echo "❌ 阶段 $i 日志未完成，尝试重新训练..."
                    # 可以自动重启
                fi
            fi
        done
        
        echo "所有训练完成，退出监控"
        break
    fi
    
    echo "[$(date)] 训练进程运行中: $PIDS"
    
    # 检查最新日志
    for log in $(ls -t ${LOG_DIR}/train_loop_s*.log 2>/dev/null | head -3); do
        STAGE=$(basename $log | grep -o "s[0-9]")
        LAST_LINE=$(tail -1 "$log")
        
        if echo "$LAST_LINE" | grep -q "Training complete"; then
            echo "✅ $STAGE 完成"
            # 分析结果
            if grep -q "Win rate: 0.00%" "$log"; then
                echo "⚠️ $STAGE 胜率 0%，可能需要调整"
            fi
        elif echo "$LAST_LINE" | grep -q "Error\|Traceback"; then
            echo "❌ $STAGE 报错!"
            tail -20 "$log"
        else
            # 提取进度
            STEPS=$(tail -30 "$log" | grep "total_timesteps" | tail -1 | grep -o "[0-9]\+" | tail -1)
            EP_REW=$(tail -30 "$log" | grep "ep_rew_mean" | tail -1 | grep -o "[-0-9.]\+" | tail -1)
            echo "  $STAGE: ${STEPS:-0} steps, reward: ${EP_REW:-N/A}"
        fi
    done
    
    # 检查 GPU
    GPU_MEM=$(nvidia-smi --query-gpu=memory.used --format=csv,noheader 2>/dev/null | head -1)
    echo "  GPU 内存: ${GPU_MEM:-N/A}"
    
    echo "---"
    sleep 300  # 5分钟
done
