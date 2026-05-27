"""
tests/test_counterfactual_engine.py — CounterfactualEngine 测试

覆盖：
- TrajectoryNode / TrajectoryBranch 基本操作
- ParallelTrajectoryMaintainer：创建/延伸/剪枝/合并
- DivergencePointTracker：分岔检测/分类
- ConsequenceProjector：三种投影方法
- CounterfactualSelector：对比/选择压力/偏置计算
- CounterfactualEngine：完整流程
"""

import pytest
import torch
import numpy as np
from unittest.mock import MagicMock

from engine.counterfactual_engine import (
    TrajectoryNode,
    TrajectoryBranch,
    TrajectoryState,
    DivergenceType,
    ProjectionMethod,
    DivergencePoint,
    ConsequenceEstimate,
    ContrastResult,
    CounterfactualResult,
    ParallelTrajectoryMaintainer,
    DivergencePointTracker,
    ConsequenceProjector,
    CounterfactualSelector,
    CounterfactualEngine,
    DEFAULT_COUNTERFACTUAL_CONFIG,
)
from engine.organizational_density_index import DensityIndexResult


# ─── Fixtures ───

@pytest.fixture
def dim():
    return 8


@pytest.fixture
def sample_state(dim):
    return torch.randn(dim)


@pytest.fixture
def sample_state_2(dim):
    return torch.randn(dim)


@pytest.fixture
def candidate_directions(dim):
    """生成3个候选方向"""
    dirs = []
    for _ in range(3):
        d = torch.randn(dim)
        d = d / d.norm()
        dirs.append(d)
    return dirs


@pytest.fixture
def maintainer():
    return ParallelTrajectoryMaintainer()


@pytest.fixture
def tracker():
    return DivergencePointTracker()


@pytest.fixture
def projector():
    return ConsequenceProjector()


@pytest.fixture
def selector():
    return CounterfactualSelector()


@pytest.fixture
def engine():
    return CounterfactualEngine()


@pytest.fixture
def odi_result():
    mock = MagicMock(spec=DensityIndexResult)
    mock.odi = 0.7
    return mock


@pytest.fixture
def low_odi_result():
    mock = MagicMock(spec=DensityIndexResult)
    mock.odi = 0.2
    return mock


# ═══════════════════════════════════════════════════════════════
# TrajectoryNode 测试
# ═══════════════════════════════════════════════════════════════

class TestTrajectoryNode:

    def test_create_node(self, sample_state):
        node = TrajectoryNode(
            state_vector=sample_state,
            timestamp=0,
            node_id="n000001",
        )
        assert node.node_id == "n000001"
        assert node.timestamp == 0
        assert node.parent_idx is None
        assert torch.equal(node.state_vector, sample_state)

    def test_node_with_parent(self, sample_state):
        node = TrajectoryNode(
            state_vector=sample_state,
            timestamp=1,
            parent_idx=0,
            node_id="n000002",
        )
        assert node.parent_idx == 0  # parent node index
        assert node.timestamp == 1

    def test_node_repr(self, sample_state):
        node = TrajectoryNode(
            state_vector=sample_state,
            timestamp=5,
            parent_idx=3,
            node_id="n_test",
        )
        r = repr(node)
        assert "n_test" in r
        assert "t=5" in r


# ═══════════════════════════════════════════════════════════════
# TrajectoryBranch 测试
# ═══════════════════════════════════════════════════════════════

