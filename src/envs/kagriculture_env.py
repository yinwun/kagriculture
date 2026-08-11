"""
Kagriculture Gymnasium Environment Wrapper

将 Kaggle Kagriculture 环境包装成 Gymnasium 格式，供 Stable Baselines3 使用。
注意：Kaggle 官方拼写是 kaggriculture (两个 g)
"""

import gymnasium as gym
import numpy as np
from typing import Dict, Tuple, Optional, List, Any

# ============================================================
# Constants
# ============================================================

MAX_STEPS = 720  # 30 days * 24 steps/day
GRID_SIZE = 10

# Phase 1: WHEAT-only market actions (95% coverage)
PHASE1_MARKET_ACTIONS = [
    "HOLD",              # 0: 不操作
    "HIRE",              # 1: 雇佣
    "SELL_WHEAT",        # 2: 卖小麦
    "BUY_PRODUCT_WHEAT", # 3: 买小麦
]

# Farmer actions for Phase 1 (simplified)
PHASE1_FARMER_ACTIONS = [
    "PASS",              # 0: 跳过
    "NORTH",             # 1: 向北
    "SOUTH",             # 2: 向南
    "WEST",              # 3: 向西
    "EAST",              # 4: 向东
]

# ============================================================
# Kagriculture Environment Registration (一次性)
# ============================================================

_KAGRICULTURE_REGISTERED = False

def _register_kagriculture():
    """注册 Kagriculture 环境到 Kaggle Environments (只注册一次)"""
    global _KAGRICULTURE_REGISTERED
    if _KAGRICULTURE_REGISTERED:
        return
        
    from kaggle_environments import core as _core
    from kaggle_environments.envs.kaggriculture.kaggriculture import (
        agents as _kg_agents,
        html_renderer as _kg_html_renderer,
        interpreter as _kg_interpreter,
        renderer as _kg_renderer,
        specification as _kg_specification,
    )
    
    # 注意：Kaggle 官方拼写是 kagriculture (两个 g - kaggriculture)
    if "kagriculture" not in _core.environments:
        _core.register("kagriculture", {
            "agents": _kg_agents,
            "html_renderer": _kg_html_renderer,
            "interpreter": _kg_interpreter,
            "renderer": _kg_renderer,
            "specification": _kg_specification,
        })
    
    _KAGRICULTURE_REGISTERED = True

# 在模块导入时注册
_register_kagriculture()

# ============================================================
# Observation Processor
# ============================================================

class ObsProcessor:
    """处理 raw observation 到 neural network 输入"""
    
    def __init__(self):
        self.input_dim = 32  # 简化版本
    
    def process(self, obs: Dict) -> np.ndarray:
        """将 Kagriculture observation 转换为固定长度 vector"""
        result = np.zeros(self.input_dim, dtype=np.float32)
        
        # 全局状态 (0-2)
        result[0] = obs.get("step", 0) / MAX_STEPS
        result[1] = obs.get("day", 0) / 30.0
        # Money - simple_obs has money key directly
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
        farm = obs.get("farm", {})
        result[11] = farm.get("plantable_tiles", 0) / 100.0
        result[12] = farm.get("plants_ready", 0) / 100.0
        result[13] = farm.get("total_plants", 0) / 100.0
        result[14] = farm.get("weed_density", 0)
        
        # Animals (15-20)
        animals = farm.get("animals", {})
        result[15] = animals.get("cows", 0) / 10.0
        result[16] = animals.get("sheep", 0) / 10.0
        result[17] = animals.get("unfed", 0) / 10.0
        
        # Private state (21-25)
        private = obs.get("private", {})
        result[21] = private.get("hands", 0) / 5.0
        result[22] = private.get("money", 0) / 100000.0
        result[23] = private.get("wheat_in_shed", 0) / 1000.0
        result[24] = private.get("fertilizer_in_shed", 0) / 100.0
        result[25] = private.get("hires_left", 0) / 3.0
        
        # 对手估算 (26-30)
        opponent = obs.get("opponent", {})
        result[26] = opponent.get("estimated_money", 0) / 100000.0
        result[27] = opponent.get("visible_plants", 0) / 100.0
        result[28] = opponent.get("visible_animals", 0) / 10.0
        
        return result
    
    def get_input_dim(self) -> int:
        return self.input_dim


