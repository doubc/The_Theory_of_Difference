"""
engine/cross_layer_gravity.py — 跨层级引力调制

理论依据：
《差异论》§4.2 "引力势是层级间的媒介场"
高层级的演化不是孤立的——它受到低层级冻结比特质量分布的引力调制。

实现原理：
1. 从每一层计算"引力势场"（冻结且激活的比特作为质量源）
2. 引力势通过封装映射投影到上一层
3. 投影后的引力势调制上一层的源/汇注入强度
   - 正引力势 → 该区域更容易被注入（质量吸引）
   - 负引力势 → 该区域更容易被吸收（质量排斥）
4. 调制强度随层级距离衰减（1/d^2 律）

与 BiasField 的区别：
- BiasField：解封触发后的瞬时偏置（事件驱动）
- CrossLayerGravity：持续存在的引力场（场驱动）
"""

import torch
import numpy as np
from typing import Dict, List, Optional, Tuple
from engine.encapsulation_engine import EncapsulationEngine


class GravityField:
    """一个层级的引力势场

    引力势 Φ(i) 表示位置 i 处的引力强度。
    正值 = 吸引（更容易注入），负值 = 排斥（更容易吸收）
    """

    def __init__(self, layer_id: int, potential: torch.Tensor,
                 mass_sources: List[int], generation_step: int):
        """
        Args:
            layer_id: 产生该引力场的层级
            potential: 引力势向量，shape=(N,)
            mass_sources: 产生引力的质量源（冻结且激活的比特索引）
            generation_step: 生成该场的演化步数
        """
        self.layer_id = layer_id
        self.potential = potential          # 引力势
        self.mass_sources = mass_sources    # 质量源位置
        self.generation_step = generation_step
        self.total_mass = len(mass_sources)

    def decay(self, steps_elapsed: int, decay_rate: float = 0.98) -> bool:
        """引力势随时间衰减"""
        self.potential = self.potential * (decay_rate ** steps_elapsed)
        return self.potential.abs().max().item() > 1e-6

    def __repr__(self):
        return (f"GravityField(L{self.layer_id}, "
                f"mass={self.total_mass}, "
                f"Φ_mean={self.potential.mean().item():.4f}, "
                f"Φ_max={self.potential.max().item():.4f})")