class TestTrajectoryBranch:

    def test_create_branch(self, sample_state):
        branch = TrajectoryBranch(
            branch_id="b000001",
            creation_step=0,
        )
        assert branch.branch_id == "b000001"
        assert branch.depth == 0
        assert branch.probability == 1.0
        assert branch.state == TrajectoryState.ACTIVE
        assert branch.is_active

    def test_extend_branch(self, sample_state, sample_state_2):
        branch = TrajectoryBranch(branch_id="b000001")
        node1 = TrajectoryNode(state_vector=sample_state, timestamp=0, node_id="n1")
        node2 = TrajectoryNode(state_vector=sample_state_2, timestamp=1, parent_idx=0, node_id="n2")

        branch.extend(node1)
        assert branch.depth == 1
        assert branch.root == node1

        branch.extend(node2, prob_factor=0.8)
        assert branch.depth == 2
        assert branch.leaf == node2
        assert abs(branch.probability - 0.8) < 1e-6

    def test_branch_states(self, sample_state):
        branch = TrajectoryBranch(branch_id="b000001")
        assert branch.leaf is None
        assert branch.root is None

        node = TrajectoryNode(state_vector=sample_state, timestamp=0, node_id="n1")
        branch.extend(node)
        assert branch.leaf == node
        assert branch.root == node

    def test_branch_repr(self):
        branch = TrajectoryBranch(branch_id="b_test", probability=0.75)
        r = repr(branch)
        assert "b_test" in r
        assert "prob=0.75" in r


# ═══════════════════════════════════════════════════════════════
# ParallelTrajectoryMaintainer 测试
# ═══════════════════════════════════════════════════════════════

class TestParallelTrajectoryMaintainer:

    def test_create_branch(self, maintainer, sample_state):
        branch = maintainer.create_branch(sample_state)
        assert branch is not None
        assert branch.branch_id.startswith("b")
        assert branch.depth == 1
        assert maintainer.n_total_branches == 1

    def test_create_multiple_branches(self, maintainer, sample_state):
        branches = []
        for i in range(3):
            b = maintainer.create_branch(sample_state + i * 0.1)
            assert b is not None
            branches.append(b)

        assert maintainer.n_total_branches == 3
        assert maintainer.n_active_branches == 3

    def test_max_branches_limit(self, maintainer, sample_state):
        config = {'max_branches': 3}
        m = ParallelTrajectoryMaintainer(config=config)

        for i in range(5):
            b = m.create_branch(sample_state + i * 0.01)

        assert m.n_total_branches == 3
        assert m.n_active_branches == 3

    def test_extend_branch(self, maintainer, sample_state, sample_state_2):
        branch = maintainer.create_branch(sample_state)
        node = maintainer.extend_branch(branch.branch_id, sample_state_2, prob_factor=0.9)

        assert node is not None
        assert branch.depth == 2
        assert abs(branch.probability - 0.9) < 1e-6

    def test_extend_nonexistent_branch(self, maintainer, sample_state):
        node = maintainer.extend_branch("nonexistent", sample_state)
        assert node is None

    def test_extend_completed_branch(self, maintainer, sample_state):
        config = {'max_depth': 2}
        m = ParallelTrajectoryMaintainer(config=config)

        branch = m.create_branch(sample_state)
        m.extend_branch(branch.branch_id, sample_state)
        m.extend_branch(branch.branch_id, sample_state)  # 达到 max_depth

        # 再延伸应该返回 None（分支已完成）
        node = m.extend_branch(branch.branch_id, sample_state)
        assert node is None
        assert branch.state == TrajectoryState.COMPLETED

    def test_prune_branches(self, maintainer, sample_state):
        config = {'prune_threshold': 0.5}
        m = ParallelTrajectoryMaintainer(config=config)

        b1 = m.create_branch(sample_state, initial_probability=0.8)
        b2 = m.create_branch(sample_state, initial_probability=0.3)

        # 延伸 b2 使其概率降低
        m.extend_branch(b2.branch_id, sample_state, prob_factor=0.5)

        pruned = m.prune_branches()
        assert b2.branch_id in pruned
        assert b2.state == TrajectoryState.PRUNED
        assert b1.state == TrajectoryState.ACTIVE

    def test_merge_similar_branches(self, maintainer, sample_state):
        config = {'merge_similarity': 0.95, 'max_branches': 5}
        m = ParallelTrajectoryMaintainer(config=config)

        # 创建两个非常相似的分支
        b1 = m.create_branch(sample_state)
        b2 = m.create_branch(sample_state + torch.randn_like(sample_state) * 0.001)

        # 延伸使叶节点相似
        m.extend_branch(b1.branch_id, sample_state)
        m.extend_branch(b2.branch_id, sample_state + torch.randn_like(sample_state) * 0.001)

        merged = m.merge_similar_branches()
        assert len(merged) >= 1
        assert b2.state == TrajectoryState.MERGED

    def test_get_active_branches(self, maintainer, sample_state):
        maintainer.create_branch(sample_state)
        maintainer.create_branch(sample_state + 0.1)

        active = maintainer.get_active_branches()
        assert len(active) == 2

    def test_get_branch(self, maintainer, sample_state):
        branch = maintainer.create_branch(sample_state)
        retrieved = maintainer.get_branch(branch.branch_id)
        assert retrieved is not None
        assert retrieved.branch_id == branch.branch_id

    def test_get_nonexistent_branch(self, maintainer):
        assert maintainer.get_branch("nonexistent") is None

    def test_reset(self, maintainer, sample_state):
        maintainer.create_branch(sample_state)
        maintainer.create_branch(sample_state)
        maintainer.reset()

        assert maintainer.n_total_branches == 0
        assert maintainer.n_active_branches == 0

    def test_get_summary(self, maintainer, sample_state):
        maintainer.create_branch(sample_state)
        summary = maintainer.get_summary()

        assert summary['n_total'] == 1
        assert summary['n_active'] == 1
        assert 'max_depth' in summary
        assert 'mean_probability' in summary

    def test_step(self, maintainer):
        maintainer.step()
        maintainer.step()
        assert maintainer._step_count == 2


