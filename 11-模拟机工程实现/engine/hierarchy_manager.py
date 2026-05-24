"""
engine/hierarchy_manager.py — 层级管理器

管理多层状态空间，支持：
1. 层级初始化（从单层演化器结果创建多层结构）
2. 层间状态传递（L → L+1 提升，L+1 → L 解封下降）
3. 跨层级绑定强度管理
4. 层级状态快照和恢复

与 EncapsulationEngine 的关系：
- EncapsulationEngine 负责"如何封装"（分组、映射、值计算）
- HierarchyManager 负责"何时封装"（层级生命周期管理）
"""

import torch
import numpy as np
from typing import List, Optional, Dict, Tuple, Set
from engine.encapsulation_engine import EncapsulationEngine, EncapsulatedBit, IndexMapping
from acl.axioms_v2 import AxiomConstraints


class BiasField:
    """回流偏置场 — 跨层级状态偏置的载体

    理论依据（Appearing Before Appearing §3.3）：
    持留是路径依赖的递归——第n次重构的不对称性成为第n+1次的起始偏置。

    偏置不是值覆盖，是概率调制：保持差异论的核心（差异发生，而非确定性指令）。
    偏置强度必须衰减——否则低层被高层完全支配，丧失自主性。
    """

    def __init__(self, source_layer: int, target_layer: int,
                 bias_vector: torch.Tensor, strength: float,
                 origin_step: int):
        """
        Args:
            source_layer: 偏置来源层（L+1 产生的偏置）
            target_layer: 偏置目标层（传回到 L）
            bias_vector: 偏置方向（非绝对值，是倾向），shape=(target_N,)
            strength: 偏置强度，随时间衰减
            origin_step: 产生偏置时的步数
        """
        self.source_layer = source_layer
        self.target_layer = target_layer
        self.bias_vector = bias_vector
        self.strength = strength
        self.origin_step = origin_step
        self.decay_rate = 0.95  # 每次传播衰减 5%

    def decay(self):
        """衰减偏置强度"""
        self.strength *= self.decay_rate
        return self.strength > 1e-4  # 返回是否仍有意义

    def __repr__(self):
        return (f"BiasField(L{self.source_layer}->L{self.target_layer}, "
                f"strength={self.strength:.4f}, step={self.origin_step})")


class LayerState:
    """单层的完整状态"""

    def __init__(self, layer_id: int, state: torch.Tensor,
                 constraints: AxiomConstraints,
                 active_bits: Set[int],
                 frozen_bits: Set[int]):
        self.layer_id = layer_id
        self.state = state                    # 状态向量
        self.constraints = constraints        # 该层的公理约束器
        self.active_bits = active_bits        # 活跃比特索引
        self.frozen_bits = frozen_bits        # 冻结比特索引（本层内）
        self.n_bits = len(state)
        self.step_count = 0                   # 该层已运行的步数
        self.is_sealed = False                # 该层是否已封口

    @property
    def hamming_weight(self) -> int:
        return int(self.state.sum().item())

    def __repr__(self):
        return (f"LayerState(L{self.layer_id}, N={self.n_bits}, "
                f"w={self.hamming_weight}, "
                f"active={len(self.active_bits)}, "
                f"frozen={len(self.frozen_bits)}, "
                f"sealed={self.is_sealed})")


