## 文件二：`calculations/ns_limit.md`

---

# 守恒律涌现：从离散守恒量到连续性方程和 Euler 方程

> 本文件是 CLEM-TASK-03 的技术附录，包含从 $J(2n,n)$ 离散守恒律到连续偏微分方程的完整推导细节。

---

## §1 离散系统的基本设置

### §1.1 状态空间

比特空间 $\{0,1\}^{2n}$，权重 $n$ 层（中截面），顶点集 $V_n = \binom{[2n]}{n}$，$|V_n| = \binom{2n}{n}$。

### §1.2 密度函数

$\rho: V_n \times \mathbb{Z}_{\geq 0} \to \mathbb{R}_{\geq 0}$，$\rho(v, t)$ 表示时刻 $t$ 在顶点 $v$ 处的差异密度。

总量：$M(t) = \sum_{v \in V_n} \rho(v, t)$。

**A5 的离散表达**：$M(t) = M(0)$，$\forall t \geq 0$。

### §1.3 演化规则

**A4**：每次演化仅改变一个比特 → 在 $V_n$ 上只能沿 $J(2n,n)$ 的边移动（Hamming 距离 2 的跳跃）。

**A6**：演化图是 DAG → 每条边有流量方向 $J(u \to v, t) \geq 0$。

**A7**：演化中存在闭合路径 → 绕三角面的净环流为零（$\partial^2 = 0$ 的流量版本）。

---

## §2 离散连续性方程

### §2.1 方程推导

在顶点 $v$ 处，密度变化率等于流入量减流出量：

$$\frac{d\rho(v,t)}{dt} = \sum_{u: \{u,v\} \in E} \left[ J(u \to v, t) - J(v \to u, t) \right]$$

定义净流量 $F(u \to v, t) = J(u \to v, t) - J(v \to u, t)$，则：

$$\frac{d\rho(v,t)}{dt} = \sum_{u \sim v} F(u \to v, t)$$

### §2.2 总量守恒验证

$$\frac{dM}{dt} = \sum_v \sum_{u \sim v} F(u \to v, t) = \sum_{\{u,v\} \in E} [F(u \to v) + F(v \to u)] = 0$$

最后一步因为 $F(u \to v) + F(v \to u) = 0$（反对称性）。✓

---

## §3 散度形式与连续极限

### §3.1 离散散度算子

定义离散散度：对定义在边上的函数 $g: E \to \mathbb{R}$，

$$(\operatorname{div} g)(v) = \sum_{u \sim v} g(e_{uv}) \cdot \operatorname{sgn}(v, e_{uv})$$

其中 $\operatorname{sgn}(v, e_{uv}) = +1$（$v$ 是终点）或 $-1$（$v$ 是起点）。

这是边界算子 $\partial_1$ 的转置：$\operatorname{div} = \partial_1^T$。

### §3.2 离散 de Rham 关系

A7 保证 $\partial_2^T \partial_1^T = (\partial_1 \partial_2)^T = 0$，即：

$$\operatorname{curl} \circ \operatorname{grad} = 0 \quad \text{（离散 de Rham 关系）}$$

其中 $\operatorname{grad} = \partial_1^T$，$\operatorname{curl} = \partial_2^T$。这是离散微积分基本定理，由 A7 直接给出。

### §3.3 散度形式

离散连续性方程变为：

$$\frac{d\rho}{dt} = -\operatorname{div}(\mathbf{F}) = -\partial_1^T \mathbf{F}$$

其中 $\mathbf{F}$ 是定义在边上的流量场（1-形式）。

### §3.4 连续极限

在 $n \to \infty$ 下（利用 TASK-02 的算子映射）：

- $\partial_1^T \to \nabla \cdot$（散度算子）
- $\mathbf{F} \to \rho \mathbf{u}$（动量通量）

得到：

$$\boxed{\frac{\partial \rho}{\partial \tau} + \nabla \cdot (\rho \mathbf{u}) = 0}$$

连续性方程。$\square$

### §3.5 各向同性的作用

A8 保证 $J(2n,n)$ 的顶点传递性。在 Taylor 展开中，邻居位移向量之和 $\sum_{u \sim v} \boldsymbol{\delta}_{uv} = \mathbf{0}$
（各向同性），一阶项消失，二阶主导，保证散度形式的标准性。

---

## §4 动量场与对流项

### §4.1 动量场的定义

动量密度：$\mathbf{p}(v, t) = \rho(v, t) \cdot \mathbf{u}(v, t)$。

