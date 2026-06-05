# A9 多隶属封口机制重设计

## 问题陈述

### 当前实现的根本限制

A9 封口（`_seal()`）在现有实现中是一个**二元操作**：每个比特要么被冻结（`sealed_bits`），要么保持活跃。冻结的比特通过 EncapsulationEngine 的 Union-Find 被划分为互不相交的组（组织），每组封装为一个高层级比特。

这导致两个理论缺陷：

1. **单隶属约束**：一个比特只能属于一个组织。理论上，差异的余差应当能同时参与多个组织的封口——正如一个人可以同时隶属于多个社会组织，一个实体可以同时承担多种功能。

2. **一次性封口**：封口是一个时刻事件（在某一步触发），而非渐进过程。理论上，封口应当是连续的：组织不断形成、比特逐步被锁定，未被组织的余差持续参与后续封口。

### 用户的理论指导

> "全部试验最大的难点其实是A9，理论上是无限组装可能性，一方面是不断递归、参与下一层组装、未被组织的余差要参与其他的A9封口，这是一个逻辑不那么清晰的环节，可以类比于一个人的社会身份可以同时隶属于多个组织，也可以类比于一个实体同时负责多个功能。"

---

## 多隶属模型

### 核心概念

**组织（Organization）**：一组绑定强度足够高的比特，共同构成一个功能单元。

**隶属度（Membership Weight）**：比特对某个组织的参与程度，取值 [0, 1]。

**锁定水平（Lock Level）**：比特的所有隶属度之和，代表已被组织"占用"的自由度比例。

**残余自由度（Residual Freedom）**：`1 - lock_level`，代表比特还可以参与新组织的"空余容量"。

**完全锁定**：当 `lock_level >= lock_threshold`（默认 0.95）时，比特不再参与任何新组织。

### 形式化定义

对每个比特 $i$，定义：

- $M(i) = \{(g_k, w_k)\}$：比特 $i$ 的组织隶属集合，$g_k$ 为组织 ID，$w_k \in (0,1]$ 为隶属度
- $L(i) = \sum_{(g,w) \in M(i)} w$：锁定水平
- $R(i) = 1 - L(i)$：残余自由度

约束不变式：

$$\forall i: \quad L(i) \leq 1.0$$

一个比特的残余自由度 $R(i)$ 决定了它参与新组织的"权重上限"——新隶属度 $w_{new} \leq R(i)$。

### 组织形成

组织通过**绑定强度聚类**自然形成。与当前 Union-Find 的区别是：Union-Find 产生硬划分（每个节点恰好属于一个连通分量），而多隶属模型使用**重叠聚类**——一个比特可以同时属于多个高绑定强度簇。

具体算法：**贪心团扩展**（Greedy Clique Expansion）

1. 计算所有活跃比特对的绑定强度
2. 对于绑定强度超过阈值的比特对 $(i, j)$，尝试合并到现有组织或创建新组织
3. 比特加入组织的条件：与该组织现有成员的平均绑定强度 > 加入阈值
4. 隶属度 = 该比特与组织成员的平均绑定强度（归一化到 [0, 1]）
5. 比特可加入多个组织，直到 $L(i) \geq lock\_threshold$

### 渐进封口

与当前"一次性 _seal()"不同，多隶属封口是**持续的**：

- 每隔 `org_formation_interval` 步（默认 50），执行一次组织形成扫描
- 新的组织自然涌现，已有组织可以吸收新成员或分裂
- 比特的锁定水平随组织参与逐渐增加
- 当系统中完全锁定比特数 >= `sealing_activation_threshold` 时，触发封装

---

## 数据结构变更

### AxiomConstraints 中的新字段

