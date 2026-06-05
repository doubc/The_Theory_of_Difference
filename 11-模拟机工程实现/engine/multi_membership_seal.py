"""
engine/multi_membership_seal.py — A9 多隶属封口机制

替代原有的二元封口（sealed_bits: Set[int]），支持：
1. 比特同时隶属多个组织（多隶属）
2. 渐进式封口（组织逐步形成，非一次性事件）
3. 残余自由度追踪（未被组织占用的自由度可参与新组织）

理论对应：
- 差异的余差持续参与后续封口
- 一个实体可以同时隶属于多个社会组织
- 封口是从开放演化到闭合整合的渐进过渡

数据结构：
- organizations: Dict[int, Set[int]]  — org_id -> 成员比特集合
- bit_memberships: Dict[int, List[Tuple[int, float]]]  — bit_idx -> [(org_id, weight), ...]
- _org_binding_scores: Dict[int, float]  — org_id -> 组内平均绑定强度

向后兼容：
- sealed_bits 计算属性：完全锁定的比特集合
- sealed 计算属性：系统是否已达到封口阈值
- 旧的直接赋值通过 setter 转为等价的隶属关系
"""

import torch
import numpy as np
from typing import Dict, Set, List, Tuple, Optional
from dataclasses import dataclass, field


@dataclass
class OrgInfo:
    """单个组织的元信息"""
    org_id: int
    members: Set[int]
    avg_binding: float         # 组内平均绑定强度
    formation_step: int        # 形成时的步数
    is_encapsulated: bool = False  # 是否已被封装到高层级


@dataclass
class MembershipSnapshot:
    """多隶属状态快照"""
    n_organizations: int
    n_multi_member_bits: int   # 隶属多个组织的比特数
    n_fully_locked: int        # 完全锁定的比特数
    n_partially_locked: int    # 部分锁定的比特数
    n_free: int                # 完全自由的比特数
    avg_lock_level: float      # 平均锁定水平
    max_memberships: int       # 单个比特的最大隶属数
    org_sizes: List[int]       # 各组织的成员数
    org_bindings: List[float]  # 各组织的平均绑定强度


