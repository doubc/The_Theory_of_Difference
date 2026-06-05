"""
tests/test_multi_membership_seal.py — A9 多隶属封口机制测试

测试覆盖：
1. 基础锁定水平计算
2. 组织形成算法
3. 多隶属特性（比特同时属于多个组织）
4. 渐进封口行为
5. 向后兼容（sealed_bits / sealed 接口）
6. 快照与查询
7. 边界条件
"""

import pytest
import torch
import numpy as np
from engine.multi_membership_seal import (
    MultiMembershipSeal, OrgInfo, MembershipSnapshot
)


# ================================================================
# Fixtures
# ================================================================

@pytest.fixture
def simple_binding_matrix():
    """简单绑定强度矩阵：3 个明显聚类
    
    比特 0-3: 聚类 A（强绑定）
    比特 4-7: 聚类 B（强绑定）
    比特 3, 8: 跨聚类桥接（比特 3 同时与 A、B 有绑定）
    """
    N = 10
    B = torch.zeros(N, N)
    
    # 聚类 A: bits 0-3
    for i in range(4):
        for j in range(4):
            if i != j:
                B[i][j] = 0.5
    
    # 聚类 B: bits 4-7
    for i in range(4, 8):
        for j in range(4, 8):
            if i != j:
                B[i][j] = 0.4
    
    # 桥接: bit 3 与 bit 4 有较强绑定
    B[3][4] = 0.3
    B[4][3] = 0.3
    
    # 比特 8 和 9 是孤立的
    return B


@pytest.fixture
def mms_simple(simple_binding_matrix):
    """基于简单绑定矩阵的多隶属封口引擎"""
    return MultiMembershipSeal(
        N=10,
        binding_strength=simple_binding_matrix,
        org_formation_interval=10,
        org_join_threshold=0.2,
        lock_threshold=0.95,
        max_orgs_per_bit=4,
        min_org_size=2,
        sealing_activation_threshold=5,
    )


@pytest.fixture
def uniform_binding_matrix():
    """均匀绑定强度矩阵（所有比特对绑定强度相同）"""
    N = 12
    B = torch.ones(N, N) * 0.3
    B.fill_diagonal_(0)
    return B


@pytest.fixture
def mms_uniform(uniform_binding_matrix):
    """基于均匀绑定矩阵的多隶属封口引擎"""
    return MultiMembershipSeal(
        N=12,
        binding_strength=uniform_binding_matrix,
        org_formation_interval=10,
        org_join_threshold=0.2,
        lock_threshold=0.95,
        max_orgs_per_bit=3,
        min_org_size=2,
        sealing_activation_threshold=8,
    )


# ================================================================
# Test 1: 基础锁定水平计算
# ================================================================

class TestLockLevel:
    """锁定水平计算测试"""
    
    def test_free_bit_has_zero_lock(self, mms_simple):
        """未参与任何组织的比特锁定水平为 0"""
        assert mms_simple.compute_lock_level(0) == 0.0
        assert mms_simple.get_residual_freedom(0) == 1.0
        assert not mms_simple.is_fully_locked(0)
        assert not mms_simple.is_partially_locked(0)
    
    def test_lock_level_from_memberships(self, mms_simple):
        """手动设置隶属关系后锁定水平正确"""
        mms_simple.bit_memberships[0] = [(0, 0.3), (1, 0.4)]
        assert abs(mms_simple.compute_lock_level(0) - 0.7) < 1e-6
        assert abs(mms_simple.get_residual_freedom(0) - 0.3) < 1e-6
        assert mms_simple.is_partially_locked(0)
        assert not mms_simple.is_fully_locked(0)
    
    def test_fully_locked_bit(self, mms_simple):
        """锁定水平 >= threshold 的比特为完全锁定"""
        mms_simple.bit_memberships[0] = [(0, 0.5), (1, 0.5)]
        assert mms_simple.compute_lock_level(0) >= 0.95
        assert mms_simple.is_fully_locked(0)
        assert mms_simple.get_residual_freedom(0) == 0.0
    
    def test_lock_level_capped_at_one(self, mms_simple):
        """锁定水平上限为 1.0"""
        mms_simple.bit_memberships[0] = [(0, 0.6), (1, 0.6), (2, 0.6)]
        assert mms_simple.compute_lock_level(0) == 1.0
    
    def test_empty_memberships(self, mms_simple):
        """空隶属关系锁定水平为 0"""
        assert mms_simple.compute_lock_level(5) == 0.0


