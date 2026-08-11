"""
Multi-Head Policy Network for Kagriculture

使用独立的 head 处理不同的 action types:
- Market head: HIRE, SELL, BUY_PRODUCT
- Farmer head: movement, farming actions
- Hands head: 每个 hand 的动作
"""

import torch
import torch.nn as nn
from typing import Tuple, Dict, Any


class MultiHeadPolicy(nn.Module):
    """
    多头 Policy Network
    
    共享 encoder + 多个 task-specific heads
    """
    
    def __init__(
        self,
        obs_dim: int,
        action_dims: Dict[str, int],
        hidden_dim: int = 256,
    ):
        super().__init__()
        
        self.obs_dim = obs_dim
        self.action_dims = action_dims
        self.hidden_dim = hidden_dim
        
        # 共享 encoder
        self.encoder = nn.Sequential(
            nn.Linear(obs_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, hidden_dim),
            nn.ReLU(),
        )
        
        # Market head (Phase 1: 5 actions)
        self.market_head = nn.Sequential(
            nn.Linear(hidden_dim, 128),
            nn.ReLU(),
            nn.Linear(128, action_dims.get("market", 5)),
        )
        
        # Farmer head (Phase 1: 5 actions)
        self.farmer_head = nn.Sequential(
            nn.Linear(hidden_dim, 128),
            nn.ReLU(),
            nn.Linear(128, action_dims.get("farmer", 5)),
        )
        
        # Value function (shared)
        self.value_head = nn.Sequential(
            nn.Linear(hidden_dim, 128),
            nn.ReLU(),
            nn.Linear(128, 1),
        )
    
    def forward(self, obs: torch.Tensor) -> Tuple[Dict[str, torch.Tensor], torch.Tensor]:
        """
        Forward pass
        
        Args:
            obs: observation tensor, shape (batch, obs_dim)
            
        Returns:
            action_logits: dict of action logits for each head
            value: state value estimate
        """
        # 编码
        hidden = self.encoder(obs)
        
        # 计算 logits
        action_logits = {
            "market": self.market_head(hidden),
            "farmer": self.farmer_head(hidden),
        }
        
        # Value estimate
        value = self.value_head(hidden)
        
        return action_logits, value
    
    def get_action(
        self,
        obs: torch.Tensor,
        deterministic: bool = False,
    ) -> Tuple[Dict[str, int], torch.Tensor, torch.Tensor]:
        """
        从 observation 获取 action
        
        Args:
            obs: observation tensor
            deterministic: 如果 True，使用贪心策略
            
        Returns:
            actions: dict of action indices
            log_probs: log probabilities of actions
            values: state values
        """
        action_logits, value = self.forward(obs)
        
        actions = {}
        log_probs = {}
        
        for head_name, logits in action_logits.items():
            if deterministic:
                actions[head_name] = logits.argmax(dim=-1)
            else:
                probs = torch.softmax(logits, dim=-1)
                dist = torch.distributions.Categorical(probs)
                actions[head_name] = dist.sample()
                log_probs[head_name] = dist.log_prob(actions[head_name])
        
        return actions, log_probs, value


class SimplePolicy(nn.Module):
    """
    简化版 Policy Network (Phase 1 使用)
    
    单头输出 + value function
    """
    
    def __init__(
        self,
        obs_dim: int,
        action_dim: int,
        hidden_dim: int = 128,
    ):
        super().__init__()
        
        self.obs_dim = obs_dim
        self.action_dim = action_dim
        self.hidden_dim = hidden_dim
        
        # 共享 encoder
        self.network = nn.Sequential(
            nn.Linear(obs_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, hidden_dim),
            nn.ReLU(),
        )
        
        # Policy head
        self.policy_head = nn.Linear(hidden_dim, action_dim)
        
        # Value head
        self.value_head = nn.Sequential(
            nn.Linear(hidden_dim, 64),
            nn.ReLU(),
            nn.Linear(64, 1),
        )
    
    def forward(self, obs: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        Forward pass
        
        Args:
            obs: observation tensor, shape (batch, obs_dim)
            
        Returns:
            logits: action logits, shape (batch, action_dim)
            value: state value, shape (batch, 1)
        """
        hidden = self.network(obs)
        logits = self.policy_head(hidden)
        value = self.value_head(hidden)
        
        return logits, value
    
    def get_action(
        self,
        obs: torch.Tensor,
        deterministic: bool = False,
    ) -> Tuple[int, torch.Tensor, torch.Tensor]:
        """
        获取单个 action
        
        Args:
            obs: observation tensor (single step, shape (obs_dim,))
            deterministic: 如果 True，使用贪心策略
            
        Returns:
            action: action index
            log_prob: log probability of action
            value: state value
        """
        obs = obs.unsqueeze(0)  # 添加 batch 维度
        logits, value = self.forward(obs)
        
        if deterministic:
            action = logits.argmax(dim=-1).item()
            log_prob = None
        else:
            probs = torch.softmax(logits, dim=-1)
            dist = torch.distributions.Categorical(probs)
            action = dist.sample().item()
            log_prob = dist.log_prob(torch.tensor(action))
        
        return action, log_prob, value.item()


if __name__ == "__main__":
    # 测试
    obs_dim = 32
    action_dim = 5
    
    policy = SimplePolicy(obs_dim, action_dim)
    
    # 随机 obs
    obs = torch.randn(obs_dim)
    
    action, log_prob, value = policy.get_action(obs)
    print(f"Action: {action}, Value: {value:.4f}")
    
    # Batch 测试
    batch_obs = torch.randn(32, obs_dim)
    logits, values = policy(batch_obs)
    print(f"Batch logits shape: {logits.shape}, values shape: {values.shape}")