class MultiMembershipSeal:
    """A9 多隶属封口引擎
    
    使用方法：
        mms = MultiMembershipSeal(N=72, binding_strength=constraints.binding_strength)
        
        # 每步记录活跃
        mms.record_active(bit_idx, step)
        
        # 定期执行组织形成（由 check_A9 调用）
        if step % mms.org_formation_interval == 0:
            mms.form_organizations(step)
        
        # 检查比特是否可参与演化
        if not mms.is_fully_locked(bit_idx):
            # 允许翻转
            ...
        
        # 获取兼容旧接口的 sealed_bits
        frozen = mms.sealed_bits  # Set[int]
    """
    
    def __init__(self, N: int, binding_strength: torch.Tensor,
                 org_formation_interval: int = 50,
                 org_join_threshold: float = 0.15,
                 lock_threshold: float = 0.95,
                 max_orgs_per_bit: int = 4,
                 min_org_size: int = 2,
                 sealing_activation_threshold: Optional[int] = None,
                 device: str = "cpu"):
        """
        Args:
            N: 总比特数
            binding_strength: 绑定强度矩阵 (N, N)，由 AxiomConstraints 维护
            org_formation_interval: 组织形成扫描间隔（步数）
            org_join_threshold: 加入组织的最低绑定强度
            lock_threshold: 完全锁定的锁定水平阈值
            max_orgs_per_bit: 单个比特最多隶属的组织数
            min_org_size: 组织的最小成员数（低于此值不成立组织）
            sealing_activation_threshold: 触发封口标志的最低完全锁定比特数
            device: 计算设备
        """
        self.N = N
        self.binding_strength = binding_strength  # 引用，非拷贝
        self.org_formation_interval = org_formation_interval
        self.org_join_threshold = org_join_threshold
        self.lock_threshold = lock_threshold
        self.max_orgs_per_bit = max_orgs_per_bit
        self.min_org_size = min_org_size
        self.sealing_activation_threshold = sealing_activation_threshold or max(int(0.75 * N), 30)
        self.device = device
        
        # ── 核心数据结构 ──
        self.organizations: Dict[int, OrgInfo] = {}
        self.bit_memberships: Dict[int, List[Tuple[int, float]]] = {}
        self._next_org_id: int = 0
        
        # ── 活跃追踪 ──
        self.active_bits: Dict[int, int] = {}  # bit_idx -> last_active_step
        self.total_unique_active: Set[int] = set()
        
        # ── 封口状态（可由外部覆盖） ──
        self._sealed_override: Optional[bool] = None
        self._sealed_bits_override: Optional[Set[int]] = None
        
        # ── 历史记录 ──
        self.formation_history: List[Dict] = []  # 每次组织形成的记录
    
    # ================================================================
    # 锁定水平计算
    # ================================================================
    
    def compute_lock_level(self, bit_idx: int) -> float:
        """计算比特的锁定水平
        
        锁定水平 = 所有隶属度之和（上限 1.0）
        0.0 = 完全自由，1.0 = 完全锁定
        """
        memberships = self.bit_memberships.get(bit_idx, [])
        if not memberships:
            return 0.0
        return min(1.0, sum(w for _, w in memberships))
    
    def is_fully_locked(self, bit_idx: int) -> bool:
        """比特是否完全锁定"""
        return self.compute_lock_level(bit_idx) >= self.lock_threshold
    
    def is_partially_locked(self, bit_idx: int) -> bool:
        """比特是否部分锁定（有隶属但未完全锁定）"""
        ll = self.compute_lock_level(bit_idx)
        return 0.0 < ll < self.lock_threshold
    
    def get_residual_freedom(self, bit_idx: int) -> float:
        """获取比特的残余自由度"""
        return max(0.0, 1.0 - self.compute_lock_level(bit_idx))
    
    def get_org_memberships(self, bit_idx: int) -> List[Tuple[int, float]]:
        """获取比特的所有组织隶属关系 [(org_id, weight), ...]"""
        return self.bit_memberships.get(bit_idx, [])
    
    # ================================================================
    # 组织形成（核心算法）
    # ================================================================
    
    def form_organizations(self, current_step: int):
        """执行一次组织形成扫描
        
        贪心团扩展算法：
        1. 获取活跃且未完全锁定的比特
        2. 计算超过阈值的绑定强度比特对
        3. 按绑定强度降序，贪心地扩展或创建组织
        4. 为每个成员分配隶属度（受残余自由度约束）
        
        多隶属特性：
        - 一个比特可以加入多个组织
        - 隶属度受残余自由度限制：new_weight <= residual_freedom
        - 隶属组织数受 max_orgs_per_bit 限制
        """
        # 1. 获取活跃且未完全锁定的比特
        active_free = []
        for i in range(self.N):
            if i in self.active_bits and not self.is_fully_locked(i):
                active_free.append(i)
        
        if len(active_free) < self.min_org_size:
            return
        
        # 2. 计算绑定强度超过阈值的比特对
        edges = []
        for i_idx in range(len(active_free)):
            i = active_free[i_idx]
            for j_idx in range(i_idx + 1, len(active_free)):
                j = active_free[j_idx]
                b = self.binding_strength[i][j].item()
                if b > self.org_join_threshold:
                    edges.append((i, j, b))
        
        if not edges:
            return
        
        # 3. 贪心团扩展
        edges.sort(key=lambda e: e[2], reverse=True)
        
        # 候选组织：列表 of 比特集合
        candidate_groups: List[Set[int]] = []
        # 比特 -> 它所属的候选组织索引
        bit_to_groups: Dict[int, List[int]] = {}
        
        for i, j, b in edges:
            # 查找 i 和 j 各自所属的候选组织
            i_groups = bit_to_groups.get(i, [])
            j_groups = bit_to_groups.get(j, [])
            
            # 情况1：i 和 j 已在同一候选组织 -> 跳过
            if set(i_groups) & set(j_groups):
                continue
            
            # 情况2：i 在某个组织，j 不在 -> 尝试将 j 加入 i 的组织
            # 情况3：j 在某个组织，i 不在 -> 尝试将 i 加入 j 的组织
            # 情况4：都不在 -> 创建新组织
            
            merged = False
            
            # 尝试将新比特加入已有组织
            for g_idx in i_groups:
                group = candidate_groups[g_idx]
                if j not in group:
                    avg_b = sum(
                        self.binding_strength[j][m].item()
                        for m in group if m != j
                    ) / max(len(group), 1)
                    if avg_b > self.org_join_threshold:
                        group.add(j)
                        if j not in bit_to_groups:
                            bit_to_groups[j] = []
                        bit_to_groups[j].append(g_idx)
                        merged = True
                        break
            
            if not merged:
                for g_idx in j_groups:
                    group = candidate_groups[g_idx]
                    if i not in group:
                        avg_b = sum(
                            self.binding_strength[i][m].item()
                            for m in group if m != i
                        ) / max(len(group), 1)
                        if avg_b > self.org_join_threshold:
                            group.add(i)
                            if i not in bit_to_groups:
                                bit_to_groups[i] = []
                            bit_to_groups[i].append(g_idx)
                            merged = True
                            break
            
            if not merged:
                # 创建新候选组织
                g_idx = len(candidate_groups)
                candidate_groups.append({i, j})
                if i not in bit_to_groups:
                    bit_to_groups[i] = []
                if j not in bit_to_groups:
                    bit_to_groups[j] = []
                bit_to_groups[i].append(g_idx)
                bit_to_groups[j].append(g_idx)
        
        # 4. 过滤并注册正式组织
        n_new_orgs = 0
        for group in candidate_groups:
            if len(group) < self.min_org_size:
                continue
            
            members = sorted(group)
            # 计算组内平均绑定强度
            bindings = [
                self.binding_strength[i][j].item()
                for i in members for j in members if i < j
            ]
            avg_binding = sum(bindings) / max(len(bindings), 1)
            
            # 注册组织
            org_id = self._next_org_id
            self._next_org_id += 1
            n_new_orgs += 1
            
            self.organizations[org_id] = OrgInfo(
                org_id=org_id,
                members=set(members),
                avg_binding=avg_binding,
                formation_step=current_step,
            )
            
            # 为每个成员分配隶属度
            for bit_idx in members:
                current_memberships = self.bit_memberships.get(bit_idx, [])
                current_lock = min(1.0, sum(w for _, w in current_memberships))
                remaining = 1.0 - current_lock
                
                if remaining <= 0.01:
                    continue
                if len(current_memberships) >= self.max_orgs_per_bit:
                    continue
                
                # 隶属度 = 该比特与组内其他成员的平均绑定强度
                bit_bindings = [
                    self.binding_strength[bit_idx][m].item()
                    for m in members if m != bit_idx
                ]
                bit_avg = sum(bit_bindings) / max(len(bit_bindings), 1)
                
                # 隶属度受残余自由度约束
                weight = min(bit_avg, remaining)
                weight = max(weight, 0.01)  # 最低隶属度
                
                current_memberships.append((org_id, weight))
                self.bit_memberships[bit_idx] = current_memberships
        
        # 5. 记录形成历史
        if n_new_orgs > 0:
            self.formation_history.append({
                'step': current_step,
                'n_new_orgs': n_new_orgs,
                'n_total_orgs': len(self.organizations),
                'n_locked': len(self.sealed_bits),
                'n_partially_locked': sum(
                    1 for i in range(self.N) if self.is_partially_locked(i)
                ),
            })
    
    # ================================================================
    # 活跃记录（由 check_A9 调用）
    # ================================================================
    
    def record_active(self, bit_idx: int, step: int):
        """记录比特活跃"""
        self.active_bits[bit_idx] = step
        self.total_unique_active.add(bit_idx)
    
    # ================================================================
    # 向后兼容接口
    # ================================================================
    
    @property
    def sealed_bits(self) -> Set[int]:
        """完全锁定的比特集合（向后兼容）
        
        如果有外部覆盖（测试代码直接赋值），返回覆盖值。
        否则从 bit_memberships 计算。
        """
        if self._sealed_bits_override is not None:
            return self._sealed_bits_override
        return {
            bit_idx for bit_idx in self.bit_memberships
            if self.compute_lock_level(bit_idx) >= self.lock_threshold
        }
    
    @sealed_bits.setter
    def sealed_bits(self, value):
        """向后兼容：允许直接赋值（测试代码）
        
        将直接赋值转为等价的隶属关系：
        每个比特加入一个 singleton 组织，隶属度 = 1.0
        """
        if isinstance(value, set):
            self._sealed_bits_override = value
            # 同时更新 bit_memberships 以保持一致性
            for bit_idx in value:
                if bit_idx not in self.bit_memberships:
                    org_id = self._next_org_id
                    self._next_org_id += 1
                    self.organizations[org_id] = OrgInfo(
                        org_id=org_id,
                        members={bit_idx},
                        avg_binding=0.0,
                        formation_step=0,
                    )
                    self.bit_memberships[bit_idx] = [(org_id, 1.0)]
    
    @property
    def sealed(self) -> bool:
        """封口标志（向后兼容）"""
        if self._sealed_override is not None:
            return self._sealed_override
        return len(self.sealed_bits) >= self.sealing_activation_threshold
    
    @sealed.setter
    def sealed(self, value: bool):
        """向后兼容：允许直接赋值"""
        self._sealed_override = value
    
    def clear_overrides(self):
        """清除外部覆盖，恢复计算属性行为
        
        同时清理由 setter 创建的 singleton 组织（lock_level >= threshold 的）
        """
        if self._sealed_bits_override is not None:
            # 清除 setter 创建的 singleton 组织
            for bit_idx in self._sealed_bits_override:
                memberships = self.bit_memberships.get(bit_idx, [])
                # 只移除完全锁定且只有一个隶属的条目（setter 创建的）
                if len(memberships) == 1:
                    oid, w = memberships[0]
                    if w >= 1.0 and oid in self.organizations:
                        org = self.organizations[oid]
                        if len(org.members) == 1:
                            del self.organizations[oid]
                            self.bit_memberships[bit_idx] = []
        self._sealed_override = None
        self._sealed_bits_override = None
    
    # ================================================================
    # 查询与快照
    # ================================================================
    
    def get_snapshot(self) -> MembershipSnapshot:
        """获取当前多隶属状态的完整快照"""
        org_sizes = []
        org_bindings = []
        for org in self.organizations.values():
            org_sizes.append(len(org.members))
            org_bindings.append(org.avg_binding)
        
        lock_levels = [self.compute_lock_level(i) for i in range(self.N)]
        
        n_multi = sum(
            1 for ms in self.bit_memberships.values() if len(ms) > 1
        )
        
        return MembershipSnapshot(
            n_organizations=len(self.organizations),
            n_multi_member_bits=n_multi,
            n_fully_locked=len(self.sealed_bits),
            n_partially_locked=sum(
                1 for ll in lock_levels if 0 < ll < self.lock_threshold
            ),
            n_free=sum(1 for ll in lock_levels if ll == 0.0),
            avg_lock_level=sum(lock_levels) / max(len(lock_levels), 1),
            max_memberships=max(
                (len(ms) for ms in self.bit_memberships.values()), default=0
            ),
            org_sizes=org_sizes,
            org_bindings=org_bindings,
        )
    
    def get_org_info(self, org_id: int) -> Optional[OrgInfo]:
        """获取指定组织的信息"""
        return self.organizations.get(org_id)
    
    def get_bit_orgs(self, bit_idx: int) -> List[OrgInfo]:
        """获取比特所属的所有组织"""
        memberships = self.bit_memberships.get(bit_idx, [])
        return [
            self.organizations[oid]
            for oid, _ in memberships
            if oid in self.organizations
        ]
    
    def get_overlap_matrix(self) -> Dict[Tuple[int, int], Set[int]]:
        """计算组织间的重叠矩阵
        
        Returns:
            {(org_i, org_j): shared_bits}  — 共享成员的组织对
        """
        overlaps = {}
        org_ids = sorted(self.organizations.keys())
        for i_idx, oi in enumerate(org_ids):
            for oj in org_ids[i_idx+1:]:
                shared = self.organizations[oi].members & self.organizations[oj].members
                if shared:
                    overlaps[(oi, oj)] = shared
        return overlaps
    
    def get_summary(self) -> Dict:
        """获取摘要信息（用于日志/实验记录）"""
        snap = self.get_snapshot()
        overlaps = self.get_overlap_matrix()
        
        return {
            'n_organizations': snap.n_organizations,
            'n_multi_member_bits': snap.n_multi_member_bits,
            'n_fully_locked': snap.n_fully_locked,
            'n_partially_locked': snap.n_partially_locked,
            'n_free': snap.n_free,
            'avg_lock_level': round(snap.avg_lock_level, 4),
            'max_memberships': snap.max_memberships,
            'n_overlapping_org_pairs': len(overlaps),
            'avg_org_size': round(
                sum(snap.org_sizes) / max(len(snap.org_sizes), 1), 2
            ),
            'avg_org_binding': round(
                sum(snap.org_bindings) / max(len(snap.org_bindings), 1), 4
            ),
            'formation_events': len(self.formation_history),
        }