# ============================================================
# Kagriculture Environment
# ============================================================

class KagricultureEnv(gym.Env):
    """
    Kagriculture Gymnasium 环境
    
    使用简化 observation 和 Phase 1 action space。
    
    注意：Kaggle 环境的 observation 结构不同于标准 Gym：
    - 使用 Struct 类 (类似 dict)
    - farms[player_id] 而不是 players[player_id]
    - market 是 dict 包含 inventory 和 prices
    - tiles 可以是 None, "LOCKED", 或 dict
    - private.shed 是 dict 包含物品数量
    """
    
    metadata = {"render_modes": []}
    
    def __init__(self, opponent: str = "random", reward_type: str = "dense",
                 opponent_model_path: str = None, kaggle_env=None):
        """Kagriculture Gym env.

        Args:
          opponent: "random" or "trained"
          reward_type: "dense" (money_delta / 10000 per step) or "sparse" (0)
          opponent_model_path: path to RF joblib for "trained" opponent
          kaggle_env: optional pre-built kaggle_environments.Environment to
            share across train and eval (avoids opponent-state divergence).
            None = lazy-create on first reset.
        """
        super().__init__()

        self.opponent = opponent
        self.reward_type = reward_type
        self.opponent_model_path = opponent_model_path
        self.obs_processor = ObsProcessor()

        # 加载对手模型
        self._opponent_model = None
        if opponent == "trained":
            from src.opponent.model import OpponentModel
            model_path = opponent_model_path or "models/opponent_model.joblib"
            self._opponent_model = OpponentModel(model_path)
            self._opponent_model.load()
            print(f"Loaded opponent model from {model_path}")

        # Action space: Discrete(5) for Phase 1
        # 0: HOLD, 1: HIRE, 2: SELL_WHEAT, 3: BUY_PRODUCT_WHEAT, 4: PASS
        self.action_space = gym.spaces.Discrete(5)

        # Observation space: Box space with fixed dimension
        self.observation_space = gym.spaces.Box(
            low=-1.0, high=2.0, shape=(self.obs_processor.get_input_dim(),), dtype=np.float32
        )

        # Internal state
        self._kaggle_env = kaggle_env  # may be None → lazy create via _init_kaggle_env
        self._owns_kaggle_env = (kaggle_env is None)  # only close what we created
        self._current_obs = None
        self._step_count = 0
        self._episode_reward = 0.0
        self._won = False
        self._player_id = 0  # 我们控制的 player ID
        # Phase 2 reward state
        self._consecutive_safe = 0   # counter for inactivity penalty
        self._prev_opp_money = None   # opponent money for relative reward
        # Iter 2: track wheat for "real effect" check
        self._prev_wheat = None
        # ROI reward state: track net worth (cash + inventory value)
        self._initial_W = None        # initial net worth at episode start
        self._prev_W = None           # previous step net worth
        self._prev_W_opp = None       # opponent previous step net worth
        self._consecutive_idle = 0    # consecutive non-trade steps
        
    def _init_kaggle_env(self):
        """初始化 Kaggle 环境"""
        if self._kaggle_env is None:
            from kaggle_environments import make
            # 注意：使用 kagriculture (两个 g - kaggriculture)
            self._kaggle_env = make("kagriculture", debug=False)
            
    def reset(self, seed: Optional[int] = None, options: Optional[Dict] = None) -> Tuple[np.ndarray, Dict]:
        """Reset environment.

        Resets all episode-level state: step counter, episode reward, win flag,
        and previous-money baseline. Does NOT recreate the underlying Kaggle
        env (just calls kaggle_env.reset).
        """
        super().reset(seed=seed)
        self._init_kaggle_env()

        # 初始化
        self._kaggle_env.reset(num_agents=2)

        # 获取初始 observation
        raw_obs = self._kaggle_env.state[0].observation

        self._step_count = 0
        self._episode_reward = 0.0
        self._won = False  # fixed issue: stale state leak across episodes
        # Phase 2: reset inactivity counter and opponent money baseline
        self._consecutive_safe = 0
        self._prev_opp_money = None
        # Iter 2: reset wheat tracker
        self._prev_wheat = None
        # ROI reward: reset net worth trackers
        self._consecutive_idle = 0
        self._prev_W = None
        self._prev_W_opp = None
        self._initial_W = None

        # 获取玩家信息
        farm = raw_obs.farms[self._player_id]
        self._prev_money = farm.get("money", 0)

        # ── ROI reward: 计算初始净资产 W_0 ──
        market = raw_obs.market
        prices = market.get("prices", {})
        shed = raw_obs.private.shed if isinstance(raw_obs.private.shed, dict) else {}
        inventory_value = sum(count * prices.get(crop, 0) for crop, count in shed.items())
        self._initial_W = self._prev_money + inventory_value
        self._prev_W = self._initial_W

        # 对手初始净资产
        opp_id = 1 - self._player_id
        opp_farm = raw_obs.farms[opp_id]
        opp_money = opp_farm.get("money", 0)
        opp_shed = raw_obs.private.shed if isinstance(raw_obs.private.shed, dict) else {}
        opp_inventory_value = sum(count * prices.get(crop, 0) for crop, count in opp_shed.items())
        self._prev_W_opp = opp_money + opp_inventory_value

        # 处理 observation
        processed_obs = self._process_observation(raw_obs)

        return processed_obs, {}
    
    def _is_action_valid(self, action: int, raw_obs) -> bool:
        farm = raw_obs.farms[self._player_id]
        private = raw_obs.private
        shed = private.shed if isinstance(private.shed, dict) else {}
        market_inv = raw_obs.market.get("inventory", {})
        money = farm.get("money", 0)

        # 0: HOLD, 4: PASS 永远合法
        if action in [0, 4]:
            return True

        # 1: HIRE
        if action == 1:
            hires_left = farm.get("hires_today", 0)
            return hires_left > 0 and money >= 100

        # 2: SELL_WHEAT
        if action == 2:
            wheat_count = shed.get("WHEAT", 0)
            return wheat_count > 0

        # 3: BUY_PRODUCT_WHEAT
        if action == 3:
            market_prices = raw_obs.market.get("prices", {})
            wheat_price = market_prices.get("WHEAT", 0)
            market_wheat = market_inv.get("WHEAT", 0)
            return money >= wheat_price and wheat_price > 0 and market_wheat > 0

        return False

    def action_masks(self) -> np.ndarray:
        """Gymnasium ActionMask API: which actions are legal right now.

        Returns a (action_space.n,) int8 array where 1 = legal, 0 = illegal.
        Used by MaskablePPO (sb3-contrib) and any downstream consumer that
        wants to skip invalid actions.

        Note: regular SB3 PPO ignores this method — no behavioral change
        unless the consumer explicitly checks it or the policy is swapped
        for MaskablePPO.

        Safe to call before reset() returns: lazy-inits the kaggle_env.
        """
        self._init_kaggle_env()
        raw_obs = self._kaggle_env.state[0].observation
        mask = np.ones(self.action_space.n, dtype=np.int8)
        for a in range(self.action_space.n):
            if not self._is_action_valid(a, raw_obs):
                mask[a] = 0
        return mask
    
    def step(self, action: int) -> Tuple[np.ndarray, float, bool, bool, Dict]:
        """Take one step in the Kagriculture env.

        Returns Gymnasium 5-tuple: (obs, reward, terminated, truncated, info).
        - terminated: the Kaggle game itself ended (true game-end condition)
        - truncated: hit MAX_STEPS but the game is still going
        - info["won"]: True iff this episode ended with terminated AND p0_money > p1_money
        """
        # Guard: if the underlying kaggle env is already done (terminated
        # naturally OR truncated), don't call kaggle_env.step() again — it
        # raises "Environment done, reset required". SB3's VecEnv sometimes
        # re-calls step() before our reset completes; this guard short-
        # circuits to a done=True 5-tuple so the next call goes to reset().
        if self._kaggle_env is not None and self._kaggle_env.done:
            try:
                raw_obs = self._kaggle_env.state[0].observation
                processed_obs = self._process_observation(raw_obs)
            except Exception:
                processed_obs = np.zeros(
                    self.obs_processor.get_input_dim(), dtype=np.float32
                )
            return (
                processed_obs,
                0.0,
                True,
                False,
                {"won": self._won, "truncated_after_done": True},
            )

        # 获取执行前的原始状态
        raw_obs = self._kaggle_env.state[0].observation

        # 检查动作合法性
        is_valid = self._is_action_valid(action, raw_obs)
        invalid_penalty = 0.0

        if not is_valid:
            action_str = {}
            invalid_penalty = -0.05
        else:
            action_str = self._action_to_kaggle(action)

        opponent_action = self._get_opponent_action()

        self._kaggle_env.step([action_str, opponent_action])

        new_raw_obs = self._kaggle_env.state[0].observation

        reward, reward_info = self._compute_reward(
            new_raw_obs,
            action=action,
            is_valid=is_valid,
        )
        reward += invalid_penalty

        # Increment step first
        self._step_count += 1

        terminated = self._kaggle_env.done
        truncated = self._step_count >= MAX_STEPS
        done = terminated or truncated

        if terminated:
            # ROI-driven terminal reward:
            # sign * 1.5 + max(0, final_roi * 5.0)
            # - 躺赢 (win but roi≈0): only ~+1.5
            # - 翻倍 (roi=1.0, win): +1.5 + 5.0 = +6.5
            # - 大幅亏损 (lose): negative sign + negative roi
            W_t, W_opp_t = self._compute_net_worth(new_raw_obs)
            W_0 = self._initial_W if self._initial_W is not None else W_t
            W_0_safe = max(W_0, 1.0)
            final_roi = (W_t - W_0) / W_0_safe
            self._won = W_t > W_opp_t
            sign = 1.0 if self._won else -1.0
            terminal_reward = sign * 1.5 + max(0.0, final_roi * 5.0)
            reward += terminal_reward
        elif truncated:
            # Hit MAX_STEPS but the game is still going. Mark _won=False
            # (don't carry over from prior episode; reset() already handles
            # the start-of-episode case).
            self._won = False
        # else: episode continues, no terminal logic.

        processed_obs = self._process_observation(new_raw_obs)
        self._episode_reward += reward

        info = {
            "episode_reward": self._episode_reward,
            "step": self._step_count,
            "money": new_raw_obs.farms[self._player_id].get("money", 0),
            "won": self._won,
            "is_valid_action": is_valid,
            "action_mask": self.action_masks(),  # NEW: Gym ActionMask API, also visible in info
            **reward_info
        }

        return processed_obs, reward, terminated, truncated, info
    def _process_observation(self, raw_obs) -> np.ndarray:
        """将 Kaggle raw observation 转换为简化格式"""
        farm = raw_obs.farms[self._player_id]
        private = raw_obs.private
        
        # 构建简化 observation dict
        # 注意：private.shed 是 dict，private.inventories 是 list
        shed = private.shed if isinstance(private.shed, dict) else {}
        simple_obs = {
            "step": self._step_count,
            "day": raw_obs.day,
            "money": farm.get("money", 0),
            "market": {
                "prices": raw_obs.market.get("prices", {}),
                "inventory": raw_obs.market.get("inventory", {}),
            },
            "farm": {
                "plantable_tiles": self._count_plantable_tiles(farm),
                "plants_ready": self._count_plants_ready(farm),
                "total_plants": self._count_total_plants(farm),
                "weed_density": 0.0,
                "animals": self._count_animals(farm),
            },
            "private": {
                "hands": len(farm.get("hands", [])),
                "money": farm.get("money", 0),
                "wheat_in_shed": shed.get("WHEAT", 0),
                "fertilizer_in_shed": shed.get("FERTILIZER", 0),
                "hires_left": farm.get("hires_today", 0),
            },
            "opponent": self._estimate_opponent(raw_obs),
        }
        
        return self.obs_processor.process(simple_obs)
    
    def _count_plantable_tiles(self, farm) -> int:
        """计算可种植的 tile 数量"""
        tiles = farm.get("tiles", [])
        count = 0
        for row in tiles:
            for tile in row:
                # tile 可以是 None, "LOCKED", 或 dict
                if tile is None:
                    count += 1
                elif isinstance(tile, str) and tile == "empty":
                    count += 1
                elif isinstance(tile, dict) and (tile.get("crop") is None and tile.get("animal") is None):
                    count += 1
        return count
    
    def _count_plants_ready(self, farm) -> int:
        """计算已成熟可以收获的作物数量"""
        tiles = farm.get("tiles", [])
        count = 0
        for row in tiles:
            for tile in row:
                if isinstance(tile, dict) and tile.get("state") == "ready":
                    count += 1
        return count
    
    def _count_total_plants(self, farm) -> int:
        """计算总作物数量"""
        tiles = farm.get("tiles", [])
        count = 0
        for row in tiles:
            for tile in row:
                if isinstance(tile, dict) and tile.get("crop") is not None:
                    count += 1
        return count
    
    def _count_animals(self, farm) -> dict:
        """计算动物数量"""
        tiles = farm.get("tiles", [])
        cows = 0
        sheep = 0
        unfed = 0
        
        for row in tiles:
            for tile in row:
                if isinstance(tile, dict):
                    if tile.get("animal") == "cow":
                        cows += 1
                        if not tile.get("fed", True):
                            unfed += 1
                    elif tile.get("animal") == "sheep":
                        sheep += 1
                        if not tile.get("fed", True):
                            unfed += 1
        
        return {
            "cows": cows,
            "sheep": sheep,
            "unfed": unfed,
        }
    
    def _estimate_opponent(self, raw_obs) -> dict:
        """估算对手状态 (从可见信息)"""
        # 对手是 farms[1]
        if len(raw_obs.farms) > 1:
            opponent_farm = raw_obs.farms[1]
            return {
                "estimated_money": opponent_farm.get("money", 50000),
                "visible_plants": self._count_total_plants(opponent_farm),
                "visible_animals": self._count_animals(opponent_farm)["cows"] + 
                                   self._count_animals(opponent_farm)["sheep"],
            }
        return {
            "estimated_money": 50000.0,
            "visible_plants": 0,
            "visible_animals": 0,
        }
    
    def _action_to_kaggle(self, action: int) -> str:
        """将 internal action index 转换为 Kaggle action string"""
        # Phase 1: 5 个 action
        if action == 0:
            return {}  # HOLD - 空操作
        elif action == 1:
            return {"market": [["HIRE"]]}  # HIRE
        elif action == 2:
            return {"market": [["SELL", "WHEAT", 1]]}  # SELL_WHEAT
        elif action == 3:
            return {"market": [["BUY_PRODUCT", "WHEAT", 1]]}  # BUY_WHEAT
        elif action == 4:
            return {"farmer": ["PASS"]}  # PASS
        else:
            return {}
    
    def _get_opponent_action(self) -> str:
        """获取对手的 action"""
        if self.opponent == "random":
            import random
            actions = [
                {},                                              # HOLD
                {"market": [["HIRE"]]},                         # HIRE
                {"market": [["SELL", "WHEAT", 1]]},             # SELL_WHEAT
                {"farmer": ["PASS"]},                            # PASS
            ]
            return random.choice(actions)
        elif self.opponent == "trained":
            # 使用训练好的对手模型
            opponent_obs = self._get_opponent_obs()
            action_id = self._opponent_model.predict(opponent_obs)
            return self._action_id_to_kaggle(action_id)
        else:
            return {}

    def _action_id_to_kaggle(self, action_id: int) -> dict:
        """将动作ID转换为Kaggle格式"""
        action_map = {
            0: {},  # PASS/HOLD
            1: {"market": [["HIRE"]]},
            2: {"market": [["SELL", "WHEAT", 1]]},
            3: {"market": [["BUY_PRODUCT", "WHEAT", 1]]},
            4: {"market": [["BUY_SEED", "WHEAT", 1]]},
            5: {"market": [["BUY_ANIMAL", "COW", 1]]},
            6: {"farmer": ["FEED"]},
            7: {"farmer": ["FERTILIZE"]},
            8: {"farmer": ["WATER"]},
            9: {"farmer": ["HARVEST"]},
            10: {"farmer": ["PLANT", "WHEAT"]},
        }
        return action_map.get(action_id, {})


    def _to_dict(self, obj):
        if obj is None:
            return {}
        if isinstance(obj, dict):
            return obj
        if hasattr(obj, "__dict__"):
            return {k: self._to_dict(v) for k, v in obj.__dict__.items()}
        return obj

    def _get_opponent_obs(self):
        """获取对手(Player 1)的真实Observation (raw Struct, no dict wrapping).

        Returning the raw Struct avoids 4 dict()/dict-comp calls per step.
        OpponentModel._extract_features handles Struct attribute access.
        """
        return self._kaggle_env.state[1].observation

    def _compute_net_worth(self, raw_obs) -> Tuple[float, float]:
        """计算当前净资产 W_t 和对手净资产 W_opp_t.

        W_t = cash + Σ(inventory_i × price_i)
        避免重复计算，提取公共逻辑供 _compute_reward 和 reset 共用。
        """
        farm = raw_obs.farms[self._player_id]
        cash = farm.get("money", 0)
        market = raw_obs.market
        prices = market.get("prices", {})
        shed = raw_obs.private.shed if isinstance(raw_obs.private.shed, dict) else {}
        inventory_value = sum(count * prices.get(crop, 0) for crop, count in shed.items())
        W_t = cash + inventory_value

        opp_id = 1 - self._player_id
        opp_farm = raw_obs.farms[opp_id]
        opp_cash = opp_farm.get("money", 0)
        opp_shed = raw_obs.private.shed if isinstance(raw_obs.private.shed, dict) else {}
        opp_inventory_value = sum(count * prices.get(crop, 0) for crop, count in opp_shed.items())
        W_opp_t = opp_cash + opp_inventory_value

        return W_t, W_opp_t

    def _compute_reward(self, raw_obs, action, is_valid) -> Tuple[float, Dict]:
        """ROI 驱动 reward: 基于净资产变化率而非固定终止奖励.

        See docs/CHANGE_SPEC-roi-reward-20260811.md.

        Components:
        1. ROI reward: roi × 10.0 + relative_roi × 5.0
        2. Trade bonus: +0.02 for real net-worth effect
        3. Empty-trade penalty: -0.01 for trade-class action with no effect
        4. Inactivity penalty: -0.01*(n-5) capped at -0.10/step
        5. Clip: np.clip(reward, -5.0, 5.0)
        6. Terminal bonus (sign × 1.5 + max(0, final_roi × 5.0)) added in step()
        """
        farm = raw_obs.farms[self._player_id]
        current_money = farm.get("money", 0)
        agent_d = current_money - self._prev_money
        self._prev_money = current_money

        # Iter 2: track wheat for "real effect" detection
        current_wheat = raw_obs.private.shed.get("WHEAT", 0) if isinstance(raw_obs.private.shed, dict) else 0
        if self._prev_wheat is None:
            self._prev_wheat = current_wheat
        wheat_d = current_wheat - self._prev_wheat
        self._prev_wheat = current_wheat

        # Opponent money for relative reward
        opp_id = 1 - self._player_id
        opp_money_now = raw_obs.farms[opp_id].get("money", 0)
        if self._prev_opp_money is None:
            self._prev_opp_money = opp_money_now
        opp_d = opp_money_now - self._prev_opp_money
        self._prev_opp_money = opp_money_now

        if self.reward_type == "sparse":
            return 0.0, {"money_delta": agent_d, "opp_money_delta": opp_d,
                         "wheat_delta": wheat_d}

        # ── ROI reward computation ──
        W_t, W_opp_t = self._compute_net_worth(raw_obs)

        if self._prev_W is None:
            self._prev_W = W_t
        W_delta = W_t - self._prev_W
        self._prev_W = W_t

        if self._prev_W_opp is None:
            self._prev_W_opp = W_opp_t
        W_opp_delta = W_opp_t - self._prev_W_opp
        self._prev_W_opp = W_opp_t

        # Guard: if _initial_W is None (should not happen after reset), use W_t
        W_0 = self._initial_W if self._initial_W is not None else W_t
        W_0_safe = max(W_0, 1.0)  # avoid division by zero

        roi = W_delta / W_0_safe
        roi_relative = (W_delta - W_opp_delta) / W_0_safe

        # Real effect: net worth actually moved
        has_real_trade_effect = abs(W_delta) > 1e-5

        # 1. ROI reward (核心信号)
        reward = roi * 300.0 + roi_relative * 3.0

        # 2 & 3. Trade bonus + empty-trade penalty
        is_trade_action = action in [1, 2, 3]
        if is_trade_action and is_valid:
            if has_real_trade_effect:
                # Only executed trades clear the inactivity counter
                self._consecutive_idle = 0
                reward += 0.02
            else:
                # Null trade: format bug or market reject
                reward -= 0.01
        else:
            # HOLD, PASS, illegal → idle counter increments
            self._consecutive_idle += 1
            if is_trade_action and is_valid:
                # Trade-class action but invalid → extra penalty
                reward -= 0.01

        # 4. Inactivity penalty (gated on tradeable state)
        if self._consecutive_idle > 5 and self._has_tradeable_state(raw_obs):
            penalty = min(0.10, 0.01 * (self._consecutive_idle - 5))
            reward -= penalty

        # 5. Clip
        reward = float(np.clip(reward, -5.0, 5.0))

        return reward, {"W_delta": W_delta, "W_opp_delta": W_opp_delta,
                        "roi": roi, "money_delta": agent_d,
                        "opp_money_delta": opp_d, "wheat_delta": wheat_d}

    def _has_tradeable_state(self, raw_obs) -> bool:
        """True if agent CAN make a valid trade (has money ≥ HIRE cost OR wheat in shed).

        Inactivity penalty is only applied when this returns True — otherwise
        HOLD/PASS is the only legal action and should not be punished.
        """
        farm = raw_obs.farms[self._player_id]
        private = raw_obs.private
        shed = private.shed if isinstance(private.shed, dict) else {}
        money = farm.get("money", 0)
        wheat = shed.get("WHEAT", 0)
        return money >= 100 or wheat > 0

    def render(self, mode: str = "human"):
        pass

    def close(self):
        # Only drop the kaggle_env if we created it. If it was injected via
        # the constructor (shared between train and eval), don't null it out
        # — that would break the other env's reference. See P1-4 in
        # docs/REVIEW-env-shared-kaggle-env-20260810.md.
        if self._owns_kaggle_env:
            # kaggle_environments.Environment has no close() — drop the
            # reference and let GC clean up.
            self._kaggle_env = None


def register_kagriculture_env():
    gym.register(
        id="Kagriculture-v0",
        entry_point=KagricultureEnv,
    )


if __name__ == "__main__":
    register_kagriculture_env()
    env = gym.make("Kagriculture-v0")
    obs, info = env.reset()
    print(f"Initial obs shape: {obs.shape}")
    total_reward = 0
    for i in range(10):
        action = env.action_space.sample()
        obs, reward, done, trunc, info = env.step(action)
        total_reward += reward
        print(f"Step {i}: action={action}, reward={reward:.4f}, done={done}")
        if done:
            break
    print(f"Total reward: {total_reward:.4f}")
    env.close()