class CrossLayerGravityModulator:
    """跨层级引力调制器

    负责：
    1. 计算每一层的引力势场
    2. 将引力势投影到相邻层级
    3. 调制上一层的演化参数（源/汇强度）
    """

    def __init__(self, n_layers: int = 3,
                 gravity_decay: float = 0.5,
                 modulation_strength: float = 0.1,
                 distance_exponent: float = 2.0):
        """
        Args:
            n_layers: 最大层级数
            gravity_decay: 层间引力衰减因子（每上升一层衰减多少）
            modulation_strength: 引力对演化的调制强度
            distance_exponent: 距离衰减指数（2.0 = 平方反比律）
        """
        self.gravity_decay = gravity_decay
        self.modulation_strength = modulation_strength
        self.distance_exponent = distance_exponent

        # 每一层的引力场历史
        self.gravity_fields: Dict[int, List[GravityField]] = {
            i: [] for i in range(n_layers)
        }

        # 调制记录
        self.modulation_history: List[Dict] = []

    def compute_gravity_field(self, layer_id: int,
                              state: torch.Tensor,
                              frozen_bits: set,
                              active_bits: set,
                              binding_strength: Optional[torch.Tensor] = None,
                              step: int = 0) -> GravityField:
        """计算指定层的引力势场

        引力势计算方式：
        Φ(i) = Σ_{j in mass_sources} (1 / (d(i,j) + 1)^exponent) × sign

        其中 mass_sources = 冻结且激活的比特（"有质量的点"）
        sign 由绑定强度决定：强绑定 = 正质量（吸引），弱绑定 = 负质量（排斥）
        """
        n = len(state)
        potential = torch.zeros(n, device=state.device)

        # 质量源 = 冻结且激活的比特
        mass_sources = [
            i for i in frozen_bits
            if i < len(state) and state[i].item() > 0.5
        ]

        if not mass_sources:
            # 没有质量源，返回零场
            field = GravityField(layer_id, potential, [], step)
            self.gravity_fields[layer_id].append(field)
            return field

        # 对每个位置计算引力势
        for i in range(n):
            phi = 0.0
            for j in mass_sources:
                d = abs(i - j) + 1  # 避免除零，最小距离为 1
                distance_factor = 1.0 / (d ** self.distance_exponent)

                # 如果有绑定强度矩阵，用它决定质量符号
                if binding_strength is not None and j < binding_strength.shape[0]:
                    # 强绑定（>0.5）= 正质量，弱绑定 = 负质量
                    avg_binding = binding_strength[i][j].item()
                    mass_sign = 1.0 if avg_binding > 0.5 else -0.3
                else:
                    mass_sign = 1.0  # 默认正质量

                phi += distance_factor * mass_sign

            potential[i] = phi

        # 归一化到 [-1, 1]
        if potential.abs().max() > 0:
            potential = potential / potential.abs().max()

        field = GravityField(layer_id, potential, mass_sources, step)
        self.gravity_fields[layer_id].append(field)
        return field

    def project_gravity_up(self, source_layer_id: int,
                           source_field: GravityField,
                           target_N: int,
                           encap_engine: Optional[EncapsulationEngine] = None,
                           source_layer: int = 0) -> torch.Tensor:
        """将引力势从低层投影到高层

        投影方式取决于是否有封装映射：
        1. 有封装映射：通过映射关系聚合引力势
        2. 无封装映射：线性插值/平均
        """
        if source_field.potential.numel() == 0:
            return torch.zeros(target_N, device=source_field.potential.device)

        device = source_field.potential.device

        if encap_engine is not None and source_layer in encap_engine.index_mappings:
            mapping = encap_engine.index_mappings[source_layer]
            encap_bits = encap_engine.encapsulated_bits.get(source_layer, [])

            # 高层比特 = [活跃比特部分 + 封装比特部分]
            n_active_in_target = target_N - len(encap_bits)

            projected = torch.zeros(target_N, device=device)

            # 1. 活跃比特部分：直接映射
            for low_idx, high_idx in mapping.active_to_high.items():
                if high_idx < n_active_in_target:
                    projected[high_idx] = source_field.potential[low_idx]

            # 2. 封装比特部分：聚合源比特的引力势
            for enc_bit in encap_bits:
                source_indices = enc_bit.source_bits
                if source_indices:
                    grav_values = [
                        source_field.potential[si].item()
                        for si in source_indices
                        if si < source_field.potential.numel()
                    ]
                    if grav_values:
                        avg_grav = sum(grav_values) / len(grav_values)
                    else:
                        avg_grav = 0.0

                    high_idx = n_active_in_target + enc_bit.bit_id
                    if high_idx < target_N:
                        # 封装比特的引力势 = 源比特引力势的加权平均
                        # 权重 = 绑定强度
                        projected[high_idx] = avg_grav * enc_bit.binding_score

        else:
            # 无封装映射：线性聚合
            source_N = source_field.potential.numel()
            if source_N < target_N:
                # 低层维度小，需要扩展
                repeats = target_N // source_N + 1
                projected = source_field.potential.repeat(repeats)[:target_N]
            else:
                # 低层维度大，需要聚合
                k = source_N // target_N
                projected = torch.zeros(target_N, device=device)
                for hi in range(target_N):
                    start = hi * k
                    end = min(start + k, source_N)
                    projected[hi] = source_field.potential[start:end].mean()

        # 应用层间衰减
        projected = projected * self.gravity_decay

        return projected

    def compute_modulation(self, layer_id: int,
                           lower_fields: List[GravityField],
                           upper_fields: List[GravityField],
                           target_state: torch.Tensor) -> Dict:
        """计算对指定层的引力调制

        调制来源：
        1. 下层引力向上投影（牵引力）
        2. 上层引力向下投影（约束力）

        Returns:
            {
                'modulation_vector': 综合调制向量，
                'downward_contribution': 上层向下的贡献，
                'upward_contribution': 下层向上的贡献，
                'modulation_strength': 实际调制强度，
            }
        """
        device = target_state.device
        n = len(target_state)

        upward_contrib = torch.zeros(n, device=device)
        downward_contrib = torch.zeros(n, device=device)

        # 下层引力向上投影
        for field in lower_fields:
            distance = layer_id - field.layer_id
            if distance > 0:
                decay_factor = self.gravity_decay ** distance
                # 简化：直接复用最近的引力场（实际应通过映射投影）
                field_scaled = field.potential[:n] * decay_factor if field.potential.numel() >= n else field.potential
                if field_scaled.numel() < n:
                    field_scaled = torch.cat([field_scaled, torch.zeros(n - field_scaled.numel(), device=device)])
                upward_contrib += field_scaled

        # 上层引力向下投影
        for field in upper_fields:
            distance = field.layer_id - layer_id
            if distance > 0:
                decay_factor = self.gravity_decay ** distance
                field_scaled = field.potential[:n] * decay_factor if field.potential.numel() >= n else field.potential
                if field_scaled.numel() < n:
                    # 需要扩展
                    repeats = n // field_scaled.numel() + 1
                    field_scaled = field_scaled.repeat(repeats)[:n]
                downward_contrib += field_scaled

        # 综合调制 = 向上牵引 - 向下约束
        # 向上 = 吸引（促进注入），向下 = 约束（抑制过度激活）
        modulation = upward_contrib - downward_contrib

        # 归一化
        if modulation.abs().max() > 0:
            modulation = modulation / modulation.abs().max()

        # 应用调制强度
        modulation = modulation * self.modulation_strength

        record = {
            'layer': layer_id,
            'modulation_vector': modulation.clone(),
            'downward_contribution': downward_contrib.clone(),
            'upward_contribution': upward_contrib.clone(),
            'modulation_strength': self.modulation_strength,
            'n_lower_fields': len(lower_fields),
            'n_upper_fields': len(upper_fields),
        }
        self.modulation_history.append(record)

        return record

    def get_modulation_for_injection(self, layer_id: int,
                                     candidates: List[int],
                                     all_fields: Dict[int, List[GravityField]]) -> Dict[int, float]:
        """获取引力调制对注入候选者的影响

        Args:
            layer_id: 当前层
            candidates: 候选注入位置列表
            all_fields: 所有层的引力场 {layer_id: [GravityField]}

        Returns:
            {candidate_idx: modulation_score}
            正分 = 引力促进注入，负分 = 引力抑制注入
        """
        lower_fields = []
        upper_fields = []

        for lid, fields in all_fields.items():
            if lid < layer_id:
                lower_fields.extend(fields)
            elif lid > layer_id:
                upper_fields.extend(fields)

        # 计算调制向量
        dummy_state = torch.zeros(
            max(candidates) + 1 if candidates else 1,
            device=torch.device('cpu')
        )
        mod_result = self.compute_modulation(
            layer_id, lower_fields, upper_fields, dummy_state
        )

        modulation_vector = mod_result['modulation_vector']

        scores = {}
        for idx in candidates:
            if idx < len(modulation_vector):
                # 正引力势 → 促进注入
                scores[idx] = float(modulation_vector[idx].item())
            else:
                scores[idx] = 0.0

        return scores

    def get_active_fields(self, layer_id: int,
                          max_age_steps: int = 100,
                          current_step: int = 0) -> List[GravityField]:
        """获取指定层的活跃引力场（未衰减到可忽略且未过期）"""
        if layer_id not in self.gravity_fields:
            return []

        active = []
        for field in self.gravity_fields[layer_id]:
            steps_elapsed = current_step - field.generation_step if current_step > 0 else 0
            if steps_elapsed <= max_age_steps and field.decay(0, decay_rate=0.98):
                active.append(field)

        return active

    def clear_old_fields(self, max_age_steps: int = 200, current_step: int = 0):
        """清除过老的引力场（超过 max_age_steps 步的场）"""
        if current_step <= 0:
            return  # 无法确定年龄时跳过
        for layer_id in self.gravity_fields:
            self.gravity_fields[layer_id] = [
                f for f in self.gravity_fields[layer_id]
                if (current_step - f.generation_step) <= max_age_steps
            ]

    def project_gravity_down(self, source_field: GravityField,
                              target_N: int,
                              decay_factor: float = 0.5) -> torch.Tensor:
        """将引力势从高层投影到低层（逆向投影）

        用于上层对下层的约束力计算。
        高层比特对应低层多个比特时，引力势均匀分配。
        """
        device = source_field.potential.device
        source_N = source_field.potential.numel()

        if source_N == 0:
            return torch.zeros(target_N, device=device)

        if source_N >= target_N:
            # 高层维度大：每个低层比特聚合对应的高层引力势
            k = source_N // target_N
            projected = torch.zeros(target_N, device=device)
            for lo in range(target_N):
                start = lo * k
                end = min(start + k, source_N)
                projected[lo] = source_field.potential[start:end].mean()
        else:
            # 高层维度小：直接复制/插值
            repeats = target_N // source_N + 1
            projected = source_field.potential.repeat(repeats)[:target_N]

        return projected * decay_factor

    def get_summary(self) -> Dict:
        """获取引力调制摘要"""
        return {
            'n_layers': len(self.gravity_fields),
            'fields_per_layer': {
                lid: len(fields)
                for lid, fields in self.gravity_fields.items()
            },
            'total_modulation_events': len(self.modulation_history),
            'modulation_strength': self.modulation_strength,
            'gravity_decay': self.gravity_decay,
        }