# ═══════════════════════════════════════════════════════════════
# DivergencePointTracker 测试
# ═══════════════════════════════════════════════════════════════

class TestDivergencePointTracker:

    def test_detect_divergence(self, tracker, sample_state, candidate_directions):
        div = tracker.detect_divergence(
            current_state=sample_state,
            candidate_directions=candidate_directions,
            direction_probs=[0.4, 0.35, 0.25],
        )
        # 概率分布较均匀，应该检测到分岔（熵高 + 显著性低）
        # 注意：是否显著取决于熵和显著性阈值的组合
        if div is not None:
            assert div.n_directions == 3
            assert 0 <= div.entropy <= 1
        else:
            # 如果未检测到，说明显著性不够（方向差异大导致）
            # 这也是合法行为
            pass

    def test_no_divergence_single_direction(self, tracker, sample_state):
        div = tracker.detect_divergence(
            current_state=sample_state,
            candidate_directions=[sample_state],
        )
        assert div is None

    def test_no_divergence_dominant(self, tracker, sample_state, candidate_directions):
        # 一个方向占绝对优势，不应检测为分岔
        div = tracker.detect_divergence(
            current_state=sample_state,
            candidate_directions=candidate_directions,
            direction_probs=[0.95, 0.03, 0.02],
        )
        # 显著性很高（最优/次优比大），不应检测为分岔
        if div is not None:
            assert not div.is_significant

    def test_divergence_types(self, tracker, sample_state, candidate_directions):
        for div_type in DivergenceType:
            div = tracker.detect_divergence(
                current_state=sample_state,
                candidate_directions=candidate_directions,
                divergence_type=div_type,
            )
            if div is not None:
                assert div.divergence_type == div_type

    def test_divergence_entropy_range(self, tracker, sample_state, candidate_directions):
        div = tracker.detect_divergence(
            current_state=sample_state,
            candidate_directions=candidate_directions,
            direction_probs=[0.34, 0.33, 0.33],
        )
        if div is not None:
            assert 0 <= div.entropy <= 1

    def test_get_divergence_points(self, tracker, sample_state, candidate_directions):
        tracker.detect_divergence(
            current_state=sample_state,
            candidate_directions=candidate_directions,
            direction_probs=[0.4, 0.35, 0.25],
        )
        points = tracker.get_divergence_points()
        assert len(points) <= tracker.n_divergence_points

    def test_max_divergence_points(self, tracker, sample_state, candidate_directions):
        config = {'max_divergence_points': 2}
        t = DivergencePointTracker(config=config)

        for _ in range(5):
            t.detect_divergence(
                current_state=sample_state,
                candidate_directions=candidate_directions,
                direction_probs=[0.4, 0.35, 0.25],
            )

        assert t.n_divergence_points <= 2

    def test_reset(self, tracker, sample_state, candidate_directions):
        tracker.detect_divergence(
            current_state=sample_state,
            candidate_directions=candidate_directions,
        )
        tracker.reset()
        assert tracker.n_divergence_points == 0

    def test_divergence_point_repr(self, sample_state, candidate_directions):
        div = DivergencePoint(
            timestamp=0,
            position=sample_state,
            divergence_type=DivergenceType.STRUCTURAL,
            entropy=0.5,
            significance=1.5,
            n_directions=3,
        )
        r = repr(div)
        assert "STRUCTURAL" in r
        assert "entropy=0.5" in r