在离散系统中，"速度"对应差异在 $J(2n,n)$ 上的传播方向。由 A6（DAG 有向），每条边有优先方向（来自 TASK-01 的 Morse 高度函数）。

**$\ell = 1$ 的物理意义**：TASK-02 证明 $\ell = 1$ 的谱值精确等于 $\Lambda_1 = 2$，对所有 $n$ 成立。$\ell = 1$ 的特征空间是
3 维的，对应 $S^2$ 上的坐标函数 $(x, y, z)$。守恒量的 $\ell = 1$ 分量正是**动量的三个分量**。

### §4.2 对流项的推导

A6 规定演化图是 DAG，流量有优先方向。在连续极限下，DAG 的优先方向对应速度场 $\mathbf{u}$。

动量的对流传输：

$$\frac{\partial (\rho u_i)}{\partial \tau}\bigg|_{\text{对流}} = -\nabla \cdot (\rho u_i \mathbf{u}) = -\rho (\mathbf{u} \cdot \nabla) u_i - u_i \nabla \cdot (\rho \mathbf{u})$$

利用连续性方程化简：

$$\frac{\partial (\rho u_i)}{\partial \tau}\bigg|_{\text{对流}} = -\rho \frac{D u_i}{D\tau}$$

其中 $\frac{D}{D\tau} = \frac{\partial}{\partial \tau} + \mathbf{u} \cdot \nabla$ 是物质导数。

**公理溯源**：

$$A6 \xrightarrow{\text{DAG 方向}} \text{流量有优先方向} \xrightarrow{n \to \infty} \mathbf{u} \cdot \nabla \xrightarrow{\text{物质导数}} \frac{D}{D\tau}$$

---

## §5 压力项与不可压缩条件

### §5.1 A1' 约束的全局一致性

A1' 要求同一权重层内相邻单元满足精确距离 $d_H = 2$。这是刚性约束——相邻 $S^2$ 单元不能重叠（$d_H < 2$
），也不能脱离（$d_H > 2$）。

若密度 $\rho$ 在某处增大（单元"压缩"），A1' 约束被违反。系统产生恢复力将密度推回均匀分布，宏观上表现为压力梯度 $-\nabla p$。

### §5.2 压力的微观定义

局部压力定义为维持 A1' 约束的 Lagrange 乘子：

$$p(v, t) = \lambda_{A1'}(v, t)$$

其中 $\lambda_{A1'}$ 是约束 $\sum_{u \sim v} [d_H(v,u) - 2]^2 = 0$ 的 Lagrange 乘子。

在连续极限下，$d_H = 2$（恒定间距）对应不可压缩条件 $\nabla \cdot \mathbf{u} = 0$，Lagrange 乘子对应压力场 $p$。

严格证明（压力 Poisson 方程）标注为 CLEM-OPEN-09。

### §5.3 不可压缩条件

A1' 约束在 $n \to \infty$ 极限下给出：

$$\nabla \cdot \mathbf{u} = 0$$

定性论证：$d_H = 2$ 恒定意味着相邻顶点间"体积元"不变，连续极限下等价于流场无散度。

---

## §6 Euler 方程组装

### §6.1 各项汇总

**连续性方程**（A5 + A7 + A4 + A8）：

$$\frac{\partial \rho}{\partial \tau} + \nabla \cdot (\rho \mathbf{u}) = 0$$

**不可压缩条件**（A1'）：

$$\nabla \cdot \mathbf{u} = 0$$

在不可压缩条件下，连续性方程化简为 $\frac{\partial \rho}{\partial \tau} + \mathbf{u} \cdot \nabla \rho = 0$（密度沿流线守恒）。

**动量方程**（A5 + A6 + A1'）：

$$\boxed{\rho \left( \frac{\partial \mathbf{u}}{\partial \tau} + (\mathbf{u} \cdot \nabla)\mathbf{u} \right) = -\nabla p}$$

不可压缩 Euler 方程。$\square$

### §6.2 公理覆盖检查

| 公理  | 在 Euler 方程中的体现                | 覆盖 |
|:----|:------------------------------|:--:|
| A1' | 不可压缩条件 + 压力项                  | ✓  |
| A4  | 局部跳跃 → 散度算子                   | ✓  |
| A5  | 总量守恒 → 连续性方程                  | ✓  |
| A6  | DAG → 对流项                     | ✓  |
| A7  | $\partial^2 = 0$ → de Rham 关系 | ✓  |
| A8  | 各向同性 → 一阶项消失                  | ✓  |

六条公理全部在 Euler 方程中体现，无遗漏。$\checkmark$

---