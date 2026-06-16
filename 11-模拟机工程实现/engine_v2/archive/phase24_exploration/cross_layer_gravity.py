"""cross_layer_gravity.py — 跨层级引力调制 (Phase 24)

理论基础:
当低层级 L_k 密封后, 其组织结构形成一个"引力场", 影响高层级 L_{k+1} 的动力学。
这实现了路线图中的"跨层级引力调制 — 低层级结构约束高层级演化"。

核心思想:
1. 高层级组织的"质量" = 该组织包含的活跃位数量 × 绑定密度
2. 高层级组织对低层级的"引力" ∝ 质量 / 距离² (距离 = 层级差)
3. 引力调制低层级的:
   - a1_source 权重: 高引力区域更容易成为差异源
   - binding 增强: 高引力区域的绑定增强更快
   - 方向偏置: 高引力区域的流向偏置

物理类比:
- 高层级组织 = 大质量天体
- 低层级位 = 受引力影响的粒子
- 引力 = 跨层级约束力

这解决了 Phase 23 的关键问题:
- H23-4a/4b 失败原因: 叙事递归没有跨层级反馈, 高层级对低层级无影响
- 引入引力调制后, 高层级结构可以约束低层级演化, 可能提升涌现质量
"""

from __future__ import annotations
from dataclasses import dataclass, field as dfield
from typing import Optional, List, Dict, Set
import numpy as np


@dataclass
class GravityConfig:
    """跨层级引力配置。"""
    # 引力强度系数
    gravity_strength: float = 0.5
    
    # 引力衰减模式: 'inverse_square' | 'exponential' | 'linear'
    decay_mode: str = 'inverse_square'
    
    # 指数衰减率 (仅用于 exponential 模式)
    decay_rate: float = 0.5
    
    # 最大影响层级数 (引力最多影响几层以下)
    max_influence_depth: int = 3
    
    # 引力调制模式:
    # 'source_weight' - 调制 a1_source 权重
    # 'binding_boost' - 调制绑定增强
    # 'direction_bias' - 调制流向偏置
    # 'all' - 同时调制所有
    modulation_mode: str = 'all'
    
    # 源权重调制强度
    source_weight_factor: float = 0.3
    
    # 绑定增强调制强度
    binding_boost_factor: float = 0.2
    
    # 流向偏置强度
    direction_bias_factor: float = 0.1


@dataclass
class OrganizationGravity:
    """单个组织的引力场。"""
    org_id: str
    org_bits: Set[int]  # 组织包含的位
    layer: int  # 所在层级
    
    # 引力属性
    mass: float = 0.0  # 质量 = 活跃位数 × 绑定密度
    center_bit: int = -1  # 组织中心位 (绑定最密集的位)
    
    # 引力场 (对低层级的影响)
    influenced_bits: Dict[int, float] = dfield(default_factory=dict)  # bit -> gravity_strength