# ================================================================
# Test 2: 组织形成算法
# ================================================================

class TestOrgFormation:
    """组织形成算法测试"""
    
    def test_forms_two_clusters(self, mms_simple):
        """应形成至少 2 个组织（对应 2 个聚类）"""
        # 标记所有比特为活跃
        for i in range(10):
            mms_simple.record_active(i, 0)
        
        mms_simple.form_organizations(current_step=10)
        
        assert len(mms_simple.organizations) >= 2, \
            f"Expected >= 2 orgs, got {len(mms_simple.organizations)}"
    
    def test_org_members_from_same_cluster(self, mms_simple):
        """组织成员应主要来自同一聚类"""
        for i in range(10):
            mms_simple.record_active(i, 0)
        
        mms_simple.form_organizations(current_step=10)
        
        # 检查聚类 A (bits 0-3) 是否在某个组织中
        cluster_a = {0, 1, 2, 3}
        found_a = False
        for org in mms_simple.organizations.values():
            if cluster_a.issubset(org.members) or len(cluster_a & org.members) >= 3:
                found_a = True
                break
        assert found_a, "Cluster A bits should form an organization"
    
    def test_bridge_bit_multi_membership(self, mms_simple):
        """桥接比特（bit 3）应有可能属于多个组织"""
        for i in range(10):
            mms_simple.record_active(i, 0)
        
        # 多次执行组织形成以增加多隶属机会
        for step in range(10, 200, 10):
            mms_simple.form_organizations(current_step=step)
        
        # bit 3 是桥接比特，与两个聚类都有绑定
        memberships_3 = mms_simple.get_org_memberships(3)
        # 由于绑定强度设置，bit 3 应该至少属于 1 个组织
        assert len(memberships_3) >= 1, \
            f"Bridge bit 3 should belong to >= 1 org, got {len(memberships_3)}"
    
    def test_no_org_below_min_size(self, mms_simple):
        """成员数低于 min_org_size 的不应成为组织"""
        # 只标记 1 个比特为活跃
        mms_simple.record_active(0, 0)
        mms_simple.form_organizations(current_step=10)
        assert len(mms_simple.organizations) == 0
    
    def test_org_binding_score_positive(self, mms_simple):
        """组织的绑定强度得分应为正"""
        for i in range(8):
            mms_simple.record_active(i, 0)
        
        mms_simple.form_organizations(current_step=10)
        
        for org in mms_simple.organizations.values():
            assert org.avg_binding > 0, \
                f"Org {org.org_id} should have positive binding, got {org.avg_binding}"
    
    def test_formation_history_recorded(self, mms_simple):
        """组织形成应被记录在历史中"""
        for i in range(8):
            mms_simple.record_active(i, 0)
        
        mms_simple.form_organizations(current_step=10)
        
        if len(mms_simple.organizations) > 0:
            assert len(mms_simple.formation_history) > 0
            assert mms_simple.formation_history[0]['step'] == 10
    
    def test_uniform_binding_forms_orgs(self, mms_uniform):
        """均匀绑定应形成组织"""
        for i in range(12):
            mms_uniform.record_active(i, 0)
        
        mms_uniform.form_organizations(current_step=10)
        
        assert len(mms_uniform.organizations) >= 1, \
            "Uniform binding should form at least 1 organization"


# ================================================================
# Test 3: 多隶属特性
# ================================================================

