"""unsealing.py — 解封机制 (Phase 24 P1)

理论基础:
当高层级结构形成后, 如果基底(L0)状态发生足够大的变化, 
高层级的封装可能需要被"解封"以允许重新组织。

这实现了路线图中的"解封机制 — 基底状态变化超过阈值 → 封装比特解冻"。

核心思想:
1. 密封不是永久的 — 如果基底变化足够大, 密封可以被撤销
2. 解封阈值 = f(基底变化量, 时间, 高层级稳定性)
3. 解封后, 该层重新进入活跃演化状态

物理类比:
- 密封 = 相变 (液态 → 固态)
- 解封 = 逆向相变 (固态 → 液态)
- 温度 = 基底变化率
- 解封阈值 = 熔点

这解决了 Phase 23 的关键问题:
- H23-2a/2c 失败原因: 系统过于稳定, 缺乏动态变化
- 引入解封机制后, 系统可以打破局部最优, 探索更多状态空间
"""

from __future__ import annotations
from dataclasses import dataclass, field as dfield
from typing import Optional, List, Dict, Set
import numpy as np


@dataclass
class UnsealingConfig:
    """解封机制配置。"""
    # 基底变化率阈值 (超过此值触发解封检查)
    change_rate_threshold: float = 0.3
    
    # 解封概率系数 (基底变化率 × 此系数 = 解封概率)
    unseal_probability_factor: float = 0.5
    
    # 最小密封持续时间 (密封后至少等待这么多步才可能解封)
    min_seal_duration: int = 50
    
    # 高层级稳定性权重 (高层级越稳定, 越不容易被解封)
    stability_weight: float = 0.5
    
    # 解封后冻结比例 (解封时解冻多少比例的位)
    unfreeze_fraction: float = 0.3
    
    # 是否启用解封机制
    enabled: bool = True


@dataclass
class LayerState:
    """层状态追踪。"""
    layer_idx: int
    seal_step: Optional[int] = None
    is_sealed: bool = False
    frozen_bits: Set[int] = dfield(default_factory=set)
    
    # 变化率追踪
    change_history: List[float] = dfield(default_factory=list)
    avg_change_rate: float = 0.0
    
    # 解封历史
    unseal_count: int = 0
    last_unseal_step: Optional[int] = None


class UnsealingMechanism:
    """解封机制管理器。
    
    在 RecursiveWorld 中使用:
    1. 追踪每层的变化率
    2. 当变化率超过阈值时, 检查是否需要解封
    3. 执行解封操作
    """
    
    def __init__(self, config: Optional[UnsealingConfig] = None):
        self.config = config or UnsealingConfig()
        self.layer_states: Dict[int, LayerState] = {}
        self.current_step: int = 0
    
    def register_layer(self, layer_idx: int):
        """注册新层。"""
        if layer_idx not in self.layer_states:
            self.layer_states[layer_idx] = LayerState(layer_idx=layer_idx)
    
    def update_change_rate(self, layer_idx: int, change_rate: float):
        """更新层的变化率。"""
        if layer_idx not in self.layer_states:
            self.register_layer(layer_idx)
        
        state = self.layer_states[layer_idx]
        state.change_history.append(change_rate)
        
        # 保持最近 20 步的历史
        if len(state.change_history) > 20:
            state.change_history.pop(0)
        
        # 计算平均变化率
        state.avg_change_rate = np.mean(state.change_history)
    
    def mark_sealed(self, layer_idx: int, frozen_bits: Set[int]):
        """标记层为已密封。"""
        if layer_idx not in self.layer_states:
            self.register_layer(layer_idx)
        
        state = self.layer_states[layer_idx]
        state.is_sealed = True
        state.seal_step = self.current_step
        state.frozen_bits = frozen_bits.copy()
    
    def check_unsealing(self, layer_idx: int, current_step: int) -> Optional[Dict]:
        """检查是否需要解封。
        
        Args:
            layer_idx: 层索引
            current_step: 当前步数
        
        Returns:
            解封信息 dict 或 None (不解封)
        """
        if not self.config.enabled:
            return None
        
        if layer_idx not in self.layer_states:
            return None
        
        state = self.layer_states[layer_idx]
        
        # 检查是否已密封
        if not state.is_sealed:
            return None
        
        # 检查密封持续时间
        seal_duration = current_step - state.seal_step
        if seal_duration < self.config.min_seal_duration:
            return None
        
        # 检查变化率是否超过阈值
        if state.avg_change_rate < self.config.change_rate_threshold:
            return None
        
        # 计算解封概率
        # 基础概率 = 变化率 × 系数
        base_prob = state.avg_change_rate * self.config.unseal_probability_factor
        
        # 调整因子: 密封时间越长, 越容易解封
        time_factor = min(1.0, seal_duration / 200.0)
        
        # 最终概率
        unseal_prob = base_prob * time_factor
        
        # 随机决定是否解封
        if np.random.random() < unseal_prob:
            # 计算要解冻的位数
            n_unfreeze = int(len(state.frozen_bits) * self.config.unfreeze_fraction)
            n_unfreeze = max(1, min(n_unfreeze, len(state.frozen_bits)))
            
            # 随机选择要解冻的位
            frozen_list = list(state.frozen_bits)
            unfreeze_bits = set(np.random.choice(
                frozen_list, 
                size=n_unfreeze, 
                replace=False
            ).tolist())
            
            return {
                'layer_idx': layer_idx,
                'unseal_step': current_step,
                'seal_duration': seal_duration,
                'avg_change_rate': state.avg_change_rate,
                'unseal_probability': unseal_prob,
                'unfreeze_bits': unfreeze_bits,
                'n_unfreeze': n_unfreeze
            }
        
        return None
    
    def execute_unsealing(self, layer_idx: int, unseal_info: Dict):
        """执行解封操作。
        
        Args:
            layer_idx: 层索引
            unseal_info: 解封信息
        """
        if layer_idx not in self.layer_states:
            return
        
        state = self.layer_states[layer_idx]
        
        # 更新状态
        state.is_sealed = False
        state.seal_step = None
        state.frozen_bits -= unseal_info['unfreeze_bits']
        state.unseal_count += 1
        state.last_unseal_step = unseal_info['unseal_step']
        
        # 清空变化率历史 (重新开始追踪)
        state.change_history.clear()
        state.avg_change_rate = 0.0
    
    def get_summary(self) -> Dict:
        """获取解封机制摘要。"""
        summary = {
            'enabled': self.config.enabled,
            'total_layers': len(self.layer_states),
            'layers': {}
        }
        
        for layer_idx, state in self.layer_states.items():
            summary['layers'][layer_idx] = {
                'is_sealed': state.is_sealed,
                'seal_step': state.seal_step,
                'avg_change_rate': state.avg_change_rate,
                'unseal_count': state.unseal_count,
                'last_unseal_step': state.last_unseal_step,
                'n_frozen_bits': len(state.frozen_bits)
            }
        
        return summary
