"""
region_classifier.py — 区域分类器：死寂/爆炸不是失败

将状态空间分为四类区域：
- DEAD: 死寂区 -> 吸收体（黑洞型）
- EXPLOSIVE: 爆炸区 -> 辐射源（超新星型）
- ACTIVE: 活跃区 -> 正常演化
- PHASE: 相变区 -> 结构最丰富的地方

设计决策：系统的一部分陷入死寂或爆炸时，不终止实验，
而是将这些区域转化为新的边界条件。
"""

import numpy as np
from typing import Tuple, Dict, Optional
from enum import IntEnum


class RegionType(IntEnum):
    """区域类型枚举"""
    DEAD = 0       # 死寂区 -> 吸收体（黑洞）
    EXPLOSIVE = 1   # 爆炸区 -> 辐射源（超新星）
    ACTIVE = 2      # 活跃区 -> 正常演化
    PHASE = 3       # 相变区 -> 结构最丰富


class RegionClassifier:
    """
    区域分类器。
    
    根据状态的局部活跃度和能量密度将空间划分为不同区域，
    每个区域有不同的演化行为。
    """
    
    def __init__(self, state_shape: Tuple[int, ...], config: Optional[Dict] = None):
        """
        初始化分类器。
        
        Args:
            state_shape: 状态空间的形状，例如 (height, width) 或 (dim_x, dim_y, dim_z)。
            config: 可选配置，用于覆盖默认的判定阈值和行为参数。
        """
        self.shape = state_shape
        self.state: np.ndarray = None
        self.prev_state: np.ndarray = None
        self.region_map: np.ndarray = None
        
        # 默认配置与阈值
        self.config = {
            # --- 区域分类阈值 ---
            'activity_threshold_low': 1e-6,    # 低于此值视为死寂
            'activity_threshold_high': 1e+3,   # 高于此值视为爆炸
            'energy_density_phase_min': 0.2,   # 相变区能量密度下限
            'energy_density_phase_max': 0.8,   # 相变区能量密度上限
            
            # --- 行为参数 ---
            'dead_absorption_rate': 0.1,       # 黑洞吸收强度 (0, 1]
            'explosive_injection_intensity': 5.0, # 超新星注入强度 [1, ∞)
            'explosive_injection_spread': 2.0,  # 注入影响的范围（格点计）
            'phase_boundary_coupling': 0.05,   # 相边界处的耦合强度
        }
        if config:
            self.config.update(config)
    
    def classify(self, state: np.ndarray) -> np.ndarray:
        """
        对状态空间进行区域分类。
        
        Args:
            state: 当前状态场
            
        Returns:
            region_map: 与状态空间同形的整数数组，元素为 RegionType 的值
        """
        self.prev_state = self.state
        self.state = state.copy()
        
        # 计算活跃度和能量密度
        activity = self._calculate_local_activity()
        energy = self._calculate_energy_density()
        
        # 初始化为活跃区
        region_map = np.full(self.shape, RegionType.ACTIVE, dtype=np.int8)
        
        # 1. 识别死寂区（黑洞型吸收体）
        dead_mask = activity < self.config['activity_threshold_low']
        region_map[dead_mask] = RegionType.DEAD
        
        # 2. 识别爆炸区（超新星型辐射源）
        explosive_mask = activity > self.config['activity_threshold_high']
        region_map[explosive_mask] = RegionType.EXPLOSIVE
        
        # 3. 识别相变区（结构最丰富的区域）
        # 条件：能量密度在中间范围，且未被标记为死寂或爆炸
        phase_mask = (
            (energy >= self.config['energy_density_phase_min']) &
            (energy <= self.config['energy_density_phase_max']) &
            ~dead_mask &
            ~explosive_mask
        )
        region_map[phase_mask] = RegionType.PHASE
        
        self.region_map = region_map
        return region_map
    
    def _calculate_local_activity(self) -> np.ndarray:
        """
        计算每个点的局部活跃度。
        使用状态变化率（时间差分的L2范数）来衡量。
        
        Returns:
            活跃度矩阵
        """
        if self.prev_state is None:
            # 首次调用，返回零矩阵
            return np.zeros(self.shape, dtype=np.float64)
        
        # 状态变化率作为活跃度
        activity = np.abs(self.state - self.prev_state)
        return activity
    
    def _calculate_energy_density(self) -> np.ndarray:
        """
        计算每个点的能量密度或序参量。
        简化实现为状态值的绝对值。
        
        Returns:
            能量密度矩阵
        """
        return np.abs(self.state)
    
    def evolve_with_regions(self, state: np.ndarray) -> np.ndarray:
        """
        按区域分流演化。
        
        Args:
            state: 当前状态
            
        Returns:
            演化后的状态
        """
        if self.region_map is None:
            self.classify(state)
        
        result = state.copy()
        
        # 1. 死寂区（黑洞）：差异被吸收，不产生差异
        # 行为：保持原状或微弱衰减
        dead_mask = self.region_map == RegionType.DEAD
        result[dead_mask] *= (1 - self.config['dead_absorption_rate'])
        
        # 2. 爆炸区（超新星）：差异注入
        # 行为：从中心向外辐射差异
        explosive_mask = self.region_map == RegionType.EXPLOSIVE
        result[explosive_mask] += self.config['explosive_injection_intensity']
        
        # 3. 相变区：结构最丰富，应用较强的耦合
        # 行为：增强与相邻区域的交互
        phase_mask = self.region_map == RegionType.PHASE
        if np.any(phase_mask):
            result[phase_mask] *= (1 + self.config['phase_boundary_coupling'])
        
        # 4. 活跃区：正常演化（由公理引擎处理）
        # 这里不做额外处理
        
        return result
    
    def get_region_stats(self) -> Dict:
        """
        获取各区域的统计信息。
        
        Returns:
            包含各区域面积的字典
        """
        if self.region_map is None:
            return {}
        
        stats = {}
        for rt in RegionType:
            count = np.sum(self.region_map == rt.value)
            stats[rt.name] = int(count)
        
        total = np.prod(self.shape)
        stats['total'] = total
        
        for rt in RegionType:
            pct = stats[rt.name] / total * 100
            stats[f'{rt.name}_pct'] = round(pct, 2)
        
        return stats


def create_classifier(state_shape: Tuple[int, ...], **config) -> RegionClassifier:
    """
    工厂函数：创建区域分类器。
    
    Args:
        state_shape: 状态空间形状
        **config: 配置参数
        
    Returns:
        RegionClassifier 实例
    """
    return RegionClassifier(state_shape, config)


# ============================================================
# 测试入口
# ============================================================

if __name__ == '__main__':
    # 简单的测试
    shape = (16, 16)
    classifier = create_classifier(shape)
    
    # 创建测试状态：中心有点活跃，周围死寂
    state = np.zeros(shape, dtype=np.float64)
    state[6:10, 6:10] = 0.5  # 活跃区
    state[2:4, 2:4] = 1e-7  # 死寂区（黑洞）
    state[12:14, 12:14] = 1e+4  # 爆炸区（超新星）
    
    region_map = classifier.classify(state)
    stats = classifier.get_region_stats()
    
    print('Region Statistics:')
    for k, v in stats.items():
        print(f'  {k}: {v}')
    
    # 测试演化
    new_state = classifier.evolve_with_regions(state)
    print(f'\nState diff: {np.abs(new_state - state).sum():.4f}')