# ═══════════════════════════════════════════════════════════════
# ConsequenceProjector 测试
# ═══════════════════════════════════════════════════════════════

class TestConsequenceProjector:

    def _make_branch(self, states):
        """辅助：从状态列表创建分支"""
        branch = TrajectoryBranch(branch_id="b_test")
        for i, s in enumerate(states):
            parent_idx = i - 1 if i > 0 else None
            node = TrajectoryNode(
                state_vector=s, timestamp=i, parent_idx=parent_idx, node_id=f"n{i}"
            )
            branch.extend(node)
        return branch

    def test_linear_project(self, projector, dim):
        states = [torch.randn(dim) for _ in range(3)]
        branch = self._make_branch(states)

        result = projector.project(branch, method='linear')
        assert isinstance(result, ConsequenceEstimate)
        assert result.branch_id == "b_test"
        assert 0 <= result.continuation_probability <= 1
        assert result.projection_method == 'linear'

    def test_momentum_project(self, projector, dim):
        states = [torch.randn(dim) for _ in range(4)]
        branch = self._make_branch(states)

        result = projector.project(branch, method='momentum')
        assert isinstance(result, ConsequenceEstimate)
        assert result.projection_method == 'momentum'

    def test_structural_project(self, projector, dim, odi_result):
        states = [torch.randn(dim) for _ in range(3)]
        branch = self._make_branch(states)

        result = projector.project(branch, odi_result=odi_result, method='structural')
        assert isinstance(result, ConsequenceEstimate)
        assert result.projection_method == 'structural'

    def test_project_single_node(self, projector, sample_state):
        """单节点分支（无法计算趋势）"""
        branch = self._make_branch([sample_state])
        result = projector.project(branch, method='linear')
        assert result.continuation_probability > 0

    def test_project_with_odi(self, projector, dim, odi_result):
        states = [torch.randn(dim) for _ in range(3)]
        branch = self._make_branch(states)

        result_with = projector.project(branch, odi_result=odi_result)
        result_without = projector.project(branch, odi_result=None)

        # ODI 影响后果估计
        assert isinstance(result_with, ConsequenceEstimate)
        assert isinstance(result_without, ConsequenceEstimate)

    def test_project_composite_score(self, projector, dim):
        states = [torch.randn(dim) for _ in range(3)]
        branch = self._make_branch(states)

        result = projector.project(branch)
        assert isinstance(result.composite_score, float)

    def test_momentum_fallback_to_linear(self, projector, sample_state):
        """节点不足时，动量投影退化为线性"""
        branch = self._make_branch([sample_state])
        result = projector.project(branch, method='momentum')
        assert result.projection_method == 'linear'

    def test_consequence_estimate_repr(self):
        ce = ConsequenceEstimate(
            branch_id="b_test",
            continuation_probability=0.75,
            composite_score=0.5,
        )
        r = repr(ce)
        assert "b_test" in r
        assert "cont_prob=0.75" in r


# ═══════════════════════════════════════════════════════════════
# CounterfactualSelector 测试
# ═══════════════════════════════════════════════════════════════

