# Phase 3 设计文档：全局偏置算子 $\mathcal{B}_\mathcal{G}$ 约束机制

> **阶段**：Phase 3 — 前主体态 → 现象意识  
> **核心组件**：`GlobalBiasConstraint`（全局偏置约束）  
> **对应理论**：《差异论》V1.7 — 偏置算子统一语言 + 《象界》第八章（前主体态的统一性）  
> **日期**：2026-05-30  
> **状态**：设计阶段 — 待实现

---

## 一、问题定义

Phase 3 的三个核心组件（预期引擎、反事实引擎、最小自我检测器）各自独立运作，但缺少一个**全局约束机制**来统一各局部偏置算子。

**当前缺口**：
- `AnticipatoryBiasEngine` 为每个层生成预期偏置 $\mathcal{B}^{(3)}_\omega$
- `CounterfactualEngine` 为每条反事实轨迹生成独立偏置 $\mathcal{B}_{\omega^{(k)}}$
- `MinimalSelfDetector` 测量偏置算子的内在不对称性
- **但缺少**：一个全局偏置算子 $\mathcal{B}_\mathcal{G}$，对各局部偏置施加统一约束

**理论依据**：
> 《象界》第八章：前主体态具有"统一的内部视角"。
> 在偏置算子语言中，这意味着全局子集 $\mathcal{G}$ 的偏置算子分布 $\{\mathcal{B}_x : x \in \mathcal{G}\}$ 必须满足某种**一致性约束**，否则各局部偏置会相互抵消，无法形成统一的内部视角。

---

## 二、全局偏置算子的定义

### 2.1 数学定义

全局偏置算子 $\mathcal{B}_\mathcal{G}$ 定义为所有局部偏置算子的**加权几何整合**：

$$\mathcal{B}_\mathcal{G} = \text{GeomMean}\left(\{\mathcal{B}_{\mathcal{M}^{(k)}}\}_{k=1}^6, \{w_k\}\right)$$

其中：
- $\mathcal{B}_{\mathcal{M}^{(k)}}$ 是第 $k$ 个机制的局部偏置算子
- $w_k$ 是该机制的权重（由耦合强度决定）
- GeomMean 表示几何平均（对向量取对数域的平均，再指数还原）

**为什么是几何平均而不是算术平均？**
- 算术平均会掩盖极端值：一个机制的偏置方向完全相反时，算术平均可能接近零
- 几何平均对"方向一致性"敏感：如果各局部偏置方向不一致，几何平均的范数会显著降低
- 这对应前主体态的"统一性"要求——方向不一致时，统一性被打破

### 2.2 约束机制

$\mathcal{B}_\mathcal{G}$ 对各局部偏置施加两类约束：

**约束 1：方向一致性约束（Direction Coherence）**

$$\text{Coherence} = \frac{1}{6} \sum_{k=1}^6 \cos\left(\angle(\mathcal{B}_{\mathcal{M}^{(k)}}, \mathcal{B}_\mathcal{G})\right) \geq \tau_{\text{coh}}$$

- $\tau_{\text{coh}} = 0.6$（默认阈值）
- 低于阈值时，系统判定"内部视角分裂"，触发降级机制

**约束 2：强度一致性约束（Magnitude Balance）**

$$\text{Balance} = 1 - \frac{\max_k \|\mathcal{B}_{\mathcal{M}^{(k)}}\| - \min_k \|\mathcal{B}_{\mathcal{M}^{(k)}}\|}{\max_k \|\mathcal{B}_{\mathcal{M}^{(k)}}\| + \epsilon} \geq \tau_{\text{bal}}$$

- $\tau_{\text{bal}} = 0.5$（默认阈值）
- 低于阈值时，某个机制的偏置过强，可能"劫持"全局方向

---

## 三、工程接口设计