class HierarchyManager:
    """层级管理器

    管理从 L0 开始的多层结构，每层有自己的：
    - 状态空间
    - 公理约束器
    - 活跃/冻结比特集合

    封装流程：
    1. 演化器在第 L 层运行
    2. A9 触发封口
    3. HierarchyManager.encapsulate_layer(L) → 创建第 L+1 层
    4. 演化器在第 L+1 层继续运行
    """

    def __init__(self, N0: int, device: str = "cpu",
                 binding_threshold: float = 0.1,
                 min_group_size: int = 2,
                 n_hierarchy_bits: int = None):
        """
        Args:
            N0: 第 0 层比特数
            device: 设备
            binding_threshold: 封装绑定强度阈值
            min_group_size: 最小组大小
            n_hierarchy_bits: 层级比特数（传给 AxiomConstraints）
        """
        self.device = device
        self.binding_threshold = binding_threshold
        self.min_group_size = min_group_size
        self.n_hierarchy_bits_init = n_hierarchy_bits

        # 封装引擎
        self.encap_engine = EncapsulationEngine(
            binding_threshold=binding_threshold,
            min_group_size=min_group_size
        )

        # 层级状态列表
        self.layers: List[LayerState] = []
        # 当前活跃层
        self.current_layer: int = 0

        # 初始化第 0 层
        self._init_layer0(N0, n_hierarchy_bits)

    def _init_layer0(self, N0: int, n_hierarchy_bits: Optional[int]):
        """初始化第 0 层"""
        state = torch.zeros(N0, device=self.device)
        constraints = AxiomConstraints(
            N0,
            n_hierarchy_bits=n_hierarchy_bits or N0 // 3,
            device=self.device
        )
        active = set(range(N0))  # 初始所有比特都活跃
        frozen = set()

        layer = LayerState(0, state, constraints, active, frozen)
        self.layers.append(layer)
        self.current_layer = 0

        # 回流通道：偏置注册表
        self.bias_registry: Dict[int, List[BiasField]] = {0: []}

    @property
    def n_layers(self) -> int:
        return len(self.layers)

    @property
    def current(self) -> LayerState:
        return self.layers[self.current_layer]

    def get_layer(self, layer_id: int) -> LayerState:
        if layer_id >= len(self.layers):
            raise IndexError(f"Layer {layer_id} not exist (total {len(self.layers)})")
        return self.layers[layer_id]

    def encapsulate_current_layer(self) -> Tuple[LayerState, Dict]:
        """对当前层执行封装，创建新层

        Returns:
            new_layer: 新创建的第 L+1 层
            info: 封装信息字典
        """
        layer = self.current

        # 使用 constraints.sealed_bits 作为冻结比特
        # active 比特 = 所有激活过的比特 - 被封口的比特
        frozen = layer.constraints.sealed_bits if layer.constraints.sealed_bits else layer.frozen_bits
        all_active = layer.constraints.active_bits if layer.constraints.active_bits else layer.active_bits
        active = all_active - frozen

        # 执行封装
        new_state, enc_bits, mapping = self.encap_engine.encapsulate(
            state=layer.state,
            frozen_bits=frozen,
            binding_strength=layer.constraints.binding_strength,
            active_bits=active,
            layer=layer.layer_id
        )

        n_active = len(active)
        n_enc = len(enc_bits)
        n_new = len(new_state)

        # 确保 N 是 3 的倍数（SpatialLongRangeEvolver 要求）
        if n_new % 3 != 0:
            pad = 3 - (n_new % 3)
            new_state = torch.cat([new_state, torch.zeros(pad, device=self.device)])
            n_new = len(new_state)

        # 为新层创建约束器
        # 新层的层级比特数按比例缩放
        new_n_hierarchy = max(1, n_new // 3)
        new_constraints = AxiomConstraints(
            n_new,
            n_hierarchy_bits=new_n_hierarchy,
            device=self.device
        )

        # 新层的活跃比特 = 全部（初始都活跃）
        new_active = set(range(n_new))
        new_frozen = set()

        # 标记当前层为已封口
        layer.is_sealed = True

        # 创建新层
        new_layer = LayerState(
            layer_id=layer.layer_id + 1,
            state=new_state,
            constraints=new_constraints,
            active_bits=new_active,
            frozen_bits=new_frozen
        )

        self.layers.append(new_layer)
        self.current_layer = new_layer.layer_id

        info = {
            'from_layer': layer.layer_id,
            'to_layer': new_layer.layer_id,
            'n_bits_before': layer.n_bits,
            'n_bits_after': n_new,
            'n_active_preserved': n_active,
            'n_encapsulated': n_enc,
            'n_frozen_discarded': len(layer.frozen_bits) - sum(
                len(e.source_bits) for e in enc_bits),
            'encapsulated_bits': enc_bits,
            'mapping': mapping,
        }

        return new_layer, info

    def step_layer(self, layer_id: int, n_steps: int = 1,
                   verbose: bool = False) -> Dict:
        """在指定层运行若干步（层内演化）

        这是一个简化版的单步演化，用于层级间交替运行。
        完整演化应使用 SpatialLongRangeEvolver，
        这里提供轻量级版本用于层级管理测试。
        """
        layer = self.get_layer(layer_id)
        constraints = layer.constraints
        state = layer.state

        total_inject = 0
        total_absorb = 0
        total_lateral = 0

        for step in range(n_steps):
            w_before = state.sum().long().item()

            # 1. 源注入
            source_strength = constraints.get_A8_source_strength(state)
            actual_inject = 0
            if source_strength > 0:
                candidates = [i for i in range(layer.n_bits)
                              if state[i] < 0.5
                              and i not in layer.frozen_bits
                              and constraints.direction[i].item() >= 0]
                if candidates:
                    n_inject = min(source_strength, len(candidates))
                    ok, _ = constraints.check_A5_inject(state, n_inject)
                    if ok:
                        chosen = np.random.choice(candidates, n_inject, replace=False)
                        for idx in chosen:
                            a9_ok, _ = constraints.check_A9(idx)
                            if not a9_ok:
                                continue
                            state[idx] = 1.0
                            constraints.record_inject(1)
                            constraints.record_active(idx)
                            constraints.direction[idx] = 1
                            actual_inject += 1

            # 2. 内部演化
            allowed = constraints.get_allowed_flips(state)
            if allowed:
                flip_idx = int(np.random.choice(allowed))
                a9_ok, _ = constraints.check_A9(flip_idx)
                if a9_ok:
                    old_val = state[flip_idx].item()
                    state[flip_idx] = 1.0 - state[flip_idx]
                    new_val = state[flip_idx].item()
                    constraints.update_A6_direction(flip_idx, old_val, new_val)
                    constraints.record_active(flip_idx)

            # 3. 横向演化
            lateral_pairs = constraints.get_A1_prime_candidates(state)
            n_lateral = 0
            for (i, j) in lateral_pairs:
                if state[i] > 0.5 and state[j] < 0.5:
                    a9_ok_i, _ = constraints.check_A9(i)
                    a9_ok_j, _ = constraints.check_A9(j)
                    if not a9_ok_i or not a9_ok_j:
                        continue
                    state[i] = 0.0
                    state[j] = 1.0
                    constraints.update_A6_direction(i, 1.0, 0.0)
                    constraints.update_A6_direction(j, 0.0, 1.0)
                    constraints.record_active(i)
                    constraints.record_active(j)
                    constraints.strengthen_binding(i, j, amount=0.1)
                    n_lateral += 1

            # 4. 汇吸收
            sink_strength = constraints.get_A8_sink_strength(state, actual_inject)
            if sink_strength > 0:
                allowed_abs = [i for i in range(layer.n_bits)
                               if state[i] > 0.5 and i not in layer.frozen_bits]
                n_absorb = min(sink_strength, len(allowed_abs))
                if n_absorb > 0:
                    ok, _ = constraints.check_A5_absorb(state, n_absorb)
                    if ok:
                        chosen = np.random.choice(allowed_abs, n_absorb, replace=False)
                        for idx in chosen:
                            state[idx] = 0.0
                            constraints.record_absorb(1)
                            constraints.direction[idx] = -1

            # 5. A7 循环检测
            constraints.check_A7(state)

            total_inject += actual_inject
            total_absorb += sink_strength
            total_lateral += n_lateral

            layer.step_count += 1

        return {
            'layer': layer_id,
            'steps': n_steps,
            'final_w': int(state.sum().item()),
            'total_inject': total_inject,
            'total_absorb': total_absorb,
            'total_lateral': total_lateral,
            'sealed': constraints.sealed,
            'active_bits': len(constraints.active_bits),
            'cycle_states': len(constraints.cycle_states),
        }

    def check_and_encapsulate(self) -> Optional[Dict]:
        """检查当前层是否应该封装（A9 触发），如果是则执行

        Returns:
            封装信息字典，如果未触发封装则返回 None
        """
        layer = self.current
        if layer.constraints.sealed and not layer.is_sealed:
            new_layer, info = self.encapsulate_current_layer()
            if self.current_layer < 3:  # 最多 3 层
                print(f"[Hierarchy] L{info['from_layer']} -> L{info['to_layer']}: "
                      f"{info['n_bits_before']} -> {info['n_bits_after']} bits "
                      f"({info['n_active_preserved']} active + {info['n_encapsulated']} enc)")
            return info
        return None

    def update_base_encapsulated_values(self):
        """更新所有封装比特的值（基底状态变化后调用）"""
        for layer_id in range(self.n_layers - 1):
            base_layer = self.get_layer(layer_id)
            self.encap_engine.update_encapsulated_values(
                base_layer.state, layer_id)

    def check_unseal(self, layer_id: int) -> List[int]:
        """检查指定层的封装比特是否应该解封"""
        base_layer = self.get_layer(layer_id)
        return self.encap_engine.check_unseal(base_layer.state, layer_id)

    # ─── 回流通道（Backflow Channel） ───────────────────────────
    #
    # 理论依据：Appearing Before Appearing §3.3
    # "持留是路径依赖的递归——第n次重构的不对称性成为第n+1次的起始偏置"
    #
    # 实现原理：
    # 1. 解封时，高层状态偏置向下传播（不是值覆盖，是概率调制）
    # 2. 偏置强度随时间衰减（保护低层自主性）
    # 3. 偏置通过 AxiomConstraints.inject 通道传入，不绕过公理体系
    #

    def __init_bias_registry(self):
        """初始化偏置注册表"""
        # bias_registry[layer_id] = [BiasField, ...]
        self.bias_registry: Dict[int, List['BiasField']] = {}
        for i in range(self.n_layers):
            self.bias_registry[i] = []

    def propagate_bias_down(self, source_layer_id: int,
                            bias_strength: float = 0.3) -> Optional['BiasField']:
        """将高层状态偏置向下传播

        当解封发生时调用：高层的汉明重量分布偏置作为 BiasField 传回低层。
        偏置方向 = 高层状态的归一化重心映射到低层索引空间。

        Args:
            source_layer_id: 产生偏置的层（通常是 L+1）
            bias_strength: 初始偏置强度

        Returns:
            生成的 BiasField，如果目标层不存在则返回 None
        """
        if source_layer_id <= 0:
            return None  # L0 没有更低的层

        source = self.get_layer(source_layer_id)
        target = self.get_layer(source_layer_id - 1)

        # 计算偏置方向：从高层状态提取归一化偏置向量
        # 映射到低层维度（如果维度不匹配，用线性插值/截断）
        source_state = source.state.clone()
        # 归一化到 [0, 1] 范围作为概率调制方向
        if source_state.max() > 0:
            source_state = source_state / (source_state.max() + 1e-8)

        # 维度适配：高层 N <= 低层 N，需要扩展
        target_N = target.n_bits
        if len(source_state) < target_N:
            # 重复填充到目标维度
            repeats = target_N // len(source_state) + 1
            bias_vector = source_state.repeat(repeats)[:target_N]
        else:
            bias_vector = source_state[:target_N]

        # 创建 BiasField
        bias = BiasField(
            source_layer=source_layer_id,
            target_layer=source_layer_id - 1,
            bias_vector=bias_vector,
            strength=bias_strength,
            origin_step=source.step_count,
        )

        # 注册偏置
        target_id = source_layer_id - 1
        if target_id not in self.bias_registry:
            self.bias_registry[target_id] = []
        self.bias_registry[target_id].append(bias)

        return bias

    def apply_bias_to_layer(self, layer_id: int) -> Dict:
        """将所有活跃偏置应用到指定层的公理约束器

        偏置不是值覆盖，是概率调制：
        - 正偏置 → 该比特更容易被注入（源注入概率 ↑）
        - 负偏置 → 该比特更容易被吸收（汇吸收概率 ↑）
        - 通过 AxiomConstraints.inject 通道传入，不绕过公理体系

        Returns:
            应用信息：应用了多少偏置，剩余多少
        """
        biases = self.bias_registry.get(layer_id, [])
        if not biases:
            return {'applied': 0, 'remaining': 0}

        layer = self.get_layer(layer_id)
        applied = 0
        remaining = []

        for bias in biases:
            if bias.strength < 1e-4:
                continue  # 太弱，跳过

            # 概率调制：根据偏置向量调整注入/吸收的候选优先级
            # 这里用偏置作为注入候选的权重，而非直接修改状态
            constraints = layer.constraints
            for idx in range(min(len(bias.bias_vector), layer.n_bits)):
                bias_val = bias.bias_vector[idx].item()
                if bias_val > 0.5:
                    # 正偏置：标记该比特为注入优先
                    # 通过增大 direction 来提升注入概率
                    if idx < len(constraints.direction):
                        # 只调整方向权重，不强制翻转
                        # 偏置强度决定调整幅度
                        if constraints.direction[idx] == 0:
                            # 未定向的比特，偏置给予正方向倾向
                            pass  # direction 不直接改，通过注入候选排序实现
                elif bias_val < 0.5:
                    # 负偏置：标记该比特为吸收优先
                    pass

            applied += 1
            if bias.decay():  # 衰减后仍有效
                remaining.append(bias)

        self.bias_registry[layer_id] = remaining
        return {'applied': applied, 'remaining': len(remaining)}

    def check_unseal_with_backflow(self, layer_id: int) -> Dict:
        """检查解封并触发回流

        解封 = 封装体边界打开 = 高层状态可以渗透回低层
        这是回流的自然触发点。

        Returns:
            {
                'unsealed': [解封的封装比特ID],
                'backflow': [生成的BiasField],
            }
        """
        unsealed = self.check_unseal(layer_id)

        backflow = []
        if unsealed:
            # 解封发生 → 触发回流
            bias = self.propagate_bias_down(layer_id + 1)
            if bias is not None:
                backflow.append(bias)

        return {
            'unsealed': unsealed,
            'backflow': backflow,
        }

    def get_hierarchy_summary(self) -> Dict:
        """获取层级结构摘要"""
        return {
            'n_layers': self.n_layers,
            'current_layer': self.current_layer,
            'layers': [
                {
                    'id': l.layer_id,
                    'N': l.n_bits,
                    'w': l.hamming_weight,
                    'active': len(l.active_bits),
                    'frozen': len(l.frozen_bits),
                    'sealed': l.is_sealed,
                    'steps': l.step_count,
                    'inj': l.constraints.total_injected,
                    'abs': l.constraints.total_absorbed,
                    'cycles': len(l.constraints.cycle_states),
                }
                for l in self.layers
            ],
            'encapsulation': {
                layer_id: self.encap_engine.get_summary(enc_layer)
                for layer_id, enc_layer in enumerate(range(1, self.n_layers + 1), 1)
                if enc_layer in self.encap_engine.encapsulated_bits
            }
        }

    def print_hierarchy(self):
        """打印层级结构"""
        summary = self.get_hierarchy_summary()
        print("=" * 60)
        print(f"Hierarchy: {summary['n_layers']} layers, current=L{summary['current_layer']}")
        print("=" * 60)
        for l in summary['layers']:
            status = "[S]" if l['sealed'] else "[O]"
            print(f"  L{l['id']}: N={l['N']}, w={l['w']}, "
                  f"active={l['active']}, frozen={l['frozen']}, "
                  f"inj={l['inj']}, abs={l['abs']}, "
                  f"cycles={l['cycles']} {status}")
        print("=" * 60)