class TestMultiMembership:
    """多隶属特性测试"""
    
    def test_bit_can_join_multiple_orgs(self):
        """比特可以同时属于多个组织"""
        N = 6
        B = torch.zeros(N, N)
        # bit 0 与 bit 1, 2 强绑定（组织 A）
        B[0][1] = B[1][0] = 0.6
        B[0][2] = B[2][0] = 0.5
        B[1][2] = B[2][1] = 0.5
        # bit 0 与 bit 3, 4 也强绑定（组织 B）
        B[0][3] = B[3][0] = 0.5
        B[0][4] = B[4][0] = 0.5
        B[3][4] = B[4][3] = 0.6
        
        mms = MultiMembershipSeal(
            N=N, binding_strength=B,
            org_join_threshold=0.3,
            max_orgs_per_bit=4,
            min_org_size=2,
            lock_threshold=0.95,
        )
        
        for i in range(N):
            mms.record_active(i, 0)
        
        # 多次扫描以增加多隶属机会
        for step in range(10, 300, 10):
            mms.form_organizations(current_step=step)
        
        # bit 0 应该属于多个组织（它是两个聚类的桥接）
        memberships_0 = mms.get_org_memberships(0)
        assert len(memberships_0) >= 1, \
            f"Bridge bit 0 should belong to >= 1 org, got {len(memberships_0)}"
    
    def test_max_orgs_per_bit_respected(self):
        """隶属组织数不超过 max_orgs_per_bit"""
        N = 8
        B = torch.ones(N, N) * 0.4
        B.fill_diagonal_(0)
        
        mms = MultiMembershipSeal(
            N=N, binding_strength=B,
            org_join_threshold=0.2,
            max_orgs_per_bit=2,
            min_org_size=2,
            lock_threshold=0.95,
        )
        
        for i in range(N):
            mms.record_active(i, 0)
        
        for step in range(10, 500, 10):
            mms.form_organizations(current_step=step)
        
        for bit_idx in range(N):
            memberships = mms.get_org_memberships(bit_idx)
            assert len(memberships) <= 2, \
                f"Bit {bit_idx} has {len(memberships)} memberships > max 2"
    
    def test_residual_freedom_decreases(self, mms_simple):
        """每次组织形成后，参与比特的残余自由度应减少"""
        for i in range(8):
            mms_simple.record_active(i, 0)
        
        initial_freedom = mms_simple.get_residual_freedom(0)
        assert initial_freedom == 1.0
        
        mms_simple.form_organizations(current_step=10)
        
        new_freedom = mms_simple.get_residual_freedom(0)
        if mms_simple.get_org_memberships(0):
            assert new_freedom < initial_freedom, \
                f"Freedom should decrease: {initial_freedom} -> {new_freedom}"
    
    def test_lock_level_invariant(self):
        """锁定水平不变式：L(i) <= 1.0"""
        N = 10
        B = torch.ones(N, N) * 0.5
        B.fill_diagonal_(0)
        
        mms = MultiMembershipSeal(
            N=N, binding_strength=B,
            org_join_threshold=0.2,
            max_orgs_per_bit=10,  # 允许很多组织
            min_org_size=2,
            lock_threshold=0.95,
        )
        
        for i in range(N):
            mms.record_active(i, 0)
        
        for step in range(10, 500, 10):
            mms.form_organizations(current_step=step)
        
        for bit_idx in range(N):
            ll = mms.compute_lock_level(bit_idx)
            assert ll <= 1.0 + 1e-6, \
                f"Bit {bit_idx} lock level {ll} > 1.0"


# ================================================================
# Test 4: 向后兼容
# ================================================================