```python
# ═══ 多隶属封口（替代 sealed_bits: Set[int]）═══

# 组织注册表：org_id -> 成员比特集合
self.organizations: Dict[int, Set[int]] = {}

# 比特隶属关系：bit_idx -> [(org_id, weight), ...]
self.bit_memberships: Dict[int, List[Tuple[int, float]]] = {}

# 组织内部绑定强度得分：org_id -> 平均绑定强度
self._org_binding_scores: Dict[int, float] = {}

# 下一个可用的组织 ID
self._next_org_id: int = 0

# 组织形成参数
self.org_formation_interval: int = 50       # 每隔多少步扫描一次
self.org_join_threshold: float = 0.15       # 加入组织的绑定强度阈值
self.lock_threshold: float = 0.95           # 完全锁定的锁定水平阈值
self.max_orgs_per_bit: int = 4              # 单个比特最多隶属的组织数

# 兼容旧接口
self.sealed_bits: Set[int] = set()          # 计算属性：完全锁定的比特
self.sealed: bool = False                   # 当完全锁定比特数 >= threshold 时为 True
```

### 向后兼容

`sealed_bits` 保留为 `Set[int]` 类型，但改为**计算属性**（property），从 `bit_memberships` 派生：

```python
@property
def sealed_bits(self) -> Set[int]:
    """完全锁定的比特集合（向后兼容）"""
    return {
        bit_idx for bit_idx, memberships in self.bit_memberships.items()
        if self._compute_lock_level(memberships) >= self.lock_threshold
    }

@sealed_bits.setter
def sealed_bits(self, value: Set[int]):
    """向后兼容：测试代码直接赋值 sealed_bits"""
    # 将直接赋值转换为等价的隶属关系
    self.bit_memberships.clear()
    for bit_idx in value:
        org_id = self._get_or_create_singleton_org(bit_idx)
        self.bit_memberships[bit_idx] = [(org_id, 1.0)]
```

类似地，`sealed` 标志变为计算属性：

```python
@property
def sealed(self) -> bool:
    return len(self.sealed_bits) >= self.min_active_bits
```

---

## 算法变更

### `_compute_lock_level()` — 锁定水平计算

```python
def _compute_lock_level(self, memberships: List[Tuple[int, float]]) -> float:
    """计算比特的锁定水平（所有隶属度之和，上限 1.0）"""
    return min(1.0, sum(w for _, w in memberships))
```

### `_form_organizations()` — 组织形成（核心算法）