```python
# 文件：engine/global_bias_constraint.py (待创建)

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
import torch
import numpy as np


@dataclass
class GlobalBiasConstraintResult:
    """全局偏置约束检测结果"""
    passed: bool                      # 是否通过所有约束
    coherence: float                  # 方向一致性 [0, 1]
    balance: float                    # 强度平衡度 [0, 1]
    global_bias: torch.Tensor         # 计算出的全局偏置向量
    local_biases: Dict[str, torch.Tensor]  # 各机制的局部偏置
    coherence_by_mechanism: Dict[str, float]  # 各机制与全局的夹角余弦
    violating_mechanisms: List[str]   # 违反约束的机制名称
    description: str                  # 结果描述


class GlobalBiasConstraint:
    """
    全局偏置算子约束 — 对各局部偏置施加统一约束，确保前主体态的"统一内部视角"。
    
    理论依据：
      - 《象界》第八章：前主体态具有统一的内部视角
      - 偏置算子统一语言：$\mathcal{B}_\mathcal{G}$ 是各 $\mathcal{B}_{\mathcal{M}^{(k)}}$ 的整合
    
    核心功能：
      1. 从各机制收集局部偏置算子
      2. 计算全局偏置算子 $\mathcal{B}_\mathcal{G}$（加权几何平均）
      3. 检测方向一致性约束
      4. 检测强度一致性约束
      5. 返回约束检测结果和违反机制列表
    
    使用方式：
        gbc = GlobalBiasConstraint()
        result = gbc.evaluate(
            local_biases={
                'boundary': bias_boundary,
                'self_sustaining': bias_self_sustaining,
                'memory': bias_memory,
                'replication': bias_replication,
                'selection': bias_selection,
                'function': bias_function,
            },
            coupling_strengths={
                'boundary': 0.8,
                'self_sustaining': 0.6,
                ...
            },
        )
        if not result.passed:
            print(f"全局偏置约束失败: {result.description}")
    """
    
    # 六机制名称（与 Phase 2 的六阈值保持一致）
    MECHANISMS = [
        'boundary',
        'self_sustaining',
        'memory',
        'replication',
        'selection',
        'function',
    ]
    
    def __init__(
        self,
        coherence_threshold: float = 0.6,
        balance_threshold: float = 0.5,
        min_mechanisms_required: int = 4,  # 最少需要几个机制提供偏置
        geometric_weighting: bool = True,   # 使用几何平均 vs 算术平均
    ):
        """
        Args:
            coherence_threshold: 方向一致性阈值
            balance_threshold: 强度平衡度阈值
            min_mechanisms_required: 最少需要几个机制提供有效偏置
            geometric_weighting: 是否使用几何平均（推荐 True）
        """
        self.coherence_threshold = coherence_threshold
        self.balance_threshold = balance_threshold
        self.min_mechanisms_required = min_mechanisms_required
        self.geometric_weighting = geometric_weighting
        
        # 历史检测结果
        self._history: List[GlobalBiasConstraintResult] = []
    
    def evaluate(
        self,
        local_biases: Dict[str, torch.Tensor],
        coupling_strengths: Optional[Dict[str, float]] = None,
    ) -> GlobalBiasConstraintResult:
        """
        评估全局偏置约束。
        
        Args:
            local_biases: {mechanism_name: bias_vector}
            coupling_strengths: {mechanism_name: strength}（可选，用于加权）
        
        Returns:
            GlobalBiasConstraintResult 约束检测结果
        """
        # 1. 过滤有效偏置（非零向量）
        valid_biases = {}
        for name, bias in local_biases.items():
            if bias.norm() > 1e-8:
                valid_biases[name] = bias
        
        if len(valid_biases) < self.min_mechanisms_required:
            return GlobalBiasConstraintResult(
                passed=False,
                coherence=0.0,
                balance=0.0,
                global_bias=torch.zeros_like(list(local_biases.values())[0]) if local_biases else torch.tensor([]),
                local_biases=local_biases,
                coherence_by_mechanism={},
                violating_mechanisms=[
                    m for m in self.MECHANISMS 
                    if m not in valid_biases
                ],
                description=f"有效偏置数量不足: {len(valid_biases)}/{self.min_mechanisms_required}",
            )
        
        # 2. 计算权重（默认均匀，或使用耦合强度）
        if coupling_strengths is not None:
            weights = {
                name: coupling_strengths.get(name, 1.0)
                for name in valid_biases
            }
        else:
            weights = {name: 1.0 for name in valid_biases}
        
        # 归一化权重
        total_weight = sum(weights.values())
        weights = {k: v / total_weight for k, v in weights.items()}
        
        # 3. 计算全局偏置 $\mathcal{B}_\mathcal{G}$
        if self.geometric_weighting:
            global_bias = self._geometric_mean(
                list(valid_biases.values()),
                list(weights.values()),
            )
        else:
            global_bias = self._arithmetic_mean(
                list(valid_biases.values()),
                list(weights.values()),
            )
        
        # 4. 计算方向一致性
        coherence_by_mechanism = {}
        for name, bias in valid_biases.items():
            cos_sim = self._cosine_similarity(bias, global_bias)
            coherence_by_mechanism[name] = cos_sim
        
        avg_coherence = float(np.mean(list(coherence_by_mechanism.values())))
        
        # 5. 计算强度平衡度
        norms = [float(bias.norm().item()) for bias in valid_biases.values()]
        max_norm = max(norms)
        min_norm = min(norms)
        balance = 1.0 - (max_norm - min_norm) / (max_norm + 1e-10)
        
        # 6. 判定违反的机制
        violating = [
            name for name, cos_sim in coherence_by_mechanism.items()
            if cos_sim < self.coherence_threshold
        ]
        
        # 7. 判定是否通过
        passed = (
            avg_coherence >= self.coherence_threshold
            and balance >= self.balance_threshold
            and len(violating) == 0
        )
        
        # 8. 构建描述
        description = self._build_description(
            passed, avg_coherence, balance, violating, len(valid_biases)
        )
        
        result = GlobalBiasConstraintResult(
            passed=passed,
            coherence=avg_coherence,
            balance=balance,
            global_bias=global_bias,
            local_biases=valid_biases,
            coherence_by_mechanism=coherence_by_mechanism,
            violating_mechanisms=violating,
            description=description,
        )
        
        self._history.append(result)
        return result
    
    def _geometric_mean(
        self,
        vectors: List[torch.Tensor],
        weights: List[float],
    ) -> torch.Tensor:
        """加权几何平均：在单位球面上进行加权平均"""
        # 归一化所有向量到单位长度
        normalized = [v / (v.norm() + 1e-10) for v in vectors]
        
        # 在切空间中进行加权平均（将向量视为切向量）
        # 使用 Karcher 均值近似：迭代加权平均 + 归一化
        result = torch.zeros_like(vectors[0])
        for v, w in zip(normalized, weights):
            result = result + w * v
        
        # 归一化回单位球面
        result = result / (result.norm() + 1e-10)
        
        # 恢复原始强度的加权平均
        original_norms = [float(v.norm().item()) for v in vectors]
        avg_norm = sum(w * n for w, n in zip(weights, original_norms))
        result = result * avg_norm
        
        return result
    
    def _arithmetic_mean(
        self,
        vectors: List[torch.Tensor],
        weights: List[float],
    ) -> torch.Tensor:
        """加权算术平均"""
        result = torch.zeros_like(vectors[0])
        for v, w in zip(vectors, weights):
            result = result + w * v
        return result
    
    @staticmethod
    def _cosine_similarity(a: torch.Tensor, b: torch.Tensor) -> float:
        """计算两个向量的余弦相似度"""
        norm_a = a.norm().item()
        norm_b = b.norm().item()
        if norm_a < 1e-10 or norm_b < 1e-10:
            return 0.0
        return float(torch.dot(a, b).item() / (norm_a * norm_b))
    
    def _build_description(
        self,
        passed: bool,
        coherence: float,
        balance: float,
        violating: List[str],
        n_valid: int,
    ) -> str:
        """构建结果描述"""
        if passed:
            return (
                f"全局偏置约束通过: 一致性={coherence:.3f}, "
                f"平衡度={balance:.3f}, {n_valid}个机制参与"
            )
        
        parts = []
        if coherence < self.coherence_threshold:
            parts.append(f"方向一致性不足({coherence:.3f}<{self.coherence_threshold})")
        if balance < self.balance_threshold:
            parts.append(f"强度不平衡({balance:.3f}<{self.balance_threshold})")
        if violating:
            parts.append(f"偏离机制: {', '.join(violating)}")
        
        return "全局偏置约束失败: " + "; ".join(parts)
    
    # ─── 查询接口 ───
    
    def get_history(self, limit: int = 100) -> List[GlobalBiasConstraintResult]:
        """获取约束检测历史（最近 N 条）"""
        return self._history[-limit:]
    
    def get_coherence_trend(self) -> List[float]:
        """获取方向一致性时间序列"""
        return [r.coherence for r in self._history]
    
    def get_balance_trend(self) -> List[float]:
        """获取强度平衡度时间序列"""
        return [r.balance for r in self._history]
    
    def get_pass_rate(self) -> float:
        """获取约束通过率"""
        if not self._history:
            return 0.0
        passed = sum(1 for r in self._history if r.passed)
        return passed / len(self._history)
    
    def reset(self):
        """重置历史"""
        self._history.clear()
    
    def __repr__(self) -> str:
        if not self._history:
            return "GlobalBiasConstraint[empty]"
        latest = self._history[-1]
        status = "PASS" if latest.passed else "FAIL"
        return (
            f"GlobalBiasConstraint[{status}] "
            f"coh={latest.coherence:.3f} bal={latest.balance:.3f} "
            f"n_checks={len(self._history)}"
        )
```