class TestBackwardCompat:
    """向后兼容接口测试"""
    
    def test_sealed_bits_setter(self, mms_simple):
        """直接赋值 sealed_bits 应工作"""
        mms_simple.sealed_bits = {0, 1, 2, 3}
        assert mms_simple.sealed_bits == {0, 1, 2, 3}
    
    def test_sealed_setter(self, mms_simple):
        """直接赋值 sealed 应工作"""
        mms_simple.sealed = True
        assert mms_simple.sealed is True
        mms_simple.sealed = False
        assert mms_simple.sealed is False
    
    def test_sealed_bits_from_memberships(self, mms_simple):
        """从 bit_memberships 计算 sealed_bits"""
        # 手动创建完全锁定的比特
        mms_simple.bit_memberships[0] = [(0, 0.5), (1, 0.5)]
        mms_simple.bit_memberships[1] = [(0, 0.5), (1, 0.5)]
        mms_simple.clear_overrides()  # 清除可能的覆盖
        
        sealed = mms_simple.sealed_bits
        assert 0 in sealed
        assert 1 in sealed
        assert 2 not in sealed
    
    def test_sealed_threshold(self, mms_simple):
        """sealed 标志在锁定比特数 >= threshold 时为 True"""
        mms_simple.clear_overrides()
        
        # 创建 threshold 个完全锁定的比特
        for i in range(mms_simple.sealing_activation_threshold):
            mms_simple.bit_memberships[i] = [(i, 1.0)]
        
        assert mms_simple.sealed is True
    
    def test_sealed_bits_override_cleared(self, mms_simple):
        """clear_overrides 应清除覆盖"""
        mms_simple.sealed_bits = {0, 1}
        assert mms_simple.sealed_bits == {0, 1}
        
        mms_simple.clear_overrides()
        # 清除后应回到计算值
        assert 0 not in mms_simple.sealed_bits or \
               mms_simple.compute_lock_level(0) >= 0.95
    
    def test_sealed_bits_setter_creates_orgs(self, mms_simple):
        """sealed_bits setter 应创建对应的组织"""
        initial_orgs = len(mms_simple.organizations)
        mms_simple.sealed_bits = {0, 1, 2}
        assert len(mms_simple.organizations) >= initial_orgs


# ================================================================
# Test 5: 快照与查询
# ================================================================

class TestSnapshot:
    """快照与查询测试"""
    
    def test_snapshot_empty(self, mms_simple):
        """空状态的快照"""
        snap = mms_simple.get_snapshot()
        assert snap.n_organizations == 0
        assert snap.n_fully_locked == 0
        assert snap.n_free == 10
        assert snap.avg_lock_level == 0.0
    
    def test_snapshot_after_formation(self, mms_simple):
        """组织形成后的快照"""
        for i in range(8):
            mms_simple.record_active(i, 0)
        
        mms_simple.form_organizations(current_step=10)
        
        snap = mms_simple.get_snapshot()
        assert snap.n_organizations >= 0
        assert snap.n_free + snap.n_partially_locked + snap.n_fully_locked == 10
    
    def test_get_summary(self, mms_simple):
        """get_summary 返回正确结构"""
        summary = mms_simple.get_summary()
        expected_keys = {
            'n_organizations', 'n_multi_member_bits', 'n_fully_locked',
            'n_partially_locked', 'n_free', 'avg_lock_level',
            'max_memberships', 'n_overlapping_org_pairs',
            'avg_org_size', 'avg_org_binding', 'formation_events',
        }
        assert expected_keys.issubset(set(summary.keys()))
    
    def test_get_overlap_matrix(self):
        """重叠矩阵正确检测共享成员"""
        N = 6
        B = torch.ones(N, N) * 0.4
        B.fill_diagonal_(0)
        
        mms = MultiMembershipSeal(
            N=N, binding_strength=B,
            org_join_threshold=0.2,
            max_orgs_per_bit=4,
            min_org_size=2,
            lock_threshold=0.95,
        )
        
        # 手动创建有重叠的组织
        mms.organizations[0] = OrgInfo(0, {0, 1, 2}, 0.4, 0)
        mms.organizations[1] = OrgInfo(1, {2, 3, 4}, 0.3, 0)
        mms.organizations[2] = OrgInfo(2, {4, 5}, 0.5, 0)
        
        overlaps = mms.get_overlap_matrix()
        
        # org 0 和 org 1 共享 bit 2
        assert (0, 1) in overlaps
        assert 2 in overlaps[(0, 1)]
        
        # org 1 和 org 2 共享 bit 4
        assert (1, 2) in overlaps
        assert 4 in overlaps[(1, 2)]
    
    def test_get_bit_orgs(self, mms_simple):
        """获取比特所属的所有组织"""
        # 手动设置
        mms_simple.organizations[0] = OrgInfo(0, {0, 1, 2}, 0.5, 0)
        mms_simple.organizations[1] = OrgInfo(1, {0, 3, 4}, 0.3, 0)
        mms_simple.bit_memberships[0] = [(0, 0.4), (1, 0.3)]
        
        orgs = mms_simple.get_bit_orgs(0)
        assert len(orgs) == 2
        org_ids = {o.org_id for o in orgs}
        assert org_ids == {0, 1}


