"""纯 NumPy RL Agent - Kaggle 提交版本
与 src/envs/kagriculture_env.py 的 ObsProcessor.process() 完全一致
"""

import sys
import os
import numpy as np

_FILE_DIR = os.path.dirname(os.path.abspath(__file__)) if '__file__' in dir() else os.getcwd()

# Constants - 必须与 KagricultureEnv 一致
MAX_STEPS = 720
OBS_DIM = 32


def _count_plantable_tiles(farm):
    """计算可种植的 tile 数量"""
    tiles = farm.get("tiles", [])
    count = 0
    for row in tiles:
        for tile in row:
            if tile is None:
                count += 1
            elif isinstance(tile, str) and tile == "empty":
                count += 1
            elif isinstance(tile, dict) and (tile.get("crop") is None and tile.get("animal") is None):
                count += 1
    return count


def _count_plants_ready(farm):
    """计算已成熟可以收获的作物数量"""
    tiles = farm.get("tiles", [])
    count = 0
    for row in tiles:
        for tile in row:
            if isinstance(tile, dict) and tile.get("state") == "ready":
                count += 1
    return count


def _count_total_plants(farm):
    """计算总作物数量"""
    tiles = farm.get("tiles", [])
    count = 0
    for row in tiles:
        for tile in row:
            if isinstance(tile, dict) and tile.get("crop") is not None:
                count += 1
    return count


def _count_animals(farm):
    """计算动物数量"""
    tiles = farm.get("tiles", [])
    cows = 0
    sheep = 0
    unfed = 0
    for row in tiles:
        for tile in row:
            if isinstance(tile, dict):
                animal = tile.get("animal")
                if animal == "cow":
                    cows += 1
                    if not tile.get("fed", False):
                        unfed += 1
                elif animal == "sheep":
                    sheep += 1
                    if not tile.get("fed", False):
                        unfed += 1
    return {"cows": cows, "sheep": sheep, "unfed": unfed}


def _estimate_opponent(raw_obs):
    """估算对手状态"""
    if len(raw_obs.farms) > 1:
        opponent_farm = raw_obs.farms[1]
        return {
            "estimated_money": opponent_farm.get("money", 50000),
            "visible_plants": _count_total_plants(opponent_farm),
            "visible_animals": _count_animals(opponent_farm)["cows"] + _count_animals(opponent_farm)["sheep"],
        }
    return {"estimated_money": 50000.0, "visible_plants": 0, "visible_animals": 0}