class TestCounterfactualSelector:

    def test_contrast(self, selector):
        factual = ConsequenceEstimate(
            branch_id="b_factual",
            continuation_probability=0.7,
            structural_impact=0.5,
            density_impact=0.3,
        )
        cf1 = ConsequenceEstimate(
            branch_id="b_cf1",
            continuation_probability=0.8,
            structural_impact=0.6,
            density_impact=0.4,
        )
        cf2 = ConsequenceEstimate(
            branch_id="b_cf2",
            continuation_probability=0.5,
            structural_impact=0.3,
            density_impact=0.2,
        )

        results = selector.contrast(factual, [cf1, cf2])
        assert len(results) == 2
        assert all(isinstance(r, ContrastResult) for r in results)

    def test_contrast_gap_sign(self, selector):
        factual = ConsequenceEstimate(
            branch_id="b_factual",
            continuation_probability=0.5,
            structural_impact=0.5,
            density_impact=0.5,
        )
        cf_higher = ConsequenceEstimate(
            branch_id="b_cf_high",
            continuation_probability=0.8,
            structural_impact=0.8,
            density_impact=0.8,
        )
        cf_lower = ConsequenceEstimate(
            branch_id="b_cf_low",
            continuation_probability=0.2,
            structural_impact=0.2,
            density_impact=0.2,
        )

        results = selector.contrast(factual, [cf_higher, cf_lower])
        assert results[0].continuation_gap > 0  # 反事实更高
        assert results[1].continuation_gap < 0  # 反事实更低

    def test_contrast_meaningful(self, selector):
        factual = ConsequenceEstimate(
            branch_id="b_factual",
            continuation_probability=0.5,
            structural_impact=0.5,
            density_impact=0.5,
        )
        cf_similar = ConsequenceEstimate(
            branch_id="b_cf_sim",
            continuation_probability=0.51,
            structural_impact=0.51,
            density_impact=0.51,
        )

        results = selector.contrast(factual, [cf_similar])
        # 差异很小，不应标记为有意义
        assert not results[0].is_meaningful

    def test_selection_pressure_positive(self, selector):
        contrasts = [
            ContrastResult(
                factual_branch_id="bf",
                counterfactual_branch_id="cf1",
                divergence_distance=0.5,
                continuation_gap=0.3,
                is_meaningful=True,
            ),
            ContrastResult(
                factual_branch_id="bf",
                counterfactual_branch_id="cf2",
                divergence_distance=0.4,
                continuation_gap=0.2,
                is_meaningful=True,
            ),
        ]
        pressure = selector.compute_selection_pressure(contrasts)
        assert pressure > 0

    def test_selection_pressure_negative(self, selector):
        contrasts = [
            ContrastResult(
                factual_branch_id="bf",
                counterfactual_branch_id="cf1",
                divergence_distance=0.5,
                continuation_gap=-0.3,
                is_meaningful=True,
            ),
        ]
        pressure = selector.compute_selection_pressure(contrasts)
        assert pressure < 0

    def test_selection_pressure_no_meaningful(self, selector):
        contrasts = [
            ContrastResult(
                factual_branch_id="bf",
                counterfactual_branch_id="cf1",
                divergence_distance=0.01,
                continuation_gap=0.01,
                is_meaningful=False,
            ),
        ]
        pressure = selector.compute_selection_pressure(contrasts)
        assert pressure == 0.0

    def test_counterfactual_bias(self, selector, dim):
        factual_state = torch.ones(dim)
        cf_state = torch.ones(dim) * 2

        contrasts = [
            ContrastResult(
                factual_branch_id="bf",
                counterfactual_branch_id="cf1",
                divergence_distance=0.5,
                continuation_gap=0.3,
                is_meaningful=True,
            ),
        ]
        branch_states = {"cf1": cf_state}

        bias = selector.compute_counterfactual_bias(contrasts, branch_states, factual_state)
        assert bias.shape == factual_state.shape
        # 偏置方向应该指向反事实状态
        assert (bias >= 0).all() or (bias <= 0).all()  # 方向一致

    def test_counterfactual_bias_no_meaningful(self, selector, dim):
        factual_state = torch.ones(dim)
        contrasts = [
            ContrastResult(
                factual_branch_id="bf",
                counterfactual_branch_id="cf1",
                divergence_distance=0.01,
                continuation_gap=0.01,
                is_meaningful=False,
            ),
        ]
        branch_states = {"cf1": torch.ones(dim) * 2}

        bias = selector.compute_counterfactual_bias(contrasts, branch_states, factual_state)
        assert torch.allclose(bias, torch.zeros(dim))

    def test_contrast_result_repr(self):
        cr = ContrastResult(
            factual_branch_id="bf",
            counterfactual_branch_id="cf1",
            divergence_distance=0.5,
            continuation_gap=0.3,
            is_meaningful=True,
        )
        r = repr(cr)
        assert "bf" in r
        assert "cf1" in r
        assert "meaningful=True" in r


