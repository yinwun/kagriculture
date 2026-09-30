# Project Context

## Goal
开发一个 Evolution Engine，用于 prompt mutation 自动优化。

## Architecture

MutationEngine
    |
    v
EvolutionEngine
    |
    v
RewardEvaluator

## Current Status

完成：
- PatternGraph
- ShapleyReward

进行中：
- WorldModel

## Important Decisions

1. 不使用 frozenset 存全部状态
2. 使用 transition graph 降低状态爆炸

## Current Problem

Reward allocation 在多工具情况下不稳定。目的是新开窗口后，读取文件知道进度