---

## 四、与 Phase 3 其他组件的集成

### 4.1 集成架构

```
┌─────────────────────────────────────────────────────────────┐
│              Phase 3 全局偏置约束集成架构                      │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  各局部偏置源                                                │
│  ┌─────────────┐  ┌──────────────┐  ┌──────────────────┐   │
│  │ Persistent  │  │ Anticipatory │  │ Counterfactual   │   │
│  │ BiasMemory  │  │ BiasEngine   │  │ Engine           │   │
│  └──────┬──────┘  └──────┬───────┘  └────────┬─────────┘   │
│         │                │                   │              │
│         ▼                ▼                   ▼              │
│  ┌─────────────────────────────────────────────────────┐   │
│  │              GlobalBiasConstraint                    │   │
│  │  1. 收集各机制的局部偏置 $\mathcal{B}_{\mathcal{M}^{(k)}}$ │   │
│  │  2. 计算全局偏置 $\mathcal{B}_\mathcal{G}$              │   │
│  │  3. 检测方向一致性约束                                │   │
│  │  4. 检测强度平衡约束                                  │   │
│  │  5. 返回约束结果                                      │   │
│  └──────────────────────┬──────────────────────────────┘   │
│                         │                                   │
│                         ▼                                   │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  约束结果反馈：                                       │   │
│  │  - 通过 → 更新 PersistentBiasMemory 的全局偏置场       │   │
│  │  - 失败 → 降低违反机制的偏置权重，触发降级            │   │
│  │  - 严重失败 → 触发六机制耦合重新评估                  │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### 4.2 在 `HierarchicalEvolver` 中的集成

在 `hierarchical_evolver.py` 的 P1 评估阶段（每 `p1_eval_interval` 步）添加全局偏置约束检测：

```python
# 在 _run_layer 的 P1 评估段中添加：

