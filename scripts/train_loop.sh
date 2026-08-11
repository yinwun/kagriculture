#!/bin/bash
# 10小时循环训练脚本
# Usage: bash scripts/train_loop.sh

source /data/app/miniconda3/bin/activate kaggle
cd /data/app/sandbox/kaggle/kg-rl

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
LOG_DIR="log"
MODEL_DIR="models"

# 训练配置
STAGES=(
    "500000:30m"
    "1000000:1h" 
    "2000000:2h"
    "5000000:5h"
)

echo "=========================================="
echo "10小时循环训练开始"
echo "时间: $(date)"
echo "=========================================="

TOTAL_START=$(date +%s)

for i in "${!STAGES[@]}"; do
    STAGE_INFO=${STAGES[$i]}
    STEPS=$(echo $STAGE_INFO | cut -d: -f1)
    LABEL=$(echo $STAGE_INFO | cut -d: -f2)
    
    MODEL_PATH="${MODEL_DIR}/ppo_loop_s${i}"
    LOG_FILE="${LOG_DIR}/train_loop_s${i}_${TIMESTAMP}.log"
    
    echo ""
    echo "=========================================="
    echo "阶段 $((i+1)): ${LABEL} (${STEPS} steps)"
    echo "开始时间: $(date)"
    echo "日志: ${LOG_FILE}"
    echo "=========================================="
    
    # 检查是否已有该阶段的模型
    if [ -f "${MODEL_PATH}.zip" ]; then
        echo "模型已存在，跳过此阶段: ${MODEL_PATH}"
        continue
    fi
    
    # 开始训练
    python scripts/train.py \
        --total_steps ${STEPS} \
        --model_path ${MODEL_PATH} \
        > ${LOG_FILE} 2>&1 &
    
    PID=$!
    echo "训练 PID: ${PID}"
    
    # 等待完成 (最多)
    ELAPSED=0
    while kill -0 $PID 2>/dev/null; do
        sleep 60
        ELAPSED=$((ELAPSED+60))
        echo "[$(date)] 已运行 ${ELAPSED}s, PID: ${PID}"
        
        # 超过阶段最大时间 130% 则停止
        MAX_TIME=$((${STEPS} / 200 * 130 / 100))  # 粗略估算
        if [ $ELAPSED -gt $((MAX_TIME)) ]; then
            echo "超过预计时间，停止 PID: ${PID}"
            kill $PID 2>/dev/null
            break
        fi
    done
    
    # 等待真正结束
    wait $PID
    EXIT_CODE=$?
    
    echo "阶段 $((i+1)) 完成，退出码: ${EXIT_CODE}"
    
    # 如果失败，停止
    if [ $EXIT_CODE -ne 0 ]; then
        echo "训练失败，退出码: ${EXIT_CODE}"
        exit 1
    fi
    
    # 检查模型
    if [ -f "${MODEL_PATH}.zip" ]; then
        echo "✅ 模型已保存: ${MODEL_PATH}"
    else
        echo "❌ 模型未找到: ${MODEL_PATH}"
    fi
done

TOTAL_END=$(date +%s)
TOTAL_ELAPSED=$((TOTAL_END - TOTAL_START))
echo ""
echo "=========================================="
echo "训练完成!"
echo "总耗时: $((TOTAL_ELAPSED/3600))h $(((TOTAL_ELAPSED%3600)/60))m"
echo "结束时间: $(date)"
echo "=========================================="