```python
def _form_organizations(self, current_step: int):
    """扫描活跃比特，形成/更新组织
    
    渐进封口：每 org_formation_interval 步执行一次。
    使用贪心团扩展算法，允许比特多隶属。
    """
    # 1. 获取当前活跃且未完全锁定的比特
    active_free = [
        i for i in range(self.N)
        if self._compute_lock_level(
            self.bit_memberships.get(i, [])
        ) < self.lock_threshold
    ]
    
    if len(active_free) < 2:
        return
    
    # 2. 计算绑定强度超过阈值的比特对
    edges = []
    for i_idx, i in enumerate(active_free):
        for j_idx, j in enumerate(active_free):
            if i < j:
                b = self.binding_strength[i][j].item()
                if b > self.org_join_threshold:
                    edges.append((i, j, b))
    
    if not edges:
        return
    
    # 3. 贪心团扩展
    # 按绑定强度降序排列
    edges.sort(key=lambda e: e[2], reverse=True)
    
    # 初始化：每条边的两个比特形成一个候选组织
    candidate_groups: List[Set[int]] = []
    bit_to_candidates: Dict[int, List[int]] = {}  # bit -> candidate group indices
    
    for i, j, b in edges:
        # 检查 i 和 j 是否已经在同一个候选组织中
        found = False
        for g_idx, group in enumerate(candidate_groups):
            if i in group and j in group:
                found = True
                break
        
        if not found:
            # 检查是否可以扩展某个现有候选组织
            extended = False
            for g_idx, group in enumerate(candidate_groups):
                if i in group or j in group:
                    new_bit = j if i in group else i
                    # 检查新比特与组内所有成员的平均绑定强度
                    avg_b = sum(
                        self.binding_strength[new_bit][m].item()
                        for m in group if m != new_bit
                    ) / max(len(group), 1)
                    if avg_b > self.org_join_threshold:
                        group.add(new_bit)
                        if new_bit not in bit_to_candidates:
                            bit_to_candidates[new_bit] = []
                        bit_to_candidates[new_bit].append(g_idx)
                        extended = True
                        break
            
            if not extended:
                # 创建新的候选组织
                g_idx = len(candidate_groups)
                candidate_groups.append({i, j})
                if i not in bit_to_candidates:
                    bit_to_candidates[i] = []
                if j not in bit_to_candidates:
                    bit_to_candidates[j] = []
                bit_to_candidates[i].append(g_idx)
                bit_to_candidates[j].append(g_idx)
    
    # 4. 将候选组织注册为正式组织
    for group in candidate_groups:
        if len(group) < 2:
            continue
        
        # 计算组内平均绑定强度
        members = sorted(group)
        bindings = [
            self.binding_strength[i][j].item()
            for i in members for j in members if i < j
        ]
        avg_binding = sum(bindings) / max(len(bindings), 1)
        
        org_id = self._next_org_id
        self._next_org_id += 1
        self.organizations[org_id] = group
        self._org_binding_scores[org_id] = avg_binding
        
        # 为每个成员分配隶属度
        for bit_idx in group:
            current_memberships = self.bit_memberships.get(bit_idx, [])
            current_lock = self._compute_lock_level(current_memberships)
            remaining = 1.0 - current_lock
            
            if remaining <= 0.01:
                continue  # 已完全锁定
            
            if len(current_memberships) >= self.max_orgs_per_bit:
                continue  # 隶属组织数已达上限
            
            # 隶属度 = 该比特与组内其他成员的平均绑定强度 * 残余自由度
            bit_bindings = [
                self.binding_strength[bit_idx][m].item()
                for m in group if m != bit_idx
            ]
            bit_avg = sum(bit_bindings) / max(len(bit_bindings), 1)
            weight = min(bit_avg, remaining)
            
            current_memberships.append((org_id, weight))
            self.bit_memberships[bit_idx] = current_memberships
```

### `check_A9()` — 修改后的封口检查

```python
def check_A9(self, flip_idx: int, partial_sealing: bool = False) -> Tuple[bool, str]:
    """A9：多隶属封口
    
    与旧版的区别：
    - 不再是一次性 _seal()，而是渐进的 _form_organizations()
    - 封口检查基于锁定水平而非二元 sealed_bits
    """
    current_step = self._step_counter()
    self.total_unique_active.add(flip_idx)
    self.active_bits[flip_idx] = current_step
    
    # 定期执行组织形成
    if current_step % self.org_formation_interval == 0 and current_step > 0:
        self._form_organizations(current_step)
    
    # 检查比特是否完全锁定
    lock_level = self._compute_lock_level(
        self.bit_memberships.get(flip_idx, [])
    )
    if lock_level >= self.lock_threshold:
        return False, f"A9: bit {flip_idx} fully locked (L={lock_level:.2f})"
    
    # 更新 sealed 标志
    n_locked = len(self.sealed_bits)
    if n_locked >= self.sealing_activation_threshold:
        self._sealed = True
    
    return True, "ok"
```

### `get_allowed_flips()` — 修改后的允许翻转

```python
def get_allowed_flips(self, state: torch.Tensor) -> List[int]:
    """获取所有被公理允许的翻转位置"""
    allowed = []
    for i in range(self.N):
        if state[i] > 0.5:
            continue
        d = self.direction[i].item()
        if d < 0:
            continue
        # A9：检查锁定水平（而非二元 sealed_bits）
        lock_level = self._compute_lock_level(
            self.bit_memberships.get(i, [])
        )
        if lock_level >= self.lock_threshold:
            continue
        allowed.append(i)
    return allowed
```

---

## 下游影响分析

### 1. EncapsulationEngine（封装引擎）

**当前**：接收 `frozen_bits: Set[int]`，使用 Union-Find 在冻结比特间分组。

