"""对手模型推理"""

import os
import numpy as np
import joblib
from collections import Counter

# Pre-allocated feature buffer (35 floats: 2 time + 6 prices + 6 inv + 8 shed
# + 5 seeds + 2 farm + 6 misc = 35). Allocated once, reused every step.
_N_FEATURES = 35
_FEATURE_BUF = np.zeros(_N_FEATURES, dtype=np.float32)


class _TreeNode:
    """Caches tree internals as flat numpy arrays for fast in-process traversal.

    Built from sklearn.tree_.DecisionTreeClassifier.tree_ once at load time.
    Avoids sklearn.predict_proba's per-call narwhals validation overhead
    (~5-10 ms per tree * 100 trees = ~500-1000 ms per env step).
    """
    __slots__ = ("children_left", "children_right", "feature", "threshold", "value")

    def __init__(self, sklearn_tree_struct):
        self.children_left = sklearn_tree_struct.children_left.astype(np.int32)
        self.children_right = sklearn_tree_struct.children_right.astype(np.int32)
        self.feature = sklearn_tree_struct.feature.astype(np.int32)
        self.threshold = sklearn_tree_struct.threshold.astype(np.float32)
        # value shape: (n_nodes, 1, n_classes) — squeeze to (n_nodes, n_classes)
        self.value = sklearn_tree_struct.value.reshape(
            sklearn_tree_struct.value.shape[0], -1
        ).astype(np.float32)


def _traverse_one(node: _TreeNode, x: np.ndarray) -> np.ndarray:
    """Walk a single tree, return the class-value vector at the leaf."""
    cl = node.children_left
    cr = node.children_right
    feat = node.feature
    thr = node.threshold
    val = node.value
    cur = 0
    # Trees have depth ≤ max_depth=15 → ≤15 iterations per sample.
    while cl[cur] != -1:
        f = feat[cur]
        if x[f] <= thr[cur]:
            cur = cl[cur]
        else:
            cur = cr[cur]
    return val[cur]


class OpponentModel:
    def __init__(self, model_path=None):
        self.model = None
        self.model_path = model_path or "models/opponent_model.joblib"
        self._nodes = None       # list of _TreeNode, preprocessed once
        self._n_classes = None

    def load(self):
        if self.model is None:
            self.model = joblib.load(self.model_path)
            # Preprocess every tree's internal arrays once
            self._nodes = [
                _TreeNode(t.tree_) for t in self.model.estimators_
            ]
            self._n_classes = self.model.n_classes_
        return self

    def predict(self, obs):
        """给定observation，返回预测的动作ID

        Manual tree traversal (no sklearn predict_proba). For 100 trees with
        depth ≤ 15, this is ~10x faster than RF.predict because it skips
        sklearn's parallel wrapper, warnings filter, narwhals is_fitted
        checks, and the inner predict_proba validation.
        """
        if self.model is None:
            self.load()
        x = self._extract_features(obs)
        proba = np.zeros(self._n_classes, dtype=np.float32)
        for node in self._nodes:
            proba += _traverse_one(node, x)
        return int(np.argmax(proba))

    def _extract_features(self, obs):
        """从observation提取特征（需要和extract.py一致）

        Accepts either a raw Kaggle Struct (preferred — no dict wrapping
        needed) or a plain dict. Writes into a pre-allocated buffer to avoid
        per-step allocation.
        """
        buf = _FEATURE_BUF
        i = 0
        # Time
        buf[i] = obs.get("day", 0) / 30.0; i += 1
        buf[i] = obs.get("hour", 0) / 24.0; i += 1

        market = obs.get("market", {})
        # Struct supports .get via attribute access — but if a real dict was
        # passed (e.g. from extract.py on JSON replays), this also works.
        prices = market.get("prices", {}) if hasattr(market, "get") else market.prices
        for item in ("WHEAT", "CARROT", "TOMATO", "MILK", "EGG", "WOOL"):
            buf[i] = (prices.get(item, 0) if hasattr(prices, "get")
                      else getattr(prices, item, 0)) / 300.0
            i += 1

        inventory = market.get("inventory", {}) if hasattr(market, "get") else market.inventory
        for item in ("WHEAT", "CARROT", "TOMATO", "MILK", "EGG", "WOOL"):
            buf[i] = (inventory.get(item, 0) if hasattr(inventory, "get")
                      else getattr(inventory, item, 0)) / 10000.0
            i += 1

        private = obs.get("private", {})
        shed = private.get("shed", {}) if hasattr(private, "get") else private.shed
        for item in ("WHEAT", "CARROT", "TOMATO", "MILK", "EGG", "WOOL", "COW", "SHEEP"):
            buf[i] = (shed.get(item, 0) if hasattr(shed, "get")
                      else getattr(shed, item, 0)) / 100.0
            i += 1

        seeds = (private.get("seeds", {}) if hasattr(private, "get")
                 else getattr(private, "seeds", {}))
        for crop in ("WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON"):
            buf[i] = (seeds.get(crop, 0) if hasattr(seeds, "get")
                      else getattr(seeds, crop, 0)) / 50.0
            i += 1

        # farms: prefer the index from obs["player"] (dynamic player_id, see
        # extract.py) but fall back to farms[0] for the dict-from-replay case.
        farms = obs.get("farms", [])
        player_id = obs.get("player", 0)
        if farms and len(farms) > player_id:
            f = farms[player_id]
            buf[i] = (f.get("money", 0) if hasattr(f, "get")
                      else getattr(f, "money", 0)) / 100000.0
            i += 1
            buf[i] = (f.get("hires_today", 0) if hasattr(f, "get")
                      else getattr(f, "hires_today", 0)) / 5.0
            i += 1
        else:
            buf[i] = 0.0; i += 1
            buf[i] = 0.0; i += 1

        # Return a slice copy so the buffer can be reused next call
        return buf[:i].copy()

# 动作ID到动作名称的映射
ACTION_ID_TO_NAME = {
    0: "PASS",
    1: "HIRE",
    2: "SELL",
    3: "BUY_PRODUCT",
    4: "BUY_SEED",
    5: "BUY_ANIMAL",
    6: "FEED",
    7: "FERTILIZE",
    8: "WATER",
    9: "HARVEST",
    10: "PLANT",
    11: "OTHER",
}

def predict_opponent_action(obs, model_path="models/opponent_model.joblib"):
    """便捷函数：给定observation，返回对手动作"""
    model = OpponentModel(model_path)
    action_id = model.predict(obs)
    return ACTION_ID_TO_NAME.get(action_id, "PASS")
