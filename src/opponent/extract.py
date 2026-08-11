
"""从 Replay 数据提取对手的 (state, action) 对"""

import os
import sys
import json
import argparse
import numpy as np

print("Starting extract.py...", flush=True)

# 动作编码
ACTION_MAP = {
    "PASS": 0,
    "HIRE": 1,
    "SELL": 2,
    "BUY_PRODUCT": 3,
    "BUY_SEED": 4,
    "BUY_ANIMAL": 5,
    "FEED": 6,
    "FERTILIZE": 7,
    "WATER": 8,
    "HARVEST": 9,
    "PLANT": 10,
    "OTHER": 11,
}

def encode_action(action_dict):
    action_list = []
    if "farmer" in action_dict and action_dict["farmer"]:
        action_list.extend(action_dict["farmer"])
    if "hands" in action_dict and action_dict["hands"]:
        for hand in action_dict["hands"]:
            if isinstance(hand, list):
                action_list.extend(hand)
    if "market" in action_dict and action_dict["market"]:
        for market_op in action_dict["market"]:
            if isinstance(market_op, list) and len(market_op) > 0:
                action_list.append(market_op[0])
    
    for action in action_list:
        if action in ACTION_MAP:
            return ACTION_MAP[action]
    return ACTION_MAP["OTHER"]

def extract_features(obs):
    features = []
    features.append(obs.get("day", 0) / 30.0)
    features.append(obs.get("hour", 0) / 24.0)
    
    market = obs.get("market", {})
    prices = market.get("prices", {})
    for item in ["WHEAT", "CARROT", "TOMATO", "MILK", "EGG", "WOOL"]:
        features.append(prices.get(item, 0) / 300.0)
    
    inventory = market.get("inventory", {})
    for item in ["WHEAT", "CARROT", "TOMATO", "MILK", "EGG", "WOOL"]:
        features.append(inventory.get(item, 0) / 10000.0)
    
    private = obs.get("private", {})
    shed = private.get("shed", {})
    for item in ["WHEAT", "CARROT", "TOMATO", "MILK", "EGG", "WOOL", "COW", "SHEEP"]:
        features.append(shed.get(item, 0) / 100.0)
    
    seeds = private.get("seeds", {})
    for crop in ["WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON"]:
        features.append(seeds.get(crop, 0) / 50.0)
    
    # Dynamic player id - important for opponent modeling!
    player_id = obs.get("player", 0)
    farms = obs.get("farms", [])
    if farms and len(farms) > player_id:
        features.append(farms[player_id].get("money", 0) / 100000.0)
        features.append(farms[player_id].get("hires_today", 0) / 5.0)
    else:
        features.extend([0, 0])
    
    return np.array(features, dtype=np.float32)

def process_replay(replay_path):
    try:
        with open(replay_path) as f:
            data = json.load(f)
    except Exception as e:
        return []
    
    dataset = []
    for step in data.get("steps", []):
        for player_data in step:
            if not isinstance(player_data, dict):
                continue
            obs = player_data.get("observation", {})
            action = player_data.get("action", {})
            if not obs or not action:
                continue
            try:
                features = extract_features(obs)
                action_id = encode_action(action)
                dataset.append((features, action_id))
            except:
                continue
    return dataset

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data_dir", type=str, default="data/extracted")
    parser.add_argument("--output", type=str, default="data/opponent_dataset.npz")
    parser.add_argument("--days", type=str, default="2026-08-07,2026-08-08")
    args = parser.parse_args()
    
    print(f"Data dir: {args.data_dir}", flush=True)
    print(f"Days: {args.days}", flush=True)
    
    all_data = []
    processed = 0
    
    for day in args.days.split(","):
        day_dir = os.path.join(args.data_dir, day)
        print(f"Processing {day_dir}...", flush=True)
        if not os.path.exists(day_dir):
            print(f"Directory not found: {day_dir}", flush=True)
            continue
        files = [f for f in os.listdir(day_dir) if f.endswith(".json")]
        print(f"Found {len(files)} files", flush=True)
        for fname in files:
            dataset = process_replay(os.path.join(day_dir, fname))
            all_data.extend(dataset)
            processed += 1
            if processed % 100 == 0:
                print(f"Processed {processed} files, {len(all_data)} samples", flush=True)
    
    print(f"Total: {processed} files, {len(all_data)} samples", flush=True)
    
    if all_data:
        X, y = zip(*all_data)
        X = np.array(X)
        y = np.array(y)
        os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
        np.savez_compressed(args.output, X=X, y=y)
        print(f"Saved to {args.output}", flush=True)
        print(f"X:{X.shape}, y:{y.shape}", flush=True)
        print(f"Action dist: {np.bincount(y)}", flush=True)

if __name__ == "__main__":
    main()