**变更**：需要接收 `organizations: Dict[int, Set[int]]` 和 `bit_memberships`，替代 frozen_bits + Union-Find 分组。封装直接基于已形成的组织，而非重新分组。

对于多隶属比特（属于多个组织），封装时需要决定：
- **方案 A**：比特参与所有所属组织的封装（在多个高层级比特中都有贡献）
- **方案 B**：比特只参与锁定水平最高的组织的封装

建议采用**方案 A**，因为它更忠实于多隶属的理论意图。

### 2. HierarchyManager（层级管理器）

**当前**：`encapsulate_current_layer()` 使用 `constraints.sealed_bits` 获取冻结比特。

**变更**：改为使用 `constraints.organizations` 和 `constraints.bit_memberships`。向后兼容路径：`sealed_bits` property 仍然可用。

### 3. HierarchicalEvolver（跨层级演化器）

**当前**：
- `_compute_cross_layer_gravity()` 使用 `frozen_indices = list(layer.constraints.sealed_bits)`
- `_make_phase2_callback()` 中的 `active_bits` 和 `frozen_bits` 统计

**变更**：
- 引力计算需要考虑部分锁定比特的锁定水平作为质量权重
- 活跃/冻结统计改为连续值（锁定水平）而非二元分类

### 4. A8 源/汇强度

**当前**：`get_A8_source_strength()` 和 `get_A8_sink_strength()` 基于 `sealed_bits` 区分冻结/未冻结比特。

**变更**：改为基于锁定水平的加权计算。部分锁定的比特对源/汇的贡献按 `1 - lock_level` 缩放。

### 5. 测试代码

**影响范围**：16 处直接赋值 `sealed_bits = {...}` 的测试需要适配 setter。

**策略**：通过 `sealed_bits.setter` 实现向后兼容，测试代码无需修改即可工作。

---

## 实施阶段

### Phase 1：基础数据结构（本次实施）

- [x] 设计文档
- [ ] `AxiomConstraints` 新增多隶属字段
- [ ] `sealed_bits` 和 `sealed` 改为计算属性（含 setter 向后兼容）
- [ ] 实现 `_form_organizations()` 贪心团扩展算法
- [ ] 修改 `check_A9()` 和 `get_allowed_flips()` 使用锁定水平
- [ ] 单元测试覆盖多隶属场景

### Phase 2：封装引擎适配（后续）

- [ ] `EncapsulationEngine.encapsulate()` 接受 organizations 作为输入
- [ ] 多隶属比特的跨组封装
- [ ] `HierarchyManager.encapsulate_current_layer()` 适配

### Phase 3：下游组件适配（后续）

- [ ] A8 源/汇强度计算适配
- [ ] 引力调制适配（部分锁定比特的质量权重）
- [ ] Phase 2 回调中的统计适配
- [ ] 全量实验回归测试

### Phase 4：验证实验（后续）

- [ ] 多隶属封口下的 L1 形成质量
- [ ] 多隶属比特比例统计
- [ ] 与单隶属基线的 CIV/NSI 对比
- [ ] 封口渐进性对系统稳定性的影响

---

## 理论意义

多隶属封口机制是差异论模拟机中**最核心的理论挑战**。它对应的是：

1. **余差的递归参与**：未被当前组织吸纳的差异（余差）不是被丢弃，而是持续参与后续的组织形成。这正是"差异不会消失，只会重组"的工程体现。

2. **身份的叠加性**：一个实体可以同时拥有多个社会身份，每个身份对应一个组织隶属。锁定水平代表"社会角色饱和度"——当一个人承担了足够多的角色，就无法再承担新的角色。

3. **从封口到封装的连续过渡**：封口不再是一个时刻事件，而是一个持续的过程。组织不断形成和巩固，封装在组织足够成熟时自然发生。

4. **无限组装可能性的有限近似**：理论上 A9 允许无限递归组装（组织可以嵌套、交叉、重叠），工程上通过 `max_orgs_per_bit` 和 `lock_threshold` 控制复杂度。