def process_observation(raw_obs, step_count=0):
    """将 Kaggle raw observation 转换为 32 维向量
    与 KagricultureEnv._process_observation() + ObsProcessor.process() 完全一致
    """
    result = np.zeros(OBS_DIM, dtype=np.float32)
    
    farm = raw_obs.farms[0]
    private = raw_obs.private
    shed = private.shed if isinstance(private.shed, dict) else {}
    
    # 构建与训练时相同的 simple_obs 结构
    simple_obs = {
        "step": step_count,
        "day": raw_obs.day,
        "money": farm.get("money", 0),
        "market": {
            "prices": raw_obs.market.get("prices", {}),
            "inventory": raw_obs.market.get("inventory", {}),
        },
        "farm": {
            "plantable_tiles": _count_plantable_tiles(farm),
            "plants_ready": _count_plants_ready(farm),
            "total_plants": _count_total_plants(farm),
            "weed_density": 0.0,
            "animals": _count_animals(farm),
        },
        "private": {
            "hands": len(farm.get("hands", [])),
            "money": farm.get("money", 0),
            "wheat_in_shed": shed.get("WHEAT", 0),
            "fertilizer_in_shed": shed.get("FERTILIZER", 0),
            "hires_left": farm.get("hires_today", 0),
        },
        "opponent": _estimate_opponent(raw_obs),
    }
    
    # 以下完全复制 ObsProcessor.process() 的逻辑
    obs = simple_obs
    
    # 全局状态 (0-2)
    result[0] = obs.get("step", 0) / MAX_STEPS
    result[1] = obs.get("day", 0) / 30.0
    money = obs.get("money", 0)
    result[2] = min(money, 100000) / 100000.0
    
    # Market (3-10)
    market = obs.get("market", {})
    prices = market.get("prices", {})
    result[3] = prices.get("WHEAT", 0) / 100.0
    result[4] = prices.get("FERTILIZER", 0) / 100.0
    result[5] = prices.get("MELON", 0) / 100.0
    result[6] = prices.get("STRAWBERRY", 0) / 100.0
    
    inventory = market.get("inventory", {})
    result[7] = inventory.get("WHEAT", 0) / 1000.0
    result[8] = inventory.get("FERTILIZER", 0) / 1000.0
    result[9] = inventory.get("MELON", 0) / 1000.0
    result[10] = inventory.get("STRAWBERRY", 0) / 1000.0
    
    # Farm 汇总 (11-20)
    farm_data = obs.get("farm", {})
    result[11] = farm_data.get("plantable_tiles", 0) / 100.0
    result[12] = farm_data.get("plants_ready", 0) / 100.0
    result[13] = farm_data.get("total_plants", 0) / 100.0
    result[14] = farm_data.get("weed_density", 0)
    
    # Animals (15-20)
    animals = farm_data.get("animals", {})
    result[15] = animals.get("cows", 0) / 10.0
    result[16] = animals.get("sheep", 0) / 10.0
    result[17] = animals.get("unfed", 0) / 10.0
    
    # Private state (21-25)
    private_data = obs.get("private", {})
    result[21] = private_data.get("hands", 0) / 5.0
    result[22] = private_data.get("money", 0) / 100000.0
    result[23] = private_data.get("wheat_in_shed", 0) / 1000.0
    result[24] = private_data.get("fertilizer_in_shed", 0) / 100.0
    result[25] = private_data.get("hires_left", 0) / 3.0
    
    # 对手估算 (26-30)
    opponent = obs.get("opponent", {})
    result[26] = opponent.get("estimated_money", 0) / 100000.0
    result[27] = opponent.get("visible_plants", 0) / 100.0
    result[28] = opponent.get("visible_animals", 0) / 10.0
    
    return result


class SimpleActorNP:
    """纯 NumPy 实现的 Actor"""
    def __init__(self, weights_path):
        data = np.load(weights_path)
        self.W1 = data['mlp_extractor.policy_net.0.weight']
        self.b1 = data['mlp_extractor.policy_net.0.bias']
        self.W2 = data['mlp_extractor.policy_net.2.weight']
        self.b2 = data['mlp_extractor.policy_net.2.bias']
        self.W_action = data['action_net.weight']
        self.b_action = data['action_net.bias']
        
    def relu(self, x):
        return np.maximum(0, x)
    
    def forward(self, obs):
        x = np.dot(self.W1, obs) + self.b1
        x = self.relu(x)
        x = np.dot(self.W2, x) + self.b2
        x = self.relu(x)
        logits = np.dot(self.W_action, x) + self.b_action
        return logits
    
    def get_action(self, obs, deterministic=True):
        logits = self.forward(obs)
        if deterministic:
            return np.argmax(logits)
        else:
            probs = np.exp(logits - np.max(logits))
            probs = probs / np.sum(probs)
            return np.random.choice(len(probs), p=probs)


_actor = None
_step_count = 0

def load_actor():
    global _actor
    if _actor is None:
        weights_path = os.path.join(_FILE_DIR, 'policy_np.npz')
        _actor = SimpleActorNP(weights_path)
    return _actor


def agent(obs, config=None):
    """Kaggle 环境入口"""
    global _step_count
    
    try:
        actor = load_actor()
        
        # 修复: 正确处理 Kaggle raw observation
        if isinstance(obs, list):
            obs_array = np.array(obs, dtype=np.float32)
        else:
            # 重要: 将 raw observation 转换为 32 维向量 (与训练时一致)
            obs_array = process_observation(obs, _step_count)
            _step_count += 1
        
        action = actor.get_action(obs_array, deterministic=True)
        
        if action == 0:
            return {}  # HOLD — empty dict (Kaggle convention: "no actions this turn")
        elif action == 1:
            return {"market": [["HIRE"]]}  # FIX: single dict, not list-wrapped
        elif action == 2:
            return {"market": [["SELL", "WHEAT", 1]]}
        elif action == 3:
            return {"market": [["BUY_PRODUCT", "WHEAT", 1]]}
        elif action == 4:
            return {"farmer": ["PASS"]}
        else:
            return {}
    except Exception as e:
        # 出错时返回空操作
        return {}
