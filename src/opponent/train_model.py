
"""对手模型训练 - Phase 2"""

import os
import sys
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
import joblib

def train_opponent_model(data_path, output_path):
    """训练对手模型"""
    print(f"Loading data from {data_path}...")
    data = np.load(data_path)
    X, y = data["X"], data["y"]
    print(f"Data shape: X={X.shape}, y={y.shape}")
    
    # 划分训练集和测试集
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )
    print(f"Train: {X_train.shape}, Test: {X_test.shape}")
    
    # 训练 RandomForest
    print("Training RandomForest...")
    model = RandomForestClassifier(
        n_estimators=100,
        max_depth=15,
        min_samples_split=10,
        n_jobs=-1,
        random_state=42
    )
    model.fit(X_train, y_train)
    
    # 评估
    train_acc = model.score(X_train, y_train)
    test_acc = model.score(X_test, y_test)
    print(f"Train accuracy: {train_acc:.4f}")
    print(f"Test accuracy: {test_acc:.4f}")
    
    # 保存
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    joblib.dump(model, output_path)
    print(f"Model saved to {output_path}")
    
    return model

if __name__ == "__main__":
    data_path = "data/opponent_dataset_combined.npz"
    output_path = "models/opponent_model.joblib"
    train_opponent_model(data_path, output_path)