class CrossLayerGravity:
    """跨层级引力调制器。
    
    在 RecursiveWorld 中使用:
    1. 当高层级密封时, 计算其组织的引力场
    2. 在低层级运行时, 用引力场调制动力学
    """
    
    def __init__(self, config: Optional[GravityConfig] = None):
        self.config = config or GravityConfig()
        self.gravity_fields: List[OrganizationGravity] = []  # 所有引力场
        self.layer_gravity: Dict[int, List[OrganizationGravity]] = {}  # 每层的引力场
    
    def compute_gravity(self, layer_idx: int, organizations: Dict[str, Set[int]], 
                       binding: np.ndarray, state: np.ndarray) -> List[OrganizationGravity]:
        """计算某层组织的引力场。
        
        Args:
            layer_idx: 层级索引
            organizations: 组织字典 {org_id: set(bits)}
            binding: 绑定矩阵
            state: 状态向量
        
        Returns:
            引力场列表
        """
        gravity_fields = []
        
        for org_id, org_bits in organizations.items():
            if len(org_bits) < 2:
                continue
            
            # 计算组织质量
            org_list = list(org_bits)
            n_active = sum(1 for b in org_list if state[b] == 1)
            
            # 绑定密度 = 平均绑定强度
            if len(org_list) > 1:
                sub_binding = binding[np.ix_(org_list, org_list)]
                binding_density = np.mean(sub_binding)
            else:
                binding_density = 0.0
            
            mass = n_active * (1.0 + binding_density)
            
            # 找中心位 (绑定最密集的位)
            if len(org_list) > 1:
                binding_sums = binding[org_list, :][:, org_list].sum(axis=1)
                center_idx = np.argmax(binding_sums)
                center_bit = org_list[center_idx]
            else:
                center_bit = org_list[0]
            
            # 创建引力场
            gravity = OrganizationGravity(
                org_id=org_id,
                org_bits=org_bits,
                layer=layer_idx,
                mass=mass,
                center_bit=center_bit
            )
            gravity.layer_size = len(state)  # 存储层级大小用于距离计算
            
            gravity_fields.append(gravity)
        
        # 存储
        self.layer_gravity[layer_idx] = gravity_fields
        self.gravity_fields.extend(gravity_fields)
        
        return gravity_fields
    
    def compute_influence(self, target_layer: int, target_bits: np.ndarray, 
                        source_layer: Optional[int] = None) -> Dict[int, float]:
        """计算低层级引力对目标层各位的影响 (bottom-up)。
        
        Args:
            target_layer: 目标层级 (高层级)
            target_bits: 目标层的状态向量
            source_layer: 指定引力源层级 (如果为 None, 使用所有低层级)
        
        Returns:
            影响字典 {bit: gravity_strength}
        """
        influence = {}
        
        for src_layer, gravities in self.layer_gravity.items():
            # 如果指定了源层级, 只使用该层
            if source_layer is not None and src_layer != source_layer:
                continue
            
            # 计算层级差: src_layer 是低层级, target_layer 是高层级
            # 我们需要 src_layer < target_layer (低层级影响高层级)
            layer_diff = target_layer - src_layer
            
            # 只有低层级影响高层级 (layer_diff > 0 表示 target 比 source 高)
            if layer_diff <= 0 or layer_diff > self.config.max_influence_depth:
                continue
            
            for gravity in gravities:
                # 计算衰减
                if self.config.decay_mode == 'inverse_square':
                    decay = 1.0 / (layer_diff ** 2)
                elif self.config.decay_mode == 'exponential':
                    decay = np.exp(-self.config.decay_rate * layer_diff)
                else:  # linear
                    decay = 1.0 / layer_diff
                
                # 引力强度 = 质量 × 衰减 × 系数
                strength = gravity.mass * decay * self.config.gravity_strength
                
                # 计算对目标层各位的影响
                # 基于目标位与引力源中心的"距离"
                # 使用模运算来创建周期性引力场 (因为层级大小不同)
                target_N = len(target_bits)
                for bit in range(target_N):
                    # 计算位与引力源中心的距离 (模运算处理不同层级大小)
                    center_norm = gravity.center_bit / max(1, gravity.layer_size) if hasattr(gravity, 'layer_size') else 0.5
                    target_norm = bit / max(1, target_N)
                    dist = abs(center_norm - target_norm)
                    # 距离越近, 引力越强 (使用高斯衰减)
                    import math
                    influence_factor = math.exp(-(dist ** 2) / 0.1)  # 高斯衰减
                    if bit not in influence:
                        influence[bit] = 0.0
                    influence[bit] += strength * influence_factor
        
        return influence
    
    def modulate_source_weights(self, a1_source: Set[int], influence: Dict[int, float]) -> Dict[int, float]:
        """调制 a1_source 权重。
        
        高引力区域更容易成为差异源。
        
        Args:
            a1_source: 差异源集合
            influence: 引力影响字典
        
        Returns:
            调制后的源权重 {bit: weight}
        """
        weights = {}
        for bit in a1_source:
            base_weight = 1.0
            if bit in influence:
                # 引力增强源权重
                base_weight += influence[bit] * self.config.source_weight_factor
            weights[bit] = base_weight
        return weights
    
    def modulate_binding(self, binding: np.ndarray, influence: Dict[int, float]) -> np.ndarray:
        """调制绑定增强。
        
        高引力区域的绑定增强更快。
        
        Args:
            binding: 绑定矩阵
            influence: 引力影响字典
        
        Returns:
            调制后的绑定矩阵 (不修改原矩阵)
        """
        modulated = binding.copy()
        
        for bit, strength in influence.items():
            if bit < len(binding):
                # 增强该位与其他位的绑定
                boost = strength * self.config.binding_boost_factor
                modulated[bit, :] += boost
                modulated[:, bit] += boost
        
        # 保持在合理范围内
        np.clip(modulated, 0.0, 10.0, out=modulated)
        
        return modulated
    
    def modulate_direction(self, direction: np.ndarray, influence: Dict[int, float]) -> np.ndarray:
        """调制流向偏置。
        
        高引力区域的流向偏置更明显。
        
        Args:
            direction: 流向向量
            influence: 引力影响字典
        
        Returns:
            调制后的流向向量 (不修改原向量)
        """
        modulated = direction.copy()
        
        for bit, strength in influence.items():
            if bit < len(direction):
                # 增强流向偏置
                bias = strength * self.config.direction_bias_factor
                if direction[bit] == 0:
                    # 双向位: 根据引力方向偏置
                    # 这里简化: 引力使位更倾向于注入 (0->1)
                    modulated[bit] = min(1, int(bias))
                elif direction[bit] == 1:
                    # 注入位: 增强注入倾向
                    modulated[bit] = 1
                # 衰减位保持不变
        
        return modulated
    
    def get_summary(self) -> Dict:
        """获取引力场摘要。"""
        summary = {
            'n_gravity_fields': len(self.gravity_fields),
            'layers': {}
        }
        
        for layer_idx, gravities in self.layer_gravity.items():
            layer_summary = {
                'n_organizations': len(gravities),
                'total_mass': sum(g.mass for g in gravities),
                'organizations': []
            }
            for g in gravities:
                layer_summary['organizations'].append({
                    'org_id': g.org_id,
                    'mass': g.mass,
                    'n_bits': len(g.org_bits),
                    'center_bit': g.center_bit
                })
            summary['layers'][layer_idx] = layer_summary
        
        return summary


class GravityModulatedLayer:
    """引力调制的层包装器。
    
    在 Layer 运行时, 用引力场调制动力学参数。
    """
    
    def __init__(self, layer, gravity: CrossLayerGravity):
        self.layer = layer
        self.gravity = gravity
        self._influence = None
    
    def compute_influence(self):
        """计算引力影响。"""
        self._influence = self.gravity.compute_influence(
            self.layer.field.layer,
            self.layer.field.state
        )
        return self._influence
    
    def get_modulated_params(self):
        """获取引力调制后的参数。"""
        if self._influence is None:
            self.compute_influence()
        
        return {
            'source_weights': self.gravity.modulate_source_weights(
                self.layer.field.a1_source, self._influence
            ),
            'binding': self.gravity.modulate_binding(
                self.layer.field.binding, self._influence
            ),
            'direction': self.gravity.modulate_direction(
                self.layer.field.direction, self._influence
            )
        }