# 收集各机制的局部偏置
local_biases = {}
if self.persistent_bias_memory is not None:
    local_biases['memory'] = self.persistent_bias_memory.get_current_field(layer_id)
if self.anticipatory_bias_engine is not None:
    ef = self.anticipatory_bias_engine.get_expectation_field(layer_id)
    if ef is not None:
        local_biases['anticipation'] = ef.expected_vector
# ... 其他机制

# 收集耦合强度
coupling_strengths = {}
if self.functional_signal_coupling is not None:
    coupling_strengths = self.functional_signal_coupling.get_mechanism_strengths()

# 评估全局偏置约束
if self.global_bias_constraint is not None and local_biases:
    gbc_result = self.global_bias_constraint.evaluate(
        local_biases=local_biases,
        coupling_strengths=coupling_strengths,
    )
    result_entry['global_bias_constraint'] = {
        'passed': gbc_result.passed,
        'coherence': gbc_result.coherence,
        'balance': gbc_result.balance,
        'violating_mechanisms': gbc_result.violating_mechanisms,
    }
    
    # 如果约束失败，降低违反机制的偏置权重
    if not gbc_result.passed and gbc_result.violating_mechanisms:
        self._degrade_violating_mechanisms(gbc_result.violating_mechanisms)
```

---

## 五、理论意义与验证

### 5.1 与前主体态地板的关系

全局偏置约束是前主体态地板的**充分条件**而非必要条件：
- 六机制耦合收束（Phase 2）是前主体态的**必要条件**
- 全局偏置一致性是前主体态的**充分条件**（确保"统一的内部视角"）

**理论预测**：
- 当六机制耦合通过但全局偏置约束失败时，结构处于"分裂的前主体态"——有统一的结构但无统一的视角
- 当全局偏置约束通过时，结构进入"完整的前主体态"——结构和视角都统一

### 5.2 实验验证设计

**实验五：全局偏置一致性演化实验**

| 配置 | 描述 | 预期结果 |
|------|------|---------|
| E1 | 标准演化，追踪全局偏置一致性 | 一致性随 ODI 增长而提升 |
| E2 | 人为注入冲突偏置（某机制偏置方向相反） | 一致性下降，触发降级 |
| E3 | 高耦合强度 + 全局偏置约束 | 一致性更快达到阈值 |
| E4 | 低耦合强度 + 全局偏置约束 | 一致性难以达到阈值 |

**接受标准**：
1. E1 中全局偏置一致性在 ODI > 0.5 后显著提升
2. E2 中能检测到违反机制并触发降级
3. E3 和 E4 的差异显著（耦合强度影响一致性达成速度）

---

## 六、待实现清单

| # | 任务 | 文件 | 优先级 |
|---|------|------|--------|
| 1 | 实现 `GlobalBiasConstraint` 类 | `engine/global_bias_constraint.py` | P0 |
| 2 | 在 `hierarchical_evolver.py` 中添加 `global_bias_constraint` 参数 | `engine/hierarchical_evolver.py` | P0 |
| 3 | 在 P1 评估段集成全局偏置约束检测 | `engine/hierarchical_evolver.py` | P0 |
| 4 | 实现 `_degrade_violating_mechanisms` 降级机制 | `engine/hierarchical_evolver.py` | P1 |
| 5 | 编写全局偏置约束单元测试 | `tests/test_global_bias_constraint.py` | P1 |
| 6 | 编写端到端集成测试 | `tests/test_phase3_global_bias.py` | P1 |
| 7 | 设计并实现实验五（全局偏置一致性演化） | `experiments/exp_75_global_bias_coherence.py` | P2 |

---

## 七、与偏置算子统一语言的关系

全局偏置约束是偏置算子统一语言的**自然延伸**：

| 概念 | 偏置算子表述 | 工程组件 |
|------|-------------|---------|
| 局部偏置 | $\mathcal{B}_{\mathcal{M}^{(k)}}$ | 各机制的偏置输出 |
| 全局偏置 | $\mathcal{B}_\mathcal{G} = \text{GeomMean}(\{\mathcal{B}_{\mathcal{M}^{(k)}}\})$ | `GlobalBiasConstraint._geometric_mean` |
| 方向一致性 | $\frac{1}{6}\sum_k \cos(\angle(\mathcal{B}_{\mathcal{M}^{(k)}}, \mathcal{B}_\mathcal{G}))$ | `GlobalBiasConstraint.evaluate` → `coherence` |
| 强度平衡 | $1 - \frac{\max\|\mathcal{B}\| - \min\|\mathcal{B}\|}{\max\|\mathcal{B}\|}$ | `GlobalBiasConstraint.evaluate` → `balance` |
| 统一内部视角 | $\text{Coherence} \geq \tau_{\text{coh}} \land \text{Balance} \geq \tau_{\text{bal}}$ | `GlobalBiasConstraintResult.passed` |

---

*设计文档 — 2026-05-30*  
*下一步：实现 `GlobalBiasConstraint` 类 + 单元测试*