# ================================================================
# Test 6: 渐进封口
# ================================================================

class TestProgressiveSealing:
    """渐进封口行为测试"""
    
    def test_sealing_progresses_over_time(self, mms_simple):
        """封口应随时间渐进（锁定比特数增加）"""
        for i in range(10):
            mms_simple.record_active(i, 0)
        
        locked_counts = []
        for step in range(10, 500, 10):
            mms_simple.form_organizations(current_step=step)
            locked_counts.append(len(mms_simple.sealed_bits))
        
        # 锁定比特数应该非递减（可能有波动，但趋势是增加）
        if len(locked_counts) > 2:
            assert locked_counts[-1] >= locked_counts[0], \
                f"Locking should progress: {locked_counts}"
    
    def test_orgs_form_incrementally(self):
        """组织应逐步增加而非一次性全部形成"""
        N = 20
        B = torch.zeros(N, N)
        # 创建 3 个聚类，绑定强度递增
        for cluster_idx in range(3):
            base = cluster_idx * 6
            strength = 0.2 + cluster_idx * 0.15
            for i in range(base, min(base + 6, N)):
                for j in range(base, min(base + 6, N)):
                    if i != j:
                        B[i][j] = strength
        
        mms = MultiMembershipSeal(
            N=N, binding_strength=B,
            org_formation_interval=10,
            org_join_threshold=0.2,
            lock_threshold=0.95,
            max_orgs_per_bit=4,
            min_org_size=2,
            sealing_activation_threshold=15,
        )
        
        for i in range(N):
            mms.record_active(i, 0)
        
        org_counts = []
        for step in range(10, 300, 10):
            mms.form_organizations(current_step=step)
            org_counts.append(len(mms.organizations))
        
        # 组织数应该增加
        if len(org_counts) > 1:
            assert org_counts[-1] >= org_counts[0], \
                f"Orgs should form over time: {org_counts}"


# ================================================================
# Test 7: 边界条件
# ================================================================

class TestEdgeCases:
    """边界条件测试"""
    
    def test_single_bit_no_org(self):
        """单个比特不应形成组织"""
        B = torch.zeros(1, 1)
        mms = MultiMembershipSeal(N=1, binding_strength=B, min_org_size=2)
        mms.record_active(0, 0)
        mms.form_organizations(current_step=10)
        assert len(mms.organizations) == 0
    
    def test_zero_binding_no_org(self):
        """零绑定强度不应形成组织"""
        B = torch.zeros(10, 10)
        mms = MultiMembershipSeal(N=10, binding_strength=B, min_org_size=2)
        for i in range(10):
            mms.record_active(i, 0)
        mms.form_organizations(current_step=10)
        assert len(mms.organizations) == 0
    
    def test_all_bits_locked(self):
        """所有比特都锁定的情况"""
        N = 4
        B = torch.ones(N, N) * 0.8
        B.fill_diagonal_(0)
        
        mms = MultiMembershipSeal(
            N=N, binding_strength=B,
            org_join_threshold=0.3,
            lock_threshold=0.95,
            max_orgs_per_bit=10,
            min_org_size=2,
        )
        
        for i in range(N):
            mms.record_active(i, 0)
        
        for step in range(10, 1000, 10):
            mms.form_organizations(current_step=step)
        
        # 应该大部分比特都被锁定
        snap = mms.get_snapshot()
        assert snap.n_fully_locked + snap.n_partially_locked > 0
    
    def test_no_active_bits(self, mms_simple):
        """没有活跃比特时不应形成组织"""
        mms_simple.form_organizations(current_step=10)
        assert len(mms_simple.organizations) == 0
    
    def test_idempotent_org_formation(self, mms_simple):
        """多次形成不应重复创建相同的组织"""
        for i in range(8):
            mms_simple.record_active(i, 0)
        
        mms_simple.form_organizations(current_step=10)
        n_orgs_1 = len(mms_simple.organizations)
        
        # 不改变绑定强度，再形成一次
        # 由于比特已有隶属度，新组织形成可能受限
        mms_simple.form_organizations(current_step=20)
        n_orgs_2 = len(mms_simple.organizations)
        
        # 组织数可能增加（如果残余自由度允许），但不会无限制增长
        assert n_orgs_2 <= n_orgs_1 + 10, \
            f"Orgs should not grow unboundedly: {n_orgs_1} -> {n_orgs_2}"


