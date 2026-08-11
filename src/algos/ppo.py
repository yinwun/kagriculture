"""
PPO Agent for Kagriculture

使用 Stable Baselines3 的 PPO 实现，包装成我们的接口。
"""

import torch
import numpy as np
from typing import Optional, Dict, Any
from stable_baselines3 import PPO
from stable_baselines3.common.callbacks import BaseCallback


class PPOAgent:
    """
    PPO Agent wrapper
    
    提供统一的训练和评估接口。
    """
    
    def __init__(
        self,
        env,
        model_config: Optional[Dict[str, Any]] = None,
        policy_config: Optional[Dict[str, Any]] = None,
        device: str = "auto",
    ):
        self.env = env
        
        default_model_config = {
            "learning_rate": 3e-4,
            "n_steps": 2048,
            "batch_size": 64,
            "n_epochs": 10,
            "gamma": 0.99,
            "gae_lambda": 0.95,
            "clip_range": 0.2,
            "ent_coef": 0.01,
            "vf_coef": 0.5,
            "max_grad_norm": 0.5,
        }
        
        default_policy_config = {
            "obs_dim": env.observation_space.shape[0],
            "action_dim": env.action_space.n,
            "hidden_dim": 128,
        }
        
        self.model_config = {**default_model_config, **(model_config or {})}
        self.policy_config = {**default_policy_config, **(policy_config or {})}
        
        self._create_model(device)
        
    def _create_model(self, device: str):
        """创建 PPO 模型"""
        from stable_baselines3.common.policies import ActorCriticPolicy
        
        self.model = PPO(
            policy=ActorCriticPolicy,
            env=self.env,
            learning_rate=self.model_config["learning_rate"],
            n_steps=self.model_config["n_steps"],
            batch_size=self.model_config["batch_size"],
            n_epochs=self.model_config["n_epochs"],
            gamma=self.model_config["gamma"],
            gae_lambda=self.model_config["gae_lambda"],
            clip_range=self.model_config["clip_range"],
            ent_coef=self.model_config["ent_coef"],
            vf_coef=self.model_config["vf_coef"],
            max_grad_norm=self.model_config["max_grad_norm"],
            verbose=1,
            device=device,
        )
    
    def learn(
        self,
        total_timesteps: int,
        callback: Optional[BaseCallback] = None,
        log_interval: int = 1,
        tb_log_name: str = "PPO",
        reset_num_timesteps: bool = False,
    ) -> "PPOAgent":
        """
        训练模型
        """
        self.model.learn(
            total_timesteps=total_timesteps,
            callback=callback,
            log_interval=log_interval,
            tb_log_name=tb_log_name,
            reset_num_timesteps=reset_num_timesteps,
        )
        return self
    
    def predict(self, obs: np.ndarray, deterministic: bool = False) -> tuple:
        """预测 action"""
        return self.model.predict(obs, deterministic=deterministic)
    
    def save(self, path: str):
        """保存模型"""
        self.model.save(path)
        print(f"Model saved to {path}")
    
    @classmethod
    def load(cls, path: str, env, device: str = "auto") -> "PPOAgent":
        """加载模型"""
        agent = cls.__new__(cls)
        agent.env = env
        agent.model = PPO.load(path, env=env, device=device)
        return agent


class EvalCallback(BaseCallback):
    """定期评估的回调"""
    
    def __init__(
        self,
        eval_env,
        n_eval_episodes: int = 10,
        eval_freq: int = 10000,
        verbose: int = 1,
    ):
        super().__init__(verbose)
        self.eval_env = eval_env
        self.n_eval_episodes = n_eval_episodes
        self.eval_freq = eval_freq
        self.last_win_rate = 0.0
        self.last_mean_reward = 0.0
        
    def _on_step(self) -> bool:
        if self.num_timesteps % self.eval_freq == 0:
            self._eval()
        return True
    
    def _eval(self):
        """执行评估"""
        wins = 0
        total_reward = 0
        
        for _ in range(self.n_eval_episodes):
            obs, _ = self.eval_env.reset()
            done = False
            episode_reward = 0
            
            while not done:
                action, _ = self.model.predict(obs, deterministic=True)
                obs, reward, done, _, info = self.eval_env.step(action)
                episode_reward += reward
            
            total_reward += episode_reward
            if info.get("won", False):
                wins += 1
        
        self.last_win_rate = wins / self.n_eval_episodes
        self.last_mean_reward = total_reward / self.n_eval_episodes
        
        print(f"Eval at {self.num_timesteps} steps: Win rate: {self.last_win_rate:.2%}, Mean reward: {self.last_mean_reward:.4f}")


if __name__ == "__main__":
    import gymnasium as gym
    
    class MockEnv(gym.Env):
        def __init__(self):
            self.observation_space = gym.spaces.Box(low=-1, high=2, shape=(32,))
            self.action_space = gym.spaces.Discrete(5)
            
        def reset(self):
            return self.observation_space.sample(), {}
        
        def step(self, action):
            obs = self.observation_space.sample()
            reward = np.random.randn()
            done = np.random.rand() < 0.1
            return obs, reward, done, False, {}
    
    env = MockEnv()
    agent = PPOAgent(env)
    agent.learn(total_timesteps=1000)
    print("Training complete")