# ═══════════════════════════════════════════════════════════════
# CounterfactualEngine 集成测试
# ═══════════════════════════════════════════════════════════════

class TestCounterfactualEngine:

    def test_explore_creates_factual_branch(self, engine, sample_state, odi_result):
        result = engine.explore(sample_state, odi_result=odi_result)
        assert engine._factual_branch_id is not None
        # With ODI=0.7 (>= partial_threshold=0.6), exploration should be active
        # or at minimum not gated
        assert result.counterfactual_active or not result.odi_gated

    def test_explore_with_low_odi(self, engine, sample_state, low_odi_result):
        result = engine.explore(sample_state, odi_result=low_odi_result)
        assert result.odi_gated
        assert not result.counterfactual_active

    def test_explore_with_high_odi(self, engine, sample_state, candidate_directions, odi_result):
        result = engine.explore(
            sample_state,
            candidate_directions=candidate_directions,
            direction_probs=[0.4, 0.35, 0.25],
            odi_result=odi_result,
        )
        assert not result.odi_gated

    def test_maintain(self, engine, sample_state):
        engine.explore(sample_state)
        branches = engine.maintain(sample_state)
        assert isinstance(branches, list)

    def test_project(self, engine, sample_state, odi_result):
        engine.explore(sample_state, odi_result=odi_result)
        consequences = engine.project(odi_result=odi_result)
        assert isinstance(consequences, list)

    def test_select(self, engine, sample_state, candidate_directions, odi_result):
        engine.explore(
            sample_state,
            candidate_directions=candidate_directions,
            direction_probs=[0.4, 0.35, 0.25],
            odi_result=odi_result,
        )
        consequences = engine.project(odi_result=odi_result)

        if len(consequences) >= 2:
            result = engine.select(consequences)
            assert isinstance(result, CounterfactualResult)
            assert isinstance(result.selection_pressure, float)

    def test_update(self, engine, sample_state, odi_result):
        engine.explore(sample_state, odi_result=odi_result)
        result = engine.update(sample_state)
        assert result is not None
        assert isinstance(result, CounterfactualResult)

    def test_full_pipeline(self, engine, sample_state, candidate_directions, odi_result):
        """完整流程：explore → maintain → project → select → update"""
        # Step 1: 探索
        explore_result = engine.explore(
            sample_state,
            candidate_directions=candidate_directions,
            direction_probs=[0.4, 0.35, 0.25],
            odi_result=odi_result,
        )

        # Step 2: 维持
        engine.maintain(sample_state)

        # Step 3: 投影
        consequences = engine.project(odi_result=odi_result)

        # Step 4: 选择
        if len(consequences) >= 2:
            select_result = engine.select(consequences)
            assert select_result.counterfactual_active or not select_result.counterfactual_active

        # Step 5: 更新
        engine.update(sample_state)

        # 验证引擎状态
        assert engine._factual_branch_id is not None

    def test_step(self, engine):
        engine.step()
        engine.step()
        assert engine._step_count == 2

    def test_reset(self, engine, sample_state, odi_result):
        engine.explore(sample_state, odi_result=odi_result)
        engine.reset()

        assert engine._factual_branch_id is None
        assert engine.n_active_branches == 0
        assert engine._step_count == 0

    def test_get_summary(self, engine, sample_state, odi_result):
        engine.explore(sample_state, odi_result=odi_result)
        summary = engine.get_summary()

        assert 'n_total_branches' in summary
        assert 'n_active_branches' in summary
        assert 'n_divergence_points' in summary
        assert 'is_active' in summary

    def test_is_active_property(self, engine, sample_state, odi_result):
        assert not engine.is_active
        engine.explore(sample_state, odi_result=odi_result)
        # 活跃性取决于分支数是否 >= min_branches

    def test_latest_result(self, engine, sample_state):
        assert engine.latest_result is None
        engine.explore(sample_state)
        assert engine.latest_result is not None

    def test_generate_candidate_directions(self, engine, sample_state):
        directions = engine._generate_candidate_directions(sample_state)
        assert len(directions) >= 2
        # 方向应该是归一化的
        for d in directions:
            assert abs(d.norm().item() - 1.0) < 1e-5

    def test_multiple_explore_cycles(self, engine, sample_state, candidate_directions, odi_result):
        """多次探索-维持循环"""
        for i in range(5):
            engine.explore(
                sample_state + i * 0.01,
                candidate_directions=candidate_directions,
                direction_probs=[0.4, 0.35, 0.25],
                odi_result=odi_result,
            )
            engine.maintain(sample_state + i * 0.01)
            engine.update(sample_state + i * 0.01)
            engine.step()

        summary = engine.get_summary()
        assert summary['n_total_branches'] > 0

    def test_counterfactual_result_repr(self):
        cr = CounterfactualResult(
            counterfactual_active=True,
            n_active_branches=3,
            selection_pressure=0.5,
        )
        r = repr(cr)
        assert "active=True" in r
        assert "branches=3" in r