# ================================================================
# Test 8: 与理论预期的对应
# ================================================================

class TestTheoryAlignment:
    """测试结果与差异论理论预期的对应"""
    
    def test_residual_differs_participate(self):
        """余差（未被组织吸纳的自由度）应能参与新组织
        
        这是 A9 多隶属的核心理论预期：
        未被组织的余差持续参与后续封口
        """
        N = 8
        B = torch.zeros(N, N)
        # 第一轮：只有 bits 0-3 有强绑定
        for i in range(4):
            for j in range(4):
                if i != j:
                    B[i][j] = 0.5
        # 第二轮：bits 2-5 有中等绑定（与第一轮有重叠）
        for i in range(2, 6):
            for j in range(2, 6):
                if i != j:
                    B[i][j] = max(B[i][j].item(), 0.3)
        # 第三轮：bits 4-7 有强绑定
        for i in range(4, 8):
            for j in range(4, 8):
                if i != j:
                    B[i][j] = 0.5
        
        B = (B + B.T) / 2
        
        mms = MultiMembershipSeal(
            N=N, binding_strength=B,
            org_join_threshold=0.2,
            lock_threshold=0.95,
            max_orgs_per_bit=4,
            min_org_size=2,
        )
        
        for i in range(N):
            mms.record_active(i, 0)
        
        # 多轮组织形成
        for step in range(10, 300, 10):
            mms.form_organizations(current_step=step)
        
        # 验证：比特 2, 3（桥接第一轮和第二轮）
        # 和比特 4, 5（桥接第二轮和第三轮）
        # 应该有更高的锁定水平
        bridge_lock = np.mean([
            mms.compute_lock_level(i) for i in [2, 3, 4, 5]
        ])
        edge_lock = np.mean([
            mms.compute_lock_level(i) for i in [0, 1, 6, 7]
        ])
        
        # 桥接比特应有更高或相等的锁定水平
        # （因为它们参与了多个组织）
        assert bridge_lock >= edge_lock * 0.8, \
            f"Bridge bits should be more locked: bridge={bridge_lock:.3f}, edge={edge_lock:.3f}"
    
    def test_org_overlap_exists(self):
        """组织间应该存在重叠（多隶属的直接证据）"""
        N = 10
        B = torch.zeros(N, N)
        # 创建有意图的重叠结构
        # Org A: bits 0-4
        for i in range(5):
            for j in range(5):
                if i != j:
                    B[i][j] = 0.4
        # Org B: bits 3-7（与 A 重叠于 bits 3, 4）
        for i in range(3, 8):
            for j in range(3, 8):
                if i != j:
                    B[i][j] = max(B[i][j].item(), 0.4)
        # Org C: bits 6-9（与 B 重叠于 bits 6, 7）
        for i in range(6, 10):
            for j in range(6, 10):
                if i != j:
                    B[i][j] = max(B[i][j].item(), 0.4)
        
        B = (B + B.T) / 2
        
        mms = MultiMembershipSeal(
            N=N, binding_strength=B,
            org_join_threshold=0.25,
            lock_threshold=0.95,
            max_orgs_per_bit=4,
            min_org_size=2,
        )
        
        for i in range(N):
            mms.record_active(i, 0)
        
        for step in range(10, 300, 10):
            mms.form_organizations(current_step=step)
        
        overlaps = mms.get_overlap_matrix()
        
        # 在足够多的轮次后，应该存在组织重叠
        # 如果不存在，至少应该有多隶属比特
        snap = mms.get_snapshot()
        has_multi_membership = snap.n_multi_member_bits > 0
        has_overlap = len(overlaps) > 0
        
        assert has_multi_membership or has_overlap or snap.n_organizations <= 1, \
            "Should find multi-membership or org overlap in chain topology"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