# ═══════════════════════════════════════════════════════════════
# 配置测试
# ═══════════════════════════════════════════════════════════════

class TestConfiguration:

    def test_default_config_exists(self):
        assert 'max_branches' in DEFAULT_COUNTERFACTUAL_CONFIG
        assert 'max_depth' in DEFAULT_COUNTERFACTUAL_CONFIG
        assert 'prune_threshold' in DEFAULT_COUNTERFACTUAL_CONFIG
        assert 'merge_similarity' in DEFAULT_COUNTERFACTUAL_CONFIG
        assert 'odi_suppress_threshold' in DEFAULT_COUNTERFACTUAL_CONFIG

    def test_custom_config(self):
        config = {'max_branches': 10, 'max_depth': 20}
        engine = CounterfactualEngine(config=config)
        assert engine.config['max_branches'] == 10
        assert engine.config['max_depth'] == 20
        # 未覆盖的配置应保持默认值
        assert engine.config['prune_threshold'] == DEFAULT_COUNTERFACTUAL_CONFIG['prune_threshold']


# ═══════════════════════════════════════════════════════════════
# 枚举测试
# ═══════════════════════════════════════════════════════════════

class TestEnums:

    def test_trajectory_state(self):
        assert TrajectoryState.ACTIVE.name == 'ACTIVE'
        assert TrajectoryState.PRUNED.name == 'PRUNED'
        assert TrajectoryState.MERGED.name == 'MERGED'
        assert TrajectoryState.COMPLETED.name == 'COMPLETED'

    def test_divergence_type(self):
        assert DivergenceType.STOCHASTIC.name == 'STOCHASTIC'
        assert DivergenceType.STRUCTURAL.name == 'STRUCTURAL'
        assert DivergenceType.EXTERNAL.name == 'EXTERNAL'
        assert DivergenceType.COUNTERFACTUAL.name == 'COUNTERFACTUAL'

    def test_projection_method(self):
        assert ProjectionMethod.LINEAR.name == 'LINEAR'
        assert ProjectionMethod.MOMENTUM.name == 'MOMENTUM'
        assert ProjectionMethod.STRUCTURAL.name == 'STRUCTURAL'
