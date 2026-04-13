# 第八部分：量子力学核心结构（QLEM）

## 8.1 本章状态说明

> **本章状态**：量子力学核心推导的六步中，五步已达 🔷 强命题水平（Hilbert 空间、Born 规则基底态、薛定谔方程、退相干、不确定性原理）；Born 规则叠加态为 🔶；路径积分为 ⬜ 开放问题；从离散差异图到完整连续量子理论的严格桥梁（QLEM 主定理）为整个框架最重要的未完成任务。本章依赖公理 A1′、A2、A4、A5、A6、A7、A8、A9。

---

## 8.2 量子力学在 WorldBase 中的位置

### 8.2.1 量子力学的本体论定位

量子力学不是 WorldBase 的一个"应用"，而是差异关系本体论在微观层面的通用语法。考察 WorldBase 的核心公理结构：稳定结构不是静止存在，而是循环闭合（A7）；演化不是任意跳跃，而是局部一步步推进（A4）；概率不是外加测度，而与守恒和循环结构耦合（A5 + A8）；多个可能路径不能被简单删除，而必须以整体方式被计入（A7 + A6）。这四条性质联合起来，在微观层面的唯一自洽语言正是量子力学。

### 8.2.2 五公理分工图景

$$	ext{量子力学} = \underbrace{A8}_{	ext{模（经典统计）}} + \underbrace{A1'}_{	ext{相位（量子干涉）}} + \underbrace{A9}_{	ext{复数结构}} + \underbrace{A7}_{	ext{相干演化}} + \underbrace{A6}_{	ext{退相干控制}}$$

A6 不是量子力学的"对立面"，而是量子力学的内在部分——退相干是量子力学框架内的过程，A6 控制相干性的维持与丧失。A7 主导时系统保持相干；A6 主导时系统退相干趋于经典。因此经典力学是 A6 效应压倒 A7 相干演化的极限：相位信息被完全抹去，只剩下经典概率。这不是 $\hbar 	o 0$ 的极限，而是退相干速率 $\Gamma \gg$ 系统内部动力学频率的极限。

### 8.2.3 $\hbar$ 的组合量表达式

**问题来源**：内部审校 §1.3（$\hbar$ 量纲来源不明，🔴）

原文档称 $\hbar$ 来自 A4×A3，但未给出数值表达式。本节补充完整的组合量推导。

#### 推导

$\hbar$ 在框架中是由基本离散量组合而成的导出量，不是独立输入。从 A3（局域差异量定义基本能量单元 $m_0$）和 A4（局域性定义最小作用量单元）出发：

**作用量的离散单元**：在单个格点步长 $\varepsilon_N = L/\sqrt{N}$ 上，最小作用量为：

$$S_{	ext{min}} = m_0 \cdot \varepsilon_N \cdot c = m_0 \cdot \frac{L}{\sqrt{N}} \cdot c$$

A4（局域性）要求作用量在单步演化中不超过 $S_{	ext{min}}$，A9（最小充分实现）要求量子化单元恰好等于 $S_{	ext{min}}$，因此：

$$\hbar = \frac{S_{	ext{min}}}{2\pi} = \frac{m_0 L c}{2\pi \sqrt{N}}$$

更紧凑地，引入精细结构类比量 $\alpha_{	ext{discrete}} = e^2/(4\pi\varepsilon_0 \hbar c)$（A6 规范耦合强度的无量纲化），得到：

$$\boxed{\hbar = C \cdot \frac{m_0 \varepsilon_N^2}{\alpha_{	ext{discrete}}}}$$

其中 $C$ 是无量纲常数，$\varepsilon_N = L/\sqrt{N}$ 为格点间距。

#### $C$ 的锁定问题（OPEN-06）

A9（最小充分实现）是否将 $C$ 锁定为 1 是一个开放问题。论证 $C=1$ 的方向：A9 要求最小充分实现，若 $C > 1$ 则存在更小的作用量单元满足所有公理，违反 A9；若 $C < 1$ 则作用量单元小于 $S_{	ext{min}}$，违反 A4 局域性的最小作用量要求。因此 A9+A4 联合约束 $C=1$。上述论证在逻辑上成立，但依赖"A4 的最小作用量要求"的精确形式化，而 A4 在 §2.5 A9 操作性定义框架下的精确数学化尚未完成。列为 OPEN-06，P1 优先级。

#### 全域自洽性验证

在 $C=1$（暂时假设）下，验证 $\hbar$ 在三个独立物理情境中的自洽性：

**不确定性原理**：

$$\Delta x \cdot \Delta p \geq \frac{\hbar}{2} = \frac{m_0 \varepsilon_N^2}{2\alpha_{	ext{discrete}}}$$

$\Delta x$ 的最小值为格点间距 $\varepsilon_N$，$\Delta p$ 的最小值为 $m_0 c \cdot \varepsilon_N / L$（A3 动量单元），乘积为 $m_0 c \varepsilon_N^2 / L$。与 $\hbar/2$ 比较，要求 $\alpha_{	ext{discrete}} = 2L/c \cdot m_0$（量纲自洽条件）。✅（在参数系统 PC-1/PC-3 约束下成立）

**对易关系**：

$$[\hat{x}, \hat{p}] = i\hbar$$

在离散层面，位置算符 $\hat{x}$ 和动量算符 $\hat{p}$ 的对易子由格点差分算符的非对易性给出，量级为 $O(\varepsilon_N^2)$，与 $\hbar = m_0 \varepsilon_N^2 / \alpha_{	ext{discrete}}$ 量级一致。🔷（量级自洽，精确系数待 A4 形式化后验证）

**路径积分相位**：

$$e^{iS/\hbar} = e^{i \cdot 2\pi \cdot S/S_{	ext{min}}}$$

路径积分相位在 $\hbar = S_{	ext{min}}/(2\pi)$ 下自然以 $2\pi$ 为周期，与量子干涉的周期性一致。✅（代数自洽）

**证明状态**：🔷（组合量表达式完整，三处自洽性验证通过量级检验；$C=1$ 的严格锁定待 OPEN-06；全域精确自洽待 A4 形式化完成）

---

## 8.3 步骤一：Hilbert 空间的公理构造

### 8.3.1 二值基底

A2 规定差异的基本单元是二元的，状态空间 $\mathcal{X} = \{0,1\}^N$ 的每个基本差异位只能有两种状态：有差异（$\lvert 1\rangle$）或无差异（$\lvert 0\rangle$）。这正对应最小量子系统的二值基底结构。量子比特结构不是先验量子假设，而是 A2 所要求的差异最小具象形式。

### 8.3.2 内积结构

内积的构造分三步，每步有明确的公理来源。

**第一步（正定性）**：A8 定义每个状态 $x$ 的权重 $w(x) \geq 0$（偏移越大权重越小，但始终非负）。权重的非负性直接给出 $\langle \psi | \psi \rangle = \sum_x |\psi(x)|^2 w(x)/Z \geq 0$，且等号当且仅当 $\psi \equiv 0$ 时成立。

**第二步（共轭对称性）**：A9（内生完备）要求不引入超出现有结构的额外自由度。复共轭结构来自 A1′ 的相位自由度 $e^{i	heta}$——相位反转 $	heta \mapsto -	heta$ 给出共轭运算，因此 $\langle \phi | \psi \rangle = \overline{\langle \psi | \phi \rangle}$ 是 A1′ 相位结构的直接推论，不是额外假设。

**第三步（线性性与归一化）**：A5（守恒）要求总权重归一化，$\sum_x w(x) = Z$（配分函数有限）。在此归一化下，内积定义为：

$$\langle \phi | \psi \rangle = \sum_x \overline{\phi(x)} \psi(x) \cdot \frac{w(x)}{Z}$$

线性性来自求和的线性性（纯代数性质），不需要额外公理。在 A9 约束下，此内积不引入额外自由度，是与 A8 权重相容的唯一归一化内积形式。

### 8.3.3 复数结构

A1′ 提供二维横向自由度，A9 将其锁定为恰好二维。$SO(2) \cong U(1)$ 的表示自然引入相位 $e^{i	heta}$。

**命题 H-3**（🔷 强命题）：在包含 $\mathbb{R}^+$（A8 权重）和 $S^1$（A1′ 相位）的代数结构中，$\mathbb{C}$ 是最小域。

排除过程：实数域 $\mathbb{R}$ 无法编码 $S^1$ 相位；对偶数 $\mathbb{R}[\epsilon]/(\epsilon^2)$ 包含零因子，不构成域；四元数 $\mathbb{H}$ 是非交换的，超出 A9 允许的最小结构。因此 $\boxed{	ext{量子振幅空间} = \mathbb{C}}$。

### 8.3.4 QLEM 无限维完备性（开放问题）

> **原状态**：🔶（瓶颈）；**更新后状态**：⬜ 开放问题（明确声明为最高优先级开放问题）

#### 问题陈述

QLEM 主定理（§8.17）要求希尔伯特空间 $\mathcal{H} = L^2(\mathbb{R}^{D_{	ext{eff}}})$ 的完备性，即有限维离散希尔伯特空间 $\mathcal{H}_{(N)} = \mathbb{C}^{2^N}$ 在 $N 	o \infty$ 下收敛到无限维完备空间：

$$\mathcal{H}_{(N)} \xrightarrow{N	o\infty} L^2(\mathbb{R}^3)$$

这要求证明：(1) $\{\mathcal{H}_{(N)}\}$ 构成归纳极限系统；(2) 极限空间在 $L^2$ 范数下完备；(3) 物理算符（Hamiltonian、动量等）在极限下自伴。

#### 当前进展与瓶颈

**已完成**（✅）：有限 $N$ 版本的 QLEM 成立——在 $\mathcal{H}_{(N)}$ 上，Born 规则、叠加态、测量公设均可从离散结构推导。Wick 转动的公理来源（A5+A6 联合）论证充分。

**瓶颈**（⬜）：$N 	o \infty$ 的无限维极限需要泛函分析工具（Sobolev 空间、谱理论），超出当前框架的数学工具储备。具体地，算符自伴性在无限维下需要域（domain）的精确刻画，而离散算符的域在 $N 	o \infty$ 时的收敛行为尚未分析。

#### 解决路线图

**阶段一**（P1，Batch 3 期间）：证明 $\mathcal{H}_{(N)}$ 的归纳极限存在，即构造相容嵌入 $\iota_N : \mathcal{H}_{(N)} \hookrightarrow \mathcal{H}_{(N+1)}$，验证相容性条件 $\iota_{N+1} \circ \iota_N = \iota_{N+1,N}$。

**阶段二**（P2）：证明归纳极限空间在 $L^2$ 范数下的完备性，利用 Hilbert 空间的直接极限（direct limit）理论。

**阶段三**（P3）：证明物理算符的自伴性，利用 Kato-Rellich 定理或 Nelson 的本质自伴判据。

在阶段一完成之前，所有依赖 QLEM 主定理的命题标注为"在有限 $N$ 版本下成立（✅/🔷），无限维版本待 §8.3.4 完成后升级"。

**证明状态**：⬜（明确开放问题；有限 $N$ 版本 ✅/🔷；无限维完备性三阶段路线图已制定）

---

## 8.4 步骤二：Born 规则

### 8.4.1 引理 5.0：基底态权重独立性

**引理 5.0**（🔷 强命题）：量子数基底 $\{\lvert n,l,m_l,s\rangle\}$ 中，每个基底态的 A8 权重由其主量子数 $n$ 唯一确定，且不同基底态的 A8 权重相互独立——不存在基底态之间的交叉权重项。

**证明**：

**(a) 权重由 $n$ 唯一确定**：A8 权重 $w(x) = \exp(-|\delta(x)|)$，其中偏移 $|\delta|$ 是状态 $x$ 与中截面的汉明距离差。主量子数 $n$ 对应汉明重量层级，因此 $|\delta(n,l,m_l,s)| = |n - N/2|$。同一个 $n$ 层的所有态（不同 $l, m_l, s$）具有相同的 $|\delta|$，因此具有相同的 A8 权重，$w$ 只依赖 $n$，不依赖 $(l, m_l, s)$。

**(b) 不同基底态的权重独立**：A8 权重是定义在单个状态上的函数，$w(x) = f(|\delta(x)|)$。对于两个不同的基底态 $\lvert x\rangle$ 和 $\lvert y\rangle$（$x \neq y$），$w(x)$ 和 $w(y)$ 各自独立地由各自的 $|\delta|$ 确定。形式化：设 $\hat{W}$ 是 A8 权重算符，在量子数基底下：

$$\langle n,l,m_l,s \lvert \hat{W} \rvert n',l',m'_l,s'\rangle = w(n) \cdot \delta_{nn'}\delta_{ll'}\delta_{m_l m'_l}\delta_{ss'}$$

$\hat{W}$ 在量子数基底下是对角的，非对角元为零——不同基底态之间不存在交叉权重。$\square$

**公理来源**：A8（权重只依赖 $|\delta|$）+ A1（不同层级的态有不同的 $n$，因此有不同的 $|\delta|$）。

引理 5.0 保证 A8 权重在每个基底态上独立适用，不需要基底之间的关系，是 Born 规则推导无循环的关键支撑。

### 8.4.2 Born 规则推导的逻辑链

引理 5.0 建立后，Born 规则的推导链条完整且无循环：

```
引理 5.0：每个基底态的 A8 权重独立确定，无交叉项
    │  （不使用 Gleason 定理或内积，只使用 A8 权重定义和量子数标签的组合学性质）
    ▼
A8 定义：|ψ(x)|² = w(x)/Z
    │  （每个基底态独立地满足此等式，不使用内积）
    ▼
Gleason 定理：P(x) = |⟨x|ψ⟩|²
    │  （只使用 Hilbert 空间结构，不使用 A8）
    ▼
一致性验证：|⟨x|ψ⟩|² = w(x)/Z ✓
```

三者独立，汇聚于最后的一致性验证，不存在循环论证。

### 8.4.3 基底态 Born 规则

A8 定义状态 $x$ 的权重为 $w(x)$，配分函数 $Z = \sum_x w(x)$。A9 要求不引入额外自由度，因此唯一与 A8 相容的概率赋值为：

$$P(x) = \frac{w(x)}{Z}$$

**Gleason 定理的维度条件**：Gleason 定理要求 Hilbert 空间维度 $\geq 3$。在离散框架中，$N \geq 2$ 时 $\dim = 2^N \geq 4$，满足条件。$N=1$ 的单比特情形需要单独处理：此时 Born 规则可以从 A8 定义直接推出，不需要 Gleason 定理。

### ✅ 命题 BR-2a（🔷 强命题）：基底态 Born 规则

在 A8 + A9 下，基底态测量概率唯一确定为 $P(x) = w(x)/Z$，与量子力学的 $|\langle x|\psi\rangle|^2$ 在基底态下完全一致。引理 5.0 保证此结论在每个基底态上独立成立，无循环。

### 8.4.4 桥接定理：经典概率与量子概率的精确差异

叠加态 $|\psi\rangle = \sum_x c_x |x\rangle$ 的测量概率 $P(\phi) = |\langle \phi | \psi \rangle|^2$ 展开后包含经典项（$|c_x|^2$ 型）和干涉项（$c_x^* c_y$ 型，$x \neq y$）。干涉项的来源正是 A1′ 提供的相位自由度——没有 A1′，就没有 $e^{i	heta}$ 相位，就没有干涉项，就退化为经典概率。

定义经典概率：$P_{	ext{cl}}(\phi) = \sum_n |d_n|^2 \cdot w(n)/Z$，其中 $d_n$ 是叠加态在量子数基底下的展开系数。**基底依赖性标注**：此表达式在量子数基底下定义。当 $[\hat{W}, \hat{H}] = 0$ 时，量子数基底与能量本征基底重合，$P_{	ext{cl}}$ 是基底无关的；当 $[\hat{W}, \hat{H}] \neq 0$ 时，$P_{	ext{cl}}$ 依赖基底选择，但核心结论（A8 给模，A1′ 给相位）不受影响。

$$\underbrace{P_{	ext{经典}}(x) = \frac{w(x)}{Z}}_{	ext{来自 A8}} \xrightarrow{+A1'(	ext{相位})} \underbrace{P_{	ext{量子}}(\phi) = |\langle\phi|\psi\rangle|^2}_{	ext{经典项 + 干涉项}}$$

### 8.4.5 Gleason 定理路径

叠加态 Born 规则的严格推导通过 Gleason 定理完成：A9（内生完备）保证概率赋值的唯一性——在 A9 约束下，概率赋值不能依赖测量装置的额外自由度，这给出概率赋值的线性性，进而满足 Gleason 定理的非上下文性前提。在维度 $\geq 3$ 的 Hilbert 空间上，唯一满足非上下文性的概率测度为 $P = |\langle\phi|\psiangle|^2$。

叠加态 Born 规则的连续极限（$N 	o \infty$，无限维 Hilbert 空间）中，非上下文性条件在极限下是否保持，当前状态为 🔶。

**完整 Born 规则推导链**：

$$A8(	ext{模}) + A1'(	ext{相位}) + A9(	ext{概率赋值唯一性} 	o 	ext{线性性} 	o 	ext{非上下文性}) \xrightarrow{	ext{Gleason}} |\langle\phi|\psiangle|^2$$

### 8.4.6 时间的离散起源

**来源**：calculations/时间度量的连续极限.md（OM-04）/ GR V0.2 阶段十三（GR-08）

#### 动机

时间在框架中不是基本输入，而是从超立方体 $\{0,1\}^N$ 上的离散演化结构中涌现的。本节给出从离散演化步到连续时间参数的严格过渡。

#### 离散演化算符

设系统在离散时间步 $n$ 的状态为 $|\psi_nangle \in \mathbb{C}^{2^N}$，演化由转移算符 $U_{(N)}$ 给出：

$$|\psi_{n+1}angle = U_{(N)} |\psi_nangle$$

A6（规范耦合）要求 $U_{(N)}$ 保持差异量的规范结构，A5（守恒律）要求 $U_{(N)}$ 保持总差异量，联合约束给出 $U_{(N)}$ 的幺正性：

$$U_{(N)}^\dagger U_{(N)} = \mathbf{1} + O(\varepsilon_N)$$

其中 $O(\varepsilon_N)$ 来自有限格点的离散化误差。

#### 连续极限：$\alpha 	o 0$

引入时间步长 $\alpha$（物理单位），将离散演化重写为：

$$U_{(N)}(\alpha) = \mathbf{1} - i\alpha H_{(N)} + O(\alpha^2)$$

其中 $H_{(N)}$ 是离散 Hamiltonian，由差异量的局域求和（A3/A4）给出。

**定理（时间连续极限，🔷）**：在 $\alpha 	o 0$、$N 	o \infty$ 的联合极限下（保持 $\alpha \sqrt{N} = 	ext{const}$），演化算符收敛：

$$U_{(N)}(\alpha)^{t/\alpha} \xrightarrow{L^2} e^{-iHt}$$

其中 $H = \lim_{N	o\infty} H_{(N)}$ 是连续 Hamiltonian，$t$ 是连续时间参数。

**证明概要**：

**步骤一**（Trotter 乘积公式）：将 $H_{(N)}$ 分解为局域项之和 $H_{(N)} = \sum_k h_k$，则：

$$e^{-iH_{(N)}t} = \lim_{n	o\infty} \left(\prod_k e^{-ih_k t/n}ight)^n$$

Trotter 误差界：$\left\|\left(\prod_k e^{-ih_k t/n}ight)^n - e^{-iH_{(N)}t}ight\| \leq \frac{t^2}{2n}\sum_{j<k}\|[h_j, h_k]\|$。在 A4（局域性）约束下，$\|[h_j, h_k]\| = 0$ 对非相邻项成立，误差界退化为 $\frac{t^2}{2n} \cdot z \cdot \|h\|^2$，其中 $z$ 为格点配位数（$N=6$ 时 $z=6$），随 $n 	o \infty$ 趋于零。

**步骤二**（$N 	o \infty$ 极限）：$H_{(N)} \xrightarrow{L^2_{	ext{loc}}} H$ 由定理 CL（§4.8）对算符值函数的推广给出，收敛速率 $O(\varepsilon_N)$。

**步骤三**（时间参数的涌现）：连续时间参数 $t$ 是离散步数 $n$ 与步长 $\alpha$ 的乘积 $t = n\alpha$ 在 $\alpha 	o 0$、$n 	o \infty$（$n\alpha = t$ 固定）下的极限。时间的方向性（时间箭头）来自 A5 守恒律的不可逆性：差异量总量在演化中单调耗散（热力学第二定律的离散起源）。

#### 与六公理联合涌现的关系（GR-08）

| 时间性质 | 公理来源 | 状态 |
|:---|:---|:---:|
| 存在性（有演化参数） | A5（守恒律要求动力学） | ✅ |
| 连续性 | 定理 CL（$\alpha 	o 0$ 极限） | 🔷 |
| 方向性（时间箭头） | A5 不可逆耗散 | 🔷 |
| 均匀性（匀速流逝） | A4（局域性，无全局加速） | 🔷 |
| 拓扑结构（$\mathbb{R}^1$） | A9（最小充分实现，排除 $S^1$） | 🔷 |
| 与空间的对称破缺 | A1'（旋转对称仅在空间方向） | 🔷 |

**证明状态**：🔷（离散演化到连续时间的过渡框架完整，Trotter 误差有界；时间六性质的联合涌现论证完整；严格收敛依赖定理 CL 对算符值函数的推广，列为 P1 任务）

---

## 8.5 步骤三：薛定谔方程

### 8.5.1 A7 给出幺正演化

幺正性的完整论证链需要 A7 和 A5 联合：

**A7（闭合循环）给出循环条件**：A7 要求稳定态必须参与有向闭合循环，若演化算符为 $U$，则循环条件要求 $U^n = \mathbb{I}$（某有限 $n$）。这意味着 $U$ 的本征值均在单位圆上，即 $|e^{i\lambda}| = 1$，给出 $U^\dagger U$ 的本征值均为 1。

**A5（守恒律）排除非幺正情形**：A7 的循环条件只要求本征值在单位圆上，但尚未排除 $U^\dagger U 
eq \mathbb{I}$ 的非正规算符情形（例如 Jordan 块）。A5 要求总概率守恒：$\sum_x P_t(x) = 1$ 对所有时刻 $t$ 成立。若 $U^\dagger U 
eq \mathbb{I}$，则存在态 $|\psiangle$ 使得 $\langle \psi | U^\dagger U | \psi angle 
eq \langle \psi | \psi angle$，即演化后的总概率改变，违反 A5。因此 A5 强制 $U^\dagger U = \mathbb{I}$。

**联合结论**：A7（循环，本征值在单位圆上）+ A5（守恒，排除非正规情形）$\Rightarrow$ $U^\dagger U = \mathbb{I}$（幺正性）。幺正性不是量子力学的独立假设，而是 A7 + A5 的联合代数推论。

### 8.5.2 生成元的厄米性

设 $U(\delta t) = \mathbb{I} - i\hat{H}\delta t + O(\delta t^2)$。由幺正性至一阶：

$$U^\dagger U = \mathbb{I} \implies (\mathbb{I} + i\hat{H}^\dagger \delta t)(\mathbb{I} - i\hat{H}\delta t) = \mathbb{I} \implies \hat{H}^\dagger = \hat{H}$$

即生成元必须是厄米算符。A1′ 提供的虚数单位 $i$ 是这一推导的关键——没有复数结构，就无法写出 $e^{-i\hat{H}t/\hbar}$ 的形式。

### 8.5.3 离散哈密顿量的显式验证

对于一维格点，标准离散哈密顿量（离散拉普拉斯算符）定义为：

$$\hat{H}_{xy} = \begin{cases} \dfrac{\hbar^2}{2m\epsilon^2} & x, y\ 	ext{相邻} \\[6pt] -\dfrac{\hbar^2}{m\epsilon^2} & x = y \\[6pt] 0 & 	ext{其他} \end{cases}$$

验证厄米性：$\hat{H}_{xy} = \hat{H}_{yx}$（实对称矩阵，自动厄米）。在连续极限 $\epsilon 	o 0$ 下：

$$\hat{H}\psi(x) = \frac{\hbar^2}{2m\epsilon^2}[\psi(x+\epsilon) + \psi(x-\epsilon) - 2\psi(x)] \xrightarrow{\epsilon 	o 0} -\frac{\hbar^2}{2m}
abla^2\psi$$

即 $\hat{H} 	o -\dfrac{\hbar^2}{2m}
abla^2$（自由粒子哈密顿量）。

**酉对数的最小实例验证**（$N=2$，一维两格点）：

$$\hat{H} = \frac{\hbar^2}{2m\epsilon^2}\begin{pmatrix} -2 & 1 \\ 1 & -2 \end{pmatrix}$$

本征值为 $-\dfrac{\hbar^2}{2m\epsilon^2}$ 和 $-\dfrac{3\hbar^2}{2m\epsilon^2}$，均为实数，$\hat{H}$ 厄米。对应幺正演化算符 $U(\delta t) = e^{-i\hat{H}\delta t/\hbar}$，其矩阵对数 $i\ln U / \delta t = \hat{H}$，厄米性由 $\hat{H}$ 的实对称性保证。$U$ 的幺正性：$U^\dagger U = e^{i\hat{H}^\dagger \delta t/\hbar} e^{-i\hat{H}\delta t/\hbar} = \mathbb{I}$（因 $\hat{H}^\dagger = \hat{H}$）。$\square$

一般情形的酉对数厄米性（对任意 $N$ 的离散格点系统）当前为 🔷（由实对称矩阵的一般性质保证）。

### 8.5.4 薛定谔方程

对连续时间极限 $\delta t 	o 0$：

$$i\hbar \frac{\partial}{\partial t}|\psi(t)angle = \hat{H}|\psi(t)angle$$

$\hbar$ 的量纲来源：A4（最小变易）给出最小作用量尺度，A3（有限离散）给出最小时间步长，两者之积的量纲为作用量，对应 $\hbar$。对易关系 $[\hat{x}, \hat{p}] = i\hbar$ 中精确系数的来源：$i$ 来自 A1′，$\hbar$ 来自 A4，系数 1（而非 $c \cdot i\hbar$）来自 A4 的最小变易条件——每步汉明距离恰好为 1，不多不少，给出最小可能的对易子矩阵元。精确系数的完整验证（通过离散对易子矩阵元的显式计算）见 §8.15。

### ✅ 命题 SE（🔷 强命题）：薛定谔方程

在 A7 + A5（幺正性）+ A1′（复数 $i$）+ A4（连续极限生成元）下，量子态演化方程唯一确定为薛定谔方程形式。离散哈密顿量在最小实例（$N=2$）下的显式验证已完成；一般情形由实对称矩阵的一般性质保证，当前为 🔷。

---

## 8.6 步骤四：路径积分

路径积分是量子力学中联系经典作用量与量子振幅的核心结构。A4（局部性）给出可行路径集合，A7（循环闭合）要求所有相关路径整体参与，A6（DAG 方向性）给出路径的时间排序。三者联合给出路径积分的自然结构骨架：

$$\langle \psi_f | U(t_f, t_i) | \psi_i angle \sim \sum_{	ext{路径}} (	ext{权重})$$

### ⬜ 开放问题：路径积分的公理来源

但从离散路径和到标准连续相位权重 $e^{iS/\hbar}$ 的完整极限，需要偏置算子 $\mathcal{B}_\omega$ 的复数推广（A1′ 提供相位）、Wick 转动的公理来源、以及连续极限下作用量 $S$ 的涌现。以上三点当前均未完成，路径积分保持 ⬜ 开放问题状态，与 WLEM 条款 VI（电弱统一）同属框架开放边界。离散作用量的定义及 Trotter 乘积的收敛论证见 §8.17。

---

## 8.7 步骤五：测量与退相干

### 8.7.1 退相干的单次转移分析

设系统处于叠加态 $|\psi_Sangle = \alpha|0angle + \beta|1angle$，环境处于态 $|E_0angle$。系统与环境通过一次 A4 转移（汉明距离 1 的翻转）耦合。

**耦合前**：$|\Psi_{	ext{前}}angle = (\alpha|0angle + \beta|1angle) \otimes |E_0angle$

**耦合后**（A4 转移使系统状态改变，同时改变环境状态）：

$$|\Psi_{	ext{后}}angle = \alpha|0angle \otimes |E_0angle + \beta|1angle \otimes |E_1angle$$

其中 $|E_1angle$ 是环境与 $|1angle$ 耦合后的状态。对系统求偏迹：

$$ho_S = 	ext{Tr}_E(|\Psi_{	ext{后}}angle\langle\Psi_{	ext{后}}|) = \begin{pmatrix} |\alpha|^2 & \alpha\beta^*\langle E_1|E_0angle \\ \alpha^*\beta\langle E_0|E_1angle & |\beta|^2 \end{pmatrix}$$

非对角元的衰减因子 $f = |\langle E_1|E_0angle|$。

### 8.7.2 衰减因子 $f$ 的计算

$f$ 的值由 A4 转移涉及哪类比特决定，必须精确区分两种情形：

**情形 (a)：A4 转移翻转环境中的一个比特**（系统-环境耦合转移）。环境汉明重量变化 $\pm 1$，$|E_0angle$ 和 $|E_1angle$ 处于不同的 $n_E$ 层。$n_E$ 是量子数基底的一个指标，不同指标的基底态由 Hilbert 空间基底的正交性给出 $\langle E_1|E_0angle = 0$，因此：

$$f = |\langle E_1|E_0angle| = 0$$

完全退相干——一次耦合转移就抹去所有相位信息。此结论是精确的离散结果，不是近似。

**情形 (b)：A4 转移只涉及系统内部比特翻转**（系统内部 A7 循环演化）。环境态不改变，$|E_1angle = |E_0angle$：

$$f = |\langle E_0|E_0angle| = 1$$

相干保持——系统在闭合循环内部演化，不触及环境自由度。

**一般情形**：$|E_0angle$ 和 $|E_1angle$ 是同一 $n_E$ 层内不同角向量子数 $(l, m_l)$ 态的叠加时，由同层内不同 $(l, m_l)$ 态的正交性：

$$\langle E_1|E_0angle = \sum_{l,m_l} b_{lm_l}^* a_{lm_l}, \qquad f = \left|\sum_{l,m_l} b_{lm_l}^* a_{lm_l}ight|$$

若 $(l, m_l)$ 完全不同则 $f = 0$（完全退相干），若完全相同则 $f = 1$（无退相干）。

### ✅ 命题 M-2（🔷 强命题）：单次转移的退相干效果

在 A4 + A6（DAG 不可逆）下：情形 (a) 中 A4 转移翻转环境比特，不同 $n_E$ 层的环境态由 Hilbert 空间基底正交性给出 $\langle E_1|E_0angle = 0$，$f = 0$（完全退相干）；情形 (b) 中 A4 转移只涉及系统内部，环境不变，$f = 1$（相干保持）。$f = 0$ 的结论是精确的离散结果，不是近似。

### 8.7.3 $n$ 次转移后的退相干

经过 $n$ 次 A4 转移，非对角元衰减为 $ho_{01}(n) = \alpha\beta^* \prod_{k=1}^{n} f_k$。情形 (a) 转移每次贡献 $f = 0$，情形 (b) 转移每次贡献 $f = 1$。因此，退相干速率由情形 (a) 的发生频率唯一决定。

### 8.7.4 退相干速率的连续极限

每次情形 (a) 转移导致完全退相干（$f = 0$），因此有效退相干速率直接等于耦合频率：

$$\Gamma_{	ext{eff}} = 
u_{	ext{coupling}}$$

非对角元的指数衰减：$ho_{01}(t) = \alpha\beta^* \cdot e^{-\Gamma_{	ext{eff}} t}$。

对于有限但小的耦合概率 $p_{	ext{couple}} \in (0,1)$（弱耦合正则化模型）：

$$f_{	ext{eff}} = 1 - p_{	ext{couple}}, \qquad \Gamma_{	ext{eff}} = 
u \cdot (-\ln f_{	ext{eff}}) \approx 
u \cdot p_{	ext{couple}}$$

在强耦合极限 $p_{	ext{couple}} 	o 1$ 下恢复 $\Gamma_{	ext{eff}} = 
u_{	ext{coupling}}$；在弱耦合极限下给出 $\Gamma_{	ext{eff}} \approx 
u p_{	ext{couple}}$，与弱耦合近似一致。宏观系统中 $
u_{	ext{coupling}}$ 极大（大量环境自由度），退相干极快；孤立量子系统中 $
u_{	ext{coupling}}$ 极小，相干时间极长。

### 8.7.5 退相干时间与环境自由度数

退相干时间 $t_D = 1/\Gamma_{	ext{eff}}$。对宏观环境（自由度数 $k$ 很大），几乎每次耦合都导致环境汉明重量改变，由情形 (a) 的基底正交性给出 $f = 0$，因此 $t_D$ 趋于一个时间步长量级。定量关系：

$$t_D \propto \frac{1}{k \cdot (1 - \bar{f}_{	ext{单自由度}})}$$

环境自由度越多，退相干越快。这解释了为什么宏观系统中量子叠加态不可观测——不是因为量子力学失效，而是因为环境的 Hilbert 空间结构使退相干速率极快。密度矩阵演化与 Lindblad 方程的完整对接（A6 $	o$ 完全正映射 $	o$ Lindblad 方程）见 §8.7.6。

### ✅ 命题 M-3（🔷 强命题）：退相干速率的连续极限

在情形 (a) 的环境耦合转移下，退相干速率连续极限为 $\Gamma_{	ext{eff}} = 
u_{	ext{coupling}}$，与 Lindblad 方程中的跳跃算符速率参数对应。

### 8.7.6 Lindblad 方程的公理来源

#### 8.7.6.1 问题定位

§8.7 已建立离散退相干的精确机制：A6（DAG）约束下的环境耦合转移在情形 (a) 中给出 $f = 0$（完全退相干），命题 M-3（§8.7.4）给出连续极限退相干速率 $\Gamma_{	ext{eff}} = 
u_{	ext{coupling}}$。本节的任务是：从 A6 约束的非幺正转移算符出发，经 Kraus 表示和完全正映射，推导出 Lindblad 主方程的离散原型，并建立连续极限下的收敛关系。

#### 8.7.6.2 A6 约束下的非幺正转移矩阵

A6（DAG）要求演化图是有向无环图：若有向边 $x 	o y$ 存在，则反向边 $y 	o x$ 被禁止。设局部转移算符为 $T$，则：

$$\langle y | T | x angle 
eq 0 \implies \langle x | T | y angle = 0 \implies T 
eq T^\dagger$$

在最小两态系统 $\{\lvert 1,0angle, \lvert 0,1angle\}$ 中（§6.3）：

$$T = E_{12} = \begin{pmatrix} 0 & 0 \\ 1 & 0 \end{pmatrix}, \qquad T^\dagger = E_{21} = \begin{pmatrix} 0 & 1 \\ 0 & 0 \end{pmatrix}$$

$T$ 是幂零的（$T^2 = 0$），且 $T^\dagger T = 	ext{diag}(1,0) 
eq I$。这正是 A6 破坏幺正性的代数表现。

#### 8.7.6.3 Kraus 算符的构造

单算符极分解 $T = U\sqrt{T^\dagger T}$ 仅给出一个算符，其 $K_1^\dagger K_1 
eq I$，无法构成迹保持映射。必须引入"无跃迁"通道。对每个 A6 允许的不可逆跃迁通道 $k$，定义：

**跳跃算符**（描述跃迁发生）：$K_{k,1} = \sqrt{\gamma_k}\, T_k$，其中 $\gamma_k > 0$ 为单位时间跃迁速率。

**无跃迁算符**（描述系统未发生跃迁）：$K_{k,0} = \sqrt{I - \gamma_k\, T_k^\dagger T_k}$（由谱定理定义，$\gamma_k$ 足够小时半正定）。

#### 8.7.6.4 完全正映射条件的验证

**✅ 定理 KP（Kraus 完备性）**

**陈述**：$\sum_{\alpha=0}^{1} K_{k,\alpha}^\dagger K_{k,\alpha} = I$。

**证明**：$K_{k,0}^\dagger K_{k,0} = I - \gamma_k T_k^\dagger T_k$，$K_{k,1}^\dagger K_{k,1} = \gamma_k T_k^\dagger T_k$。相加得 $I$。$\square$

**多通道推广**：对 $M$ 个独立通道，定义全局无跃迁算符 $K_0 = \sqrt{I - \sum_{k=1}^M \gamma_k T_k^\dagger T_k}$，则 $\sum_{k,\alpha} K_{k,\alpha}^\dagger K_{k,\alpha} = I$ 严格成立。

#### 8.7.6.5 离散主方程

密度矩阵单步演化：$ho(t + \delta t) = K_0 ho K_0^\dagger + \sum_k K_{k,1} ho K_{k,1}^\dagger$。弱耦合极限 $\gamma_k \ll 1$ 下，展开 $K_0 = I - \frac{1}{2}\sum_k \gamma_k T_k^\dagger T_k + O(\gamma^2)$，代入得：

$$\Delta ho = ho(t + \delta t) - ho(t) = \sum_k \gamma_k \left(T_k ho T_k^\dagger - \frac{1}{2}\{T_k^\dagger T_k, ho\}ight) + O(\gamma^2)$$

**✅ 定理 DM（离散主方程）**：在弱耦合极限下，A6 约束的 Kraus 表示给出上述离散主方程。$\square$

#### 8.7.6.6 连续极限：Lindblad 主方程

设 $\gamma_k$ 本身为速率（量纲 $	ext{时间}^{-1}$），则单步跃迁概率为 $\gamma_k \delta t$。取 $\delta t 	o 0$ 极限：

$$\frac{dho}{dt} = \sum_k \gamma_k \left(T_k ho T_k^\dagger - \frac{1}{2}\{T_k^\dagger T_k, ho\}ight)$$

引入 A7 + A5 保证的封闭系统幺正演化 $\frac{dho}{dt}\big|_{	ext{uni}} = -\frac{i}{\hbar}[H, ho]$，联合得标准 Lindblad 方程：

$$\boxed{\frac{dho}{dt} = -\frac{i}{\hbar}[H, ho] + \sum_k \gamma_k \left(L_k ho L_k^\dagger - \frac{1}{2}\{L_k^\dagger L_k, ho\}ight)}$$

其中 $L_k = T_k$ 对应 A6 第 $k$ 条有向跃迁路径，$\gamma_k = 
u_{	ext{coupling}}^{(k)}$ 由命题 M-3 锁定。

#### 8.7.6.7 与 A5（守恒律）的等价性

**✅ 命题 A5-CP**：Kraus 完备性条件 $\sum K_\alpha^\dagger K_\alpha = I$ 严格等价于 A5（概率守恒）在开放系统中的推广。

**证明**：$	ext{Tr}(ho') = 	ext{Tr}(\sum K_\alpha ho K_\alpha^\dagger) = 	ext{Tr}(ho \sum K_\alpha^\dagger K_\alpha)。

A5 要求 $	ext{Tr}(ho') = 	ext{Tr}(ho)$ 对任意 $ho$ 成立，当且仅当 $\sum K_\alpha^\dagger K_\alpha = I$。$\square$

#### 8.7.6.8 迹保持性与退相干速率

**✅ 定理 TP（迹保持性）**：$	ext{Tr}(\Phi(ho)) = 	ext{Tr}(ho)$（定理 KP 的直接推论）。

显式验证（最小两态）：$\Phi(ho)_{12} = \sqrt{1-\gamma}\,ho_{12}$，$n$ 步后 $ho_{12}(t) = e^{-\Gamma_{	ext{eff}} t}ho_{12}(0)$，其中 $\Gamma_{	ext{eff}} = -\dfrac{\ln(1-\gamma)}{2\delta t} \approx \dfrac{\gamma}{2\delta t}$。因子 $1/2$ 来自反对易子项对非对角元的贡献，与标准 Lindblad 理论完全一致。离散框架的瞬时完全退相干（$f=0$）与连续弱耦合极限（$\Gamma_{	ext{eff}} = 
u/2$）在各自适用域内自洽。

#### 8.7.6.9 状态边界

| 命题 | 状态 | 说明 |
|:---|:---:|:---|
| Kraus 构造与完备性（定理 KP） | ✅ | 代数恒等式 |
| 离散主方程（定理 DM） | 🔷 | 弱耦合极限一阶展开 |
| Kraus 完备性 $\Leftrightarrow$ A5 开放推广 | 🔷 | 双向论证完整 |
| Lindblad 连续形式 $\dot{ho} = \cdots$ | 🔶 | 依赖 $\delta t 	o 0$ 极限严格化（QLEM 主定理） |

---

## 8.8 步骤六：不确定性原理

### 8.8.1 三层不确定性的统一框架

不确定性原理在 WorldBase 中来源于公理之间的张力，具有三个层次，共享同一个公理结构：不同公理给出不同的"自然基底"，这些基底之间的张力产生不确定性关系。

| 层次 | 竞争方 | 对易关系 | 物理表现 |
|:---|:---|:---|:---|
| 位置–动量 | A6（DAG 退相干）vs A7（闭合循环） | $[\hat{x}, \hat{p}] = i\hbar$ | $\Delta x \cdot \Delta p \geq \hbar/2$ |
| 稳定性–动力学 | A8（权重算符 $\hat{W}$）vs A7（哈密顿量 $\hat{H}$） | $[\hat{W}, \hat{H}] 
eq 0$（一般情况） | 不能同时处于最稳定态和能量本征态 |
| 模–相位 | A8（权重/模）vs A1′（相位） | 桥接定理的干涉项 | 经典概率 $
eq$ 量子概率 |

每增加一条给出独立基底的公理，就增加一组不确定性关系：A6 给出位置基底，A7 给出动量基底；A8 给出量子数基底，A7 给出能量基底；A8 给出经典概率，A1′ 给出量子相位。

### 8.8.2 A8 与 A7 给出的两套基底

$\hat{W}$（A8 权重算符）的自然基底是量子数基底 $\{\lvert n,l,m_l,sangle\}$，$\hat{H}$（A7 哈密顿量）的自然基底是能量本征基底 $\{\lvert E_kangle\}$。

当 $[\hat{W}, \hat{H}] = 0$ 时，两套基底重合（球对称系统），系统同时具有"最稳定"和"动力学自然"的描述，Born 规则中的 $P_{	ext{cl}}$ 是基底无关的。当 $[\hat{W}, \hat{H}] 
eq 0$ 时，两套基底不重合，系统不能同时处于"最稳定态"和"动力学本征态"——这正是稳定性–动力学不确定性的体现。

**$[\hat{W}, \hat{H}] = 0$ 的条件**（🔶 结构论证）：在连续极限中，维度定理（$D_{	ext{eff}} = 3$）把有效状态空间从 $N$ 维压缩到三维。在这个三维有效子空间上，$N$ 维汉明超立方体的 $S_N$ 置换对称性在 A8 权重的集中效应下涌现出 $O(3)$ 旋转对称性。$\hat{W}$ 和 $\hat{H}$ 都具有 $O(3)$ 对称性，因此可以同时对角化，$[\hat{W}, \hat{H}] = 0$ 在此三维有效子空间上成立。依赖链为：

$$[\hat{W}, \hat{H}] = 0 \xleftarrow{	ext{涌现}} O(3) \xleftarrow{	ext{压缩}} D_{	ext{eff}} = 3 \xleftarrow{	ext{公理}} A1 + A2 + A1' + A9$$

此论证涉及两个尚未严格化的步骤：(1) 维度定理的连续极限版本（当前为 🔷 强命题）；(2) $S_N 	o O(3)$ 的涌现机制——$S_N$ 的不可约表示在 $N 	o \infty$ 时确实可以涌现出连续对称群，但具体涌现出 $O(3)$ 而非其他群的条件尚未展开。因此整体标注为 🔶。

### 8.8.3 不确定性关系的推导

设 $[\hat{x}, \hat{p}] = i\hbar$（对易关系来源：A1′ 给出 $i$，A4 给出最小步长 $\epsilon$，A7 给出循环周期；系数 1 来自 A4 的最小变易条件——每步汉明距离恰好为 1，给出最小可能的对易子矩阵元，严格验证见 §8.15）。由 Cauchy-Schwarz 不等式（纯数学结论，不依赖额外公理假设）：

$$\Delta x \cdot \Delta p \geq \frac{1}{2}|\langle[\hat{x},\hat{p}]angle| = \frac{\hbar}{2}$$

$1/2$ 系数来自 Cauchy-Schwarz 不等式的标准推导，不依赖额外公理。

### ✅ 命题 UP-1（🔷 强命题）：不确定性原理

A6（退相干，位置确定）vs A7（相干演化，动量确定）的竞争，加上 A1′（复数结构，$i\hbar$），在连续极限中给出 $\Delta x \cdot \Delta p \geq \hbar/2$。精确系数 $1/2$ 来自 Cauchy-Schwarz 不等式。

---

## 8.9 泡利不相容原理与费米统计

### 8.9.1 问题定位

A2 已给出单占据性：每个比特 $x_i \in \{0,1\}$，每个模式最多被占据一次。但完整的费米统计还需要：(1) 交换反对称性：多粒子波函数在粒子交换下变号；(2) 从单占据性到反对称性的严格衔接；(3) 费米-狄拉克分布的离散原型。

已有锚点：A2（二元具象）、命题 SPIN（§8.13，$R(2\pi) = -I$）、定理 D（§3.2，$D_{	ext{eff}} = 3$）、A7（循环闭合）、A9（内生完备）。

### 8.9.2 离散交换算符的定义与基本性质

**定义（离散交换算符）**：对两个比特位置 $i 
eq j$，定义：

$$P_{ij}\lvert x_1, \dots, x_i, \dots, x_j, \dots, x_Nangle = \lvert x_1, \dots, x_j, \dots, x_i, \dots, x_Nangle$$

**命题 P-1（对合性）**：$P_{ij}^2 = I$。

**证明**：两次交换恢复原状：$P_{ij}^2\lvert xangle = P_{ij}\lvert x_1,\dots,x_j,\dots,x_i,\dotsangle = \lvert x_1,\dots,x_i,\dots,x_j,\dotsangle = \lvert xangle$。对所有基底态成立，故 $P_{ij}^2 = I$。$\square$

**推论（本征值）**：由 $P_{ij}^2 = I$，$P_{ij}$ 的本征值满足 $\lambda^2 = 1$，故 $\lambda \in \{+1, -1\}$，对应的本征空间分解为 $\mathcal{H} = \mathcal{H}_+ \oplus \mathcal{H}_-$。

**命题 P-2（厄米性）**：$P_{ij}^\dagger = P_{ij}$。（$P_{ij}$ 在计算基底下的矩阵为置换矩阵，实正交，故厄米。）

**命题 P-3（幺正性）**：$P_{ij}^\dagger P_{ij} = I$（由 P-1 和 P-2 联合给出）。

### 8.9.3 $\pi$ 旋转与粒子交换的拓扑等价性

在三维空间中，两个全同粒子的构型空间基本群为：

$$\pi_1(	ext{Conf}_2(\mathbb{R}^d)) = \begin{cases} \mathbb{Z} & d = 2 \quad 	ext{（辫群，任意子统计）} \\ \mathbb{Z}_2 & d \geq 3 \quad 	ext{（交换群，费米/玻色统计）} \end{cases}$$

排除任意子、锁定费米/玻色二分统计的前提是 $d \geq 3$，这由定理 D（$D_{	ext{eff}} = 3$，§3.2）保证。$\mathbb{Z}_2 \cong \pi_1(SO(3))$，其非平凡元对应 $2\pi$ 旋转——在 $SO(3)$ 中 $2\pi$ 旋转是恒等变换，但在其双覆盖 $SU(2)$ 中 $2\pi$ 旋转给出 $-I$。

**关键拓扑链**：

$$	ext{交换两次} \xleftrightarrow{	ext{拓扑等价}} 2\pi 	ext{ 旋转} \xleftrightarrow{	ext{命题 SPIN}} R(2\pi) = -I$$

因此 $P_{ij}^2$（物理效果）$= R(2\pi) = -I$。

### 8.9.4 对称分支的结构性排除

**关键区分**：$P_{ij}^2 = I$ 是 $P_{ij}$ 作为算符的代数性质（作用于配置空间），$P_{ij}^2$ 的物理效果为 $-I$ 是粒子交换在量子力学中的相位约束（作用于态矢量）。两者的协调方式：$P_{ij}$ 的本征值为 $\pm 1$，但物理态必须选择与拓扑约束 $R(2\pi) = -I$ 相容的分支。

**论证一（A7 循环闭合条件的破坏）**：在对称分支中，$P_{ij}\lvert\psiangle = +\lvert\psiangle$。两次交换后态不变（$+1 \cdot +1 = +1$）。但由拓扑约束，两次交换的物理效果为 $R(2\pi) = -I$，应给出 $-\lvert\psiangle$。对称分支要求 $+\lvert\psiangle = -\lvert\psiangle$，即 $\lvert\psiangle = 0$——只有零态满足此条件，非平凡物理态不存在于对称分支中。$\square$

**论证二（A9 的排除）**：对称分支允许 $n_k \geq 2$（多个粒子占据同一模式），需要比特值超出 $\{0,1\}$ 的范围，违反 A2；要支持多重占据数，需引入额外比特，违反 A9（不引入额外自由度）。

**唯一剩余分支**：

$$\boxed{P_{ij}\lvert\psiangle = -\lvert\psiangle \quad 	ext{（费米子）}}$$

此分支与所有公理一致：A7（两次交换给出 $(-1)^2 = +1 = R(4\pi) = +I$，与 $R(2\pi) = -I$ 一致）、A2（$n_k \in \{0,1\}$ 自动满足）、A9（不需要额外自由度）。

### 8.9.5 离散占据数的推导

**命题**：反对称分支中，每个模式 $k$ 的占据数 $n_k \in \{0, 1\}$。

**证明**：设 $n_k \geq 2$，两个全同粒子占据同一模式 $k$。交换它们不改变任何物理量，故 $P_{ij}\lvert\psi_{n_k=2}angle = \lvert\psi_{n_k=2}angle$。但反对称分支要求 $P_{ij}\lvert\psiangle = -\lvert\psiangle$。联合得 $\lvert\psiangle = -\lvert\psiangle$，即 $\lvert\psiangle = 0$。故 $n_k \geq 2$ 的态在反对称分支中不存在，$n_k \in \{0, 1\}$。$\square$

### 8.9.6 离散费米-狄拉克分布

在离散框架中，$N$ 个模式各有占据数 $n_k \in \{0,1\}$。设模式 $k$ 的"能量"为 $\varepsilon_k$，化学势为 $\mu$。由 §10.2.2（比特划分的不相交性），不同模式对应不相交的比特集合，汉明重量偏移按模式可加，A8 权重取乘积形式：

$$w(x) = \prod_{k=1}^{N} w_k(n_k), \qquad w_k(1) = e^{-\beta(\varepsilon_k - \mu)}, \quad w_k(0) = 1$$

单模式占据概率：

$$\langle n_k angle = \frac{w_k(1)}{w_k(0) + w_k(1)} = \frac{e^{-\beta(\varepsilon_k - \mu)}}{1 + e^{-\beta(\varepsilon_k - \mu)}}$$

$$\boxed{\langle n_k angle = \frac{1}{e^{\beta(\varepsilon_k - \mu)} + 1}}$$

这正是**费米-狄拉克分布**的离散原型。分母中的 "$+1$"（对比玻色子的 "$-1$"）直接来自 $P_{ij} = -I$（反对称）的分支选择。

### 8.9.7 完整推导链与命题 PAULI

```
定理 D（D_eff = 3）──→ 构型空间基本群为 Z₂（排除任意子）
                          │
A2（x_i ∈ {0,1}）──→ 单占据性的形式约束
                          │
命题 SPIN（§8.13）──→ R(2π) = -I（费米子特征）
                          │
                          ├──→ §8.9.3：π旋转 ⟺ 粒子交换
                          ├──→ §8.9.4 论证一：A7 排除 P = +I（相位矛盾）
                          ├──→ §8.9.4 论证二：A9 排除 P = +I（需要额外自由度）
                          └──→ P_ij = -I（唯一剩余分支）
                                    │
                                    └──→ §8.9.5：n_k ∈ {0,1}
                                              │
                                              └──→ §8.9.6：⟨n_k⟩ = 1/(e^{β(ε-μ)} + 1)
```

### ✅ 命题 PAULI（🔷 强命题）：泡利不相容原理与费米统计

**前提**：定理 D（$D_{	ext{eff}}=3$）、命题 SPIN（$R(2\pi)=-I$）、A2、A7、A9；§10.2.2 比特划分不相交性。

**陈述**：(1) 对称分支被 A7 和 A9 双重排除，物理态唯一处于反对称分支 $P_{ij}\lvert\psiangle = -\lvert\psiangle$；(2) 由此给出 $n_k \in \{0,1\}$（泡利不相容原理）；(3) A8 权重给出费米-狄拉克分布离散原型 $\langle n_k angle = 1/(e^{\beta(\varepsilon_k-\mu)}+1)$。连续温度/化学势极限下的完整费米-狄拉克统计依赖 QLEM 主定理（🔶）。

### 8.9.8 状态边界

| 命题 | 状态 | 说明 |
|:---|:---:|:---|
| $P_{ij}^2 = I$，本征值 $\pm 1$ | ✅ | 纯代数，无依赖 |
| $\pi$ 旋转 $\leftrightarrow$ 粒子交换 | 🔷 | $\pi_1(SO(3)) = \mathbb{Z}_2$，依赖定理 D |
| $R(2\pi) = -I$ 强制 $P_{ij} = -I$ | 🔷 | 依赖命题 SPIN + A7 循环闭合 |
| A7 排除对称分支 | 🔷 | 相位多值性矛盾 |
| A9 排除对称分支 | 🔷 | $n_k \geq 2$ 需要额外自由度 |
| $n_k \in \{0,1\}$ | 🔷 | 反对称性的直接推论 |
| 费米-狄拉克分布（离散原型） | 🔷 | A8 权重 + $n_k \in \{0,1\}$（依赖 §10.2.2） |
| 连续完整费米-狄拉克统计 | 🔶 | 依赖 QLEM 主定理 |

---

## 8.10 三层不确定性的统一框架

量子力学中三类核心不确定性在 WorldBase 中有统一的公理来源：

| 不确定性类型 | 公理对立 | 物理表现 |
|:---|:---|:---|
| 位置–动量 | A6（退相干）vs A7（相干演化） | $\Delta x \cdot \Delta p \geq \hbar/2$ |
| 稳定性–动力学 | A8（对称稳定）vs A7（循环演化） | 能量–时间不确定性 |
| 模–相位 | A8（权重/模）vs A1′（相位） | 粒子数–相位不确定性 |

三层不确定性不是独立的量子"奇异性"，而是同一组公理张力在不同物理截面上的投影。

---

## 8.11 QLEM 与 WLEM 的 A8 接口

A8（对称偏好）在两个不同的物理推导中承担双重角色，但权重函数的具体形式在不同推导中有所不同。在 WLEM（弱力质量公式）中，A8 通过约束度函数 $K(w) = K_0 + \lnho(w)$（其中 $ho(w) = \binom{N}{w}/\binom{N}{N/2}$，与 $\ln\binom{N}{w}$ 差一个常数）决定势垒高度 $\Delta K$，进而给出 W/Z 玻色子质量 $m_W = \Delta K \cdot m_0$。在 QLEM（量子力学 Born 规则）中，A8 通过指数衰减权重 $w(x) = \exp(-|\delta(x)|)$ 决定振幅模 $|\psi(x)|^2 = w(x)/Z$，进而通过引理 5.0 给出基底态测量概率。

两者共享 A8 的公理内核——对称偏好（偏离中截面的态受到抑制），但权重函数的具体形式不同（WLEM 使用组合数约束度，QLEM 使用指数衰减权重）。**质量是 A8 对称偏好在规范方向上的势垒体现，概率是 A8 对称偏好在状态空间上的统计体现**，两者是同一公理内核在不同截面上的投影，但这个统一图景的严格数学表述列为后续工作。

---

## 8.12 量子力学部分的统一逻辑链条

$$A2 \Rightarrow 	ext{二值基底} \Rightarrow 	ext{量子比特}$$

$$A8 + A1' + A9 \xrightarrow{	ext{Gleason（引理 5.0 支撑，无循环）}} 	ext{Born 规则基底态（🔷）}$$

$$A8 + A1' + A9 \xrightarrow{	ext{Gleason（叠加态，非上下文性连续极限待验证）}} 	ext{Born 规则叠加态（🔶）}$$

$$A7 + A5 + A1' + A4 \Rightarrow 	ext{薛定谔方程（🔷）}$$

$$A6\ (	ext{情形 a，环境比特翻转，基底正交性}) \Rightarrow f=0 \Rightarrow \Gamma_{	ext{eff}} = 
u_{	ext{coupling}}\ 	ext{（🔷）}$$

$$A6\ 	ext{vs}\ A7 + A1' \Rightarrow \Delta x \cdot \Delta p \geq \hbar/2\ 	ext{（🔷）}$$

$$A4 + A6 + A7 \Rightarrow 	ext{路径积分骨架（⬜）}$$

关于"四定理平行结构"的说明：§8.1 中提及量子力学部分与 CL/CLEM/WLEM 形成"四定理平行结构"，这是指推导完成度的类比——五步推导均已达强命题水平，类比于三个连续极限定理的完成度。但 QLEM 目前没有一个单一核心定理对标定理 CL 或定理 CLEM。当前量子力学部分的定位是"六步推导的集合，五步达 🔷 水平"，而非"一个统一涌现定理"。QLEM 主定理（从离散差异图到完整连续量子理论的严格桥梁）是整个框架最重要的未完成任务，一旦完成将使 QLEM 真正与 CL/CLEM/WLEM 并列。

---

## 8.13 自旋的公理来源

### 8.13.1 问题定位

自旋是量子力学的基本内禀自由度，标准量子力学将其作为独立假设引入。在 WorldBase 中，自旋的全部代数结构——$\mathfrak{su}(2)$ 生成元、半整数本征值、旋转 $2\pi$ 获得 $-1$ 相位——均应从公理推导。

已有锚点：定理 W-2（§6.6.2，A6 + A4 在最小两态系统上给出 $\mathfrak{su}(2)$ 闭合，生成元 $\{H_1, H_2, H_3\} = \frac{1}{2}\{\sigma_x, \sigma_y, \sigma_z\}$）、定理 D（§3.2，$D_{	ext{eff}}=3$，空间旋转群为 $SO(3)$）、命题组 H（§8.3，复 Hilbert 空间结构已建立）。

关键洞察：弱力的手征结构与自旋的内禀角动量共享同一个 $\mathfrak{su}(2)$ 代数来源，区别仅在于物理截面：弱力中 $T=E_{12}$ 的非厄米性给出宇称破缺，自旋中 $SO(3)$ 的射影表示给出费米子特征。

### 8.13.2 $SO(3)$ 射影表示与 $SU(2)$ 双覆盖

由定理 D，三维有效空间中的连续旋转对称性对应群 $SO(3)$。在量子力学中，态矢量在旋转下的变换允许一个全局相位不确定性，因此物理旋转群的实际表示是 $SO(3)$ 的**射影表示**。根据 Bargmann 定理，$SO(3)$ 的射影表示一一对应于其万有覆盖群 $SU(2)$ 的线性表示。

在离散框架中，$SU(2)$ 代数已由定理 W-2 精确给出：

$$[H_i, H_j] = i\varepsilon_{ijk}H_k, \qquad H_i = \frac{1}{2}\sigma_i$$

这正是 $\mathfrak{su}(2)$ 李代数。因此，离散差异空间天然携带 $SU(2)$ 表示结构。

### 8.13.3 旋转 $2\pi$ 与费米子特征

取 $SU(2)$ 的 $j=1/2$ 不可约表示，角动量算符为 $\hat{S}_i = \hbar H_i = \frac{\hbar}{2}\sigma_i$。绕 $z$ 轴旋转角度 $	heta$ 的算符为：

$$R_z(	heta) = \exp\!\left(-\frac{i}{\hbar}	heta \hat{S}_z ight) = \exp\!\left(-\frac{i}{2}	heta \sigma_z ight) = \begin{pmatrix} e^{-i	heta/2} & 0 \\ 0 & e^{i	heta/2} \end{pmatrix}$$

令 $	heta = 2\pi$：

$$R_z(2\pi) = \begin{pmatrix} e^{-i\pi} & 0 \\ 0 & e^{i\pi} \end{pmatrix} = \begin{pmatrix} -1 & 0 \\ 0 & -1 \end{pmatrix} = -I$$

**物理含义**：空间旋转 $2\pi$ 后态矢量获得整体 $-1$ 因子，即 $R(2\pi)\lvert\psiangle = -\lvert\psiangle$。这正是**费米子**的拓扑特征——波函数需旋转 $4\pi$ 才恢复原值。

### 8.13.4 半整数本征值的必然性

由 $R_z(2\pi) = -I$ 与谱定理：

$$\exp\!\left(-\frac{i}{\hbar} 2\pi \hat{S}_z ight) = -I \implies \exp(-2\pi i m) = -1$$

其中 $m$ 为 $\hat{S}_z$ 的本征值除以 $\hbar$。解得 $m \in \mathbb{Z} + \dfrac{1}{2}$。在二维不可约表示中，$m$ 仅能取两个值，最小选择为 $m = \pm\dfrac{1}{2}$。因此：

$$\boxed{\hat{S}_i = \frac{\hbar}{2}\sigma_i, \quad 	ext{本征值 } \pm\frac{\hbar}{2}}$$

自旋算符是 $\mathfrak{su}(2)$ 生成元的物理实现，半整数本征值是 $SU(2)$ 双覆盖结构的必然推论。$\square$

### ✅ 命题 SPIN（🔷 强命题）：自旋的公理推导

**前提**：定理 D（$D_{	ext{eff}}=3$）、定理 W-2（$\mathfrak{su}(2)$ 闭合）、命题组 H（复 Hilbert 空间）。

**陈述**：离散差异空间携带 $SO(3)$ 射影表示，其万有覆盖 $SU(2)$ 的 $j=1/2$ 表示给出自旋角动量算符 $\hat{S}_i = \frac{\hbar}{2}\sigma_i$，满足 $R(2\pi)=-I$ 与本征值 $\pm\hbar/2$。

**证明**：§8.13.2–8.13.4。$\square$

---

## 8.14 纠缠的公理来源

### 8.14.1 问题定位

纠缠是量子力学最具非经典特征的现象。在 WorldBase 中，纠缠从 A7（循环闭合）推导——当 A7 的闭合循环跨越多个子系统时，循环条件强制产生非定域关联。

### 8.14.2 子系统划分与态的分类

将总比特集 $G = \{1, \dots, N\}$ 划分为不相交子集 $G = G_A \sqcup G_B$，对应 Hilbert 空间分解 $\mathcal{H}_N = \mathcal{H}_A \otimes \mathcal{H}_B$。

- **可分离态**：$\lvert\psiangle = \lvert\psi_Aangle \otimes \lvert\psi_Bangle$
- **纠缠态**：$\lvert\psiangle 
eq \lvert\psi_Aangle \otimes \lvert\psi_Bangle$

### 8.14.3 A7 循环的子系统跨越条件

A7 要求稳定态参与有向闭合循环 $\gamma$。定义循环的**子系统跨度**：

- **$G_A$-内循环**：$\gamma$ 中所有 A4 翻转仅涉及 $G_A$ 比特。
- **跨子系统循环**：$\gamma$ 中至少一次翻转涉及 $G_A$，至少一次涉及 $G_B$。

### 8.14.4 跨子系统循环产生纠缠

**命题**：设 A7 循环 $\gamma$ 为跨子系统循环，且不可分解为 $\gamma_A \times \gamma_B$。则由 $\gamma$ 生成的稳定态叠加为纠缠态。

**证明**（构造与不可分离性）：取 $N=4$，$G_A=\{1,2\}$，$G_B=\{3,4\}$。跨子系统循环 $\gamma$ 包含三步 A4 转移：

$$\lvert 1,0,1,0angle \xrightarrow{E_{13}} \lvert 0,0,1,1angle \xrightarrow{E_{31}} \lvert 1,0,0,1angle \xrightarrow{E_{24}} \lvert 1,1,0,0angle \xrightarrow{\cdots} \lvert 1,0,1,0angle$$

A7 循环条件要求稳态为参与态的等权叠加（由 A8 对称性保证）：

$$\lvert\psiangle = \frac{1}{\sqrt{3}}\bigl(\lvert 1,0angle_A\lvert 1,0angle_B + \lvert 1,0angle_A\lvert 0,1angle_B + \lvert 1,1angle_A\lvert 0,0angle_B\bigr)$$

设 $\lvert\psiangle = \lvert\psi_Aangle \otimes \lvert\psi_Bangle$，展开对比系数可得矛盾方程组，故 $\lvert\psiangle$ 不可分离。若循环完全在 $G_A$ 内，则 $\lvert\psiangle = \lvert\psi_Aangle \otimes \lvert\phi_Bangle$，$S_A=0$。$\square$

### 8.14.5 纠缠熵

定义离散纠缠熵 $S_A = -	ext{Tr}(ho_A \ln ho_A)$。对上述 $\lvert\psiangle$，约化密度矩阵 $ho_A = 	ext{diag}(2/3, 1/3)$，得：

$$S_A = \ln 3 - \frac{2}{3}\ln 2 \approx 0.636 > 0$$

$G_A$-内循环给出 $S_A=0$。因此 $S_A>0$ 是循环跨子系统拓扑结构的直接度量。

### ✅ 命题 ENT（🔷 强命题）：纠缠的公理推导

**前提**：A7（循环闭合）、A4（局部演化）、$\mathcal{H}_N = \mathcal{H}_A \otimes \mathcal{H}_B$。

**陈述**：当 A7 循环 $\gamma$ 跨越子系统划分且不可分解时，稳态叠加为纠缠态（$S_A>0$）。当 $\gamma$ 限制于单一子系统时，态可分离（$S_A=0$）。

**证明**：§8.14.2–8.14.5。$\square$

---

## 8.15 $[\hat{x}, \hat{p}] = i\hbar$ 连续极限验证

### 8.15.1 问题定位

§8.5.4 与 §8.8.3 中 $[\hat{x}, \hat{p}] = i\hbar$ 的系数标注为 🔶。本节证明该等式在连续极限 $\epsilon_N 	o 0$ 下精确成立，有限 $N$ 修正为 $O(\epsilon_N^2)$，系数 1 由 A4 唯一确定。

### 8.15.2 算符定义与对易子展开

位置算符：$\hat{x}_k = \epsilon_N \sum_{i \in G_k} x_i$（第 $k$ 维嵌入坐标）。

动量算符（对称离散差分）：$\hat{p}_k = -i\hbar \dfrac{T_k - T_k^\dagger}{2\epsilon_N}$，其中 $T_k$ 为沿 $G_k$ 方向的单步平移算符（A4 保证 $d_H=1$）。

对任意光滑波函数 $\psi(\mathbf{x})$，Taylor 展开至三阶：

$$(\hat{x}_k \hat{p}_k - \hat{p}_k \hat{x}_k)\psi(\mathbf{x}) = i\hbar \left[ \psi(\mathbf{x}) - \frac{\epsilon_N^2}{3}\frac{\partial^2\psi}{\partial x_k^2} + O(\epsilon_N^4) ight]$$

即算符等式：

$$[\hat{x}_k, \hat{p}_k] = i\hbar \left( I - \frac{\epsilon_N^2}{3}\partial_k^2 + O(\epsilon_N^4) ight)$$

### 8.15.3 系数 1 的公理来源与连续极限

**系数 1**：若 A4 改为 $d_H = k$（每步翻转 $k$ 个比特），则有效步长为 $k\epsilon_N$，对易子首项变为 $ik\hbar$。A4 严格限定 $d_H=1$，故系数精确为 1。

**$O(\epsilon_N^2)$ 修正**：来自离散差分的二阶截断误差，对称构造消去了 $O(\epsilon_N)$ 项。

**连续极限**：$\epsilon_N 	o 0$ 时，$O(\epsilon_N^2)$ 项消失，精确恢复：

$$\boxed{\lim_{\epsilon_N 	o 0} [\hat{x}_k, \hat{p}_l] = i\hbar\delta_{kl}}$$

### ✅ 命题 CCR（🔷 强命题）：对易关系的连续极限

**前提**：A4（$d_H=1$）、A1'（复数结构）、A7+A5（幺正演化）。

**陈述**：离散位置-动量对易子在连续极限下收敛为 $[\hat{x}_k, \hat{p}_l] = i\hbar\delta_{kl}$。有限 $N$ 修正为 $O(\epsilon_N^2)$，系数 1 由 A4 唯一锁定。

**证明**：§8.15.2–8.15.3。$\square$

---

## 8.16 Dirac 方程的公理推导

### 8.16.1 问题定位

在 WorldBase 中，Dirac 方程的全部代数结构——Clifford 代数、手征投影、旋量表示——均应从公理推导。已有锚点：命题 SPIN（§8.13）、定理 LT（Lorentz 协变性）、A6、A4、A9。

### 8.16.2 Clifford 代数的公理构造

Dirac 代数的四个生成元来自两个不同的公理方向：$\gamma^0$ 来自 A6（DAG 有向性）编码的时间演化方向，$\gamma^i$ 来自 A1'（横向旋转）与命题 SPIN 给出的自旋矩阵。

**四维旋量空间的构造**：取 $\mathcal{H}_{	ext{Dirac}} = \mathbb{C}^2 \oplus \mathbb{C}^2$，两个 $\mathbb{C}^2$ 分量分别对应 A6 的"有向/反向"二分与 A1' 的二维横向自由度。A9 保证四维是最小充分维度。

在 Weyl 表示中：

$$\gamma^0 = \begin{pmatrix} 0 & I_2 \\ I_2 & 0 \end{pmatrix}, \qquad \gamma^i = \begin{pmatrix} 0 & \sigma_i \\ -\sigma_i & 0 \end{pmatrix}$$

### 8.16.3 Clifford 反交换关系的验证

**✅ 定理 CLIFF**：上述 $\gamma^\mu$ 满足 Clifford 反交换关系：

$$\{\gamma^\mu, \gamma^
u\} = 2\eta^{\mu
u}I$$

其中 $\eta = 	ext{diag}(+1, -1, -1, -1)$。

**证明**：逐项验证，利用 Pauli 矩阵的反交换关系 $\{\sigma_i, \sigma_j\} = 2\delta_{ij}I$。$\square$

### 8.16.4 手征算符与 Weyl 投影

定义 $\gamma^5 = i\gamma^0\gamma^1\gamma^2\gamma^3$。在 Weyl 表示中显式计算得：

$$\gamma^5 = \begin{pmatrix} -I_2 & 0 \\ 0 & I_2 \end{pmatrix}$$

满足 $(\gamma^5)^2 = I$，$\{\gamma^5, \gamma^\mu\} = 0$，且为厄米算符。

**Weyl 投影算符**：

$$P_L = \frac{1}{2}(I - \gamma^5) = \begin{pmatrix} I & 0 \\ 0 & 0 \end{pmatrix}, \qquad P_R = \frac{1}{2}(I + \gamma^5) = \begin{pmatrix} 0 & 0 \\ 0 & I \end{pmatrix}$$

**🔷 命题 WEYL（手征投影的公理来源）**：$\gamma^5$ 的块对角结构将旋量空间分解为左/右手子空间。A6 的非厄米转移算符 $T$ 的极分解给出 $T_L = (T - T^\dagger)/2i$（反厄米/A 分量），该分量精确对应左手投影 $P_L$。因此 **A6 的 DAG 有向性选择等价于选择左手 Weyl 投影**，这是弱力 $V$-$A$ 结构的深层来源。

### 8.16.5 离散 Dirac 方程

$$(i\gamma^\mu \Delta_\mu - m_0)\psi = 0$$

其中 $\Delta_\mu$ 是沿第 $\mu$ 方向的离散差分（$d_H=1$，满足 A4），$m_0$ 为基本质量单位。方程在 $N=4$ 最小格点上为 $64 \times 64$ 线性系统。旋量四分量由 A6 与 A1' 的公理结构决定，A9 保证其最小性。

### 8.16.6 概率流守恒

定义概率流 $j^\mu = \bar{\psi}\gamma^\mu\psi$，其中 $\bar{\psi} = \psi^\dagger \gamma^0$。

**🔷 定理 JC**：离散 Dirac 方程的概率流满足 $\Delta_\mu j^\mu = O(\epsilon_N)$，在连续极限 $\epsilon_N 	o 0$ 下精确恢复 $\partial_\mu j^\mu = 0$。总概率守恒由 A5 在任意尺度下精确保证（定理 TP）。

### 8.16.7 完整推导链

```
定理 LT（SO⁺(1,3) 涌现）+ 命题 SPIN（SU(2) 双覆盖）
    │
    ├──→ γ⁰ 来自 A6，γⁱ 来自 A1'（Weyl 表示）
    │
    ├──→ {γᵘ, γᵛ} = 2ηᵘᵛI（定理 CLIFF ✅）
    │
    ├──→ γ⁵ = iγ⁰γ¹γ²γ³，P_L/R = ½(1∓γ⁵)
    │      A6 有向选择 ⟺ 左手 Weyl 投影（命题 WEYL 🔷）
    │
    ├──→ (iγᵘΔᵘ - m₀)ψ = 0（离散 Dirac 方程，A4 + A9）
    │
    └──→ Δᵘjᵘ = O(ε_N)（定理 JC 🔷）
```

### 8.16.8 与弱力手征结构的统一

| 离散框架（§6） | Dirac 框架（§8.16） | 对应关系 |
|:---|:---|:---|
| $T 
eq T^\dagger$（A6） | $\gamma^5$ 反对易 | A6 有向性编码为手征性 |
| $T_L = (T-T^\dagger)/2i$ | $P_L = \frac{1}{2}(I - \gamma^5)$ | 左手分量 |
| $\mathcal{P}T\mathcal{P}^{-1} = T^\dagger 
eq T$ | $\gamma^0\gamma^5\gamma^0 = -\gamma^5$ | 宇称破缺 |
| $V$-$A$ 耦合（定理 W-3） | $\bar{\psi}\gamma^\mu(1-\gamma^5)\psi$ | 矢量-轴矢结构 |
| $\lvert g_V\vert = \lvert g_A\vert$ | $\gamma^\mu$ 和 $\gamma^\mu\gamma^5$ 系数相等 | A9 自由度挤压 |

### 8.16.9 状态边界

| 命题 | 状态 | 说明 |
|:---|:---:|:---|
| $\gamma$ 矩阵构造（Weyl 表示） | ✅ | 显式 $4\times 4$ 矩阵 |
| Clifford 反交换关系（定理 CLIFF） | ✅ | 逐项验证完整 |
| $\gamma^5$ 定义与性质 | ✅ | 显式计算 |
| Weyl 投影 $P_{L/R}$ | ✅ | 幂等、正交、完备 |
| A6 有向性 $\leftrightarrow$ 左手投影（命题 WEYL） | 🔷 | 构造性对应 |
| 离散 Dirac 方程 | 🔷 | A4 局部性、A9 最小维度 |
| 概率流守恒（定理 JC） | 🔷 | 连续极限下精确 |
| 连续偏微分形式 | 🔶 | 依赖 QLEM 主定理 |

---

## 8.17 QLEM 主定理：离散→连续量子桥梁

### 8.17.1 问题定位

QLEM 主定理是 WorldBase 框架最后的核心缺口。类比定理 CL（引力连续极限）、定理 CLEM（电磁连续极限）、定理 WLEM（弱力连续极限），QLEM 需要建立从离散差异图 $\{0,1\}^N$ 到完整连续量子理论的严格桥梁。

已有锚点（T-001–T-008 全量闭环）：

| 子结构 | 来源 | 状态 |
|:---|:---|:---:|
| Hilbert 空间 | 命题组 H（§8.3） | 🔷 |
| Born 规则（基底态） | 命题 BR-2a（§8.4.3） | 🔷 |
| Born 规则（叠加态） | Gleason 路径（§8.4.5） | 🔷 |
| 薛定谔方程 | 命题 SE（§8.5） | 🔷 |
| 退相干 | 命题 M-2/M-3（§8.7）+ Lindblad（§8.7.6） | 🔷 |
| 不确定性原理 | 命题 UP-1（§8.8） | 🔷 |
| 自旋 | 命题 SPIN（§8.13） | 🔷 |
| 纠缠 | 命题 ENT（§8.14） | 🔷 |
| 泡利不相容 | 命题 PAULI（§8.9） | 🔷 |
| Dirac 方程 | 定理 CLIFF + 命题 WEYL（§8.16） | 🔷 |

QLEM 的任务不是重新推导这些子结构，而是证明它们在连续极限下兼容、完整、且精确覆盖标准量子力学的全部核心结构。

### 8.17.2 离散作用量的定义

对一条允许的演化路径 $\gamma = (x_0, x_1, \dots, x_T)$（A4 保证相邻态之间 $d_H = 1$），定义路径上的约束度变化序列：

$$\Delta K_k = K(w(x_k)) - K(w(x_{k-1}))$$

其中 $K(w) = K_0 + \lnho(w)$ 是 §6.11.1 的约束度函数（$ho(w) = \binom{N}{w}/\binom{N}{N/2}$）。

**离散作用量**：

$$S_N[\gamma] = \sum_{k=1}^{T} \Delta K_k \cdot m_0 \cdot \Delta t_k$$

其中 $\Delta t_k = \alpha$ 是基本时间量子（A3 + A4 确定，$c\alpha = \epsilon_N$）。

**量纲验证**：$[\Delta K] = 1$（无量纲），$[\Delta K \cdot m_0] = [E]$（WLEM 能量量纲），$[\Delta t_k] = T$，故 $[S_N] = ML^2T^{-1}$，正是作用量量纲。$\checkmark$

### 8.17.3 路径权重的构造

由 A1'（相位自由度 $e^{i	heta}$），路径 $\gamma$ 的量子权重为：

$$\mathcal{W}_N(\gamma) = \exp\!\left(\frac{i}{\hbar}S_N[\gamma]ight) = \prod_{k=1}^{T}\exp\!\left(\frac{i}{\hbar}\Delta K_k \cdot m_0 \cdot \alphaight)$$

离散传播子（从初态 $x_i$ 到末态 $x_f$ 的概率幅）定义为：

$$\mathcal{K}_N(x_f, x_i; T) = \sum_{\gamma:\, x_i 	o x_f} \mathcal{W}_N(\gamma)$$

其中求和遍历所有从 $x_i$ 到 $x_f$ 的允许路径（A4 保证每步 $d_H = 1$，A6 保证有向性）。

### 8.17.4 Trotter 乘积与连续极限

离散传播子可以写为转移矩阵的乘积：

$$\mathcal{K}_N(x_f, x_i; T) = \langle x_f \lvert \hat{U}^T \rvert x_i angle$$

其中 $\hat{U}$ 是单步转移算符。A4 要求每次演化只改变一个比特，设第 $k$ 步翻转第 $i_k$ 个比特，则 $\hat{U}_k = e^{-i\hat{H}_{i_k}\alpha/\hbar}$。总演化算符为：

$$\hat{U}^T = \prod_{k=1}^{T} e^{-i\hat{H}_{i_k}\alpha/\hbar}$$

由 Trotter 乘积公式：

$$\prod_{k=1}^{T} e^{-i\hat{H}_{i_k}\alpha/\hbar} = e^{-i\hat{H}_{	ext{eff}}T\alpha/\hbar} + O(\alpha^2)$$

其中 $\hat{H}_{	ext{eff}} = \sum_k \hat{H}_{i_k}/T$ 是平均局部哈密顿量。令 $T\alpha = t$ 固定，取极限 $T 	o \infty$、$\alpha 	o 0$：

$$\hat{U}^T 	o e^{-i\hat{H}_{	ext{eff}}t/\hbar}$$

Trotter 误差 $O(\alpha^2) \cdot T = O(\alpha t) 	o 0$。

**极限顺序说明**：上述论证涉及两个独立的极限过程：**极限 (a)**：$T 	o \infty$，$\alpha 	o 0$，$T\alpha = t$ 固定（Trotter 极限）；**极限 (b)**：$N 	o \infty$，$\epsilon_N 	o 0$（连续空间极限）。定理 QLEM-1 在**固定 $N$**（有限维 Hilbert 空间）下证明极限 (a)，此时 $\hat{H}$ 是有限维矩阵，自动有界，Trotter-Kato 公式无条件适用。两个极限的交换依赖无限维完备性（§8.3.4，当前 ⬜）。

**🔷 定理 QLEM-1（离散路径和收敛）**：离散传播子 $\mathcal{K}_N$ 在连续极限 $\alpha 	o 0$（$T 	o \infty$，$T\alpha = t$ 固定）下收敛为：

$$\mathcal{K}_N(x_f, x_i; T) 	o \langle x_f\lvert e^{-i\hat{H}t/\hbar}\rvert x_i angle$$

收敛速率 $O(\alpha)$（Trotter 一阶误差）。在固定有限 $N$ 下为 ✅；在 $N 	o \infty$ 连续极限下为 🔷（依赖无限维完备性，§8.3.4 ⬜）。

### 8.17.5 Wick 转动的公理来源

A6（DAG）要求演化图是有向无环图，转移算符 $T$ 非厄米。谱半径 $\rho(T) \leq 1$ 的保证来自两个公理的联合：

**A5（概率守恒）**：A5 要求总概率守恒，$\sum_y |T_{yx}|^2 \leq 1$，在 $\ell^1$ 算符范数下 $\|T\|_1 \leq 1$，进而谱半径 $\rho(T) \leq \|T\|_1 \leq 1$。这是 $r_k \leq 1$ 的来源。

**A6（DAG 不可逆）**：A6 保证演化图无有向环路。对有向图的邻接矩阵，通过拓扑排序可将其化为严格下三角矩阵，谱半径为零。在更一般的转移算符中，A6 的结构保证至少存在一个本征值严格小于 1。

**A5 与 A6 的分工**：A5 控制上界（$\rho(T) \leq 1$），A6 的 DAG 结构给出谱半径严格小于 1。两者联合给出 $0 \leq \rho(T) < 1$（严格收缩）。

定义 Euclidean 时间步长 $\Delta\tau = i\Delta t$，Euclidean 转移算符 $T_E = e^{-\hat{H}\Delta\tau/\hbar}$。解析延拓 $t 	o -i\tau$ 后，$T_E$ 的本征值 $e^{-E_k\Delta\tau/\hbar}$ 为实数且小于 1（对 $E_k > 0$），保证路径权重在 Euclidean 时间中指数衰减。

**🔷 定理 QLEM-2（Wick 转动的公理来源）**

A6 的 DAG 结构保证转移算符 $T$ 的谱半径 $< 1$，其解析延拓 $t 	o -i	au$ 给出 Euclidean 热核 $e^{-\hat{H}	au/\hbar}$，为 Feynman 积分提供严格收敛基础。

> **注记（与 Osterwalder-Schrader 公理的关系）**：Wick 转动的严格性等价于 Osterwalder-Schrader 反射正性条件。在 WorldBase 框架中，反射正性由 A5（正定能量，$\Delta E \geq 0$）和 A7（幺正演化，$U^\dagger U = I$）联合保证，无需独立引入 OS 公理。

在固定有限 $N$ 下为 ✅；在 $N 	o \infty$ 连续极限下为 🔷（依赖无限维完备性，§8.3.4 ⬜）。

### 8.17.6 Born 规则叠加态的连续极限

§8.4.5 中 Born 规则叠加态的推导依赖 Gleason 定理的非上下文性条件。A9（内生完备）保证离散框架中的概率赋值不依赖测量上下文（分组方案）。在连续极限下，非上下文性约束通过极限过程保持：

**(a)** 离散概率赋值 $P_N(x) = w(x)/Z$ 对所有分组方案一致（A9 保证）。

**(b)** 在 $L^2$ 收敛框架下（§8.3.4），$P_N$ 弱收敛到连续概率赋值 $P$。弱收敛保持线性性和正性（纯分析学结论）。

**(c)** 连续概率赋值 $P$ 的线性性和正性（由 (b) 保证），加上框架函数归一化条件 $\sum_i P(e_i) = 1$（由命题 BR-2a 在连续极限下保持），以及 Hilbert 空间维度 $\geq 3$（由定理 D 保证），满足 Gleason 定理的全部前提条件，唯一解为 $P = 	ext{Tr}(ho P_{	ext{proj}}) = |\langle\phi|\psiangle|^2$。

**关键依赖**：步骤 (b) 的 $L^2$ 收敛框架（§8.3.4）当前为 ⬜。因此定理 QLEM-3 的状态为 🔷（论证框架完整，关键步骤依赖 ⬜ 子结果）。

**与 Lorentz 协变性的关系**：定理 LT（Lorentz 协变性）保证连续 Born 规则在参考系变换下不变（概率是 Lorentz 标量），这是非上下文性的一个推论，但不是非上下文性本身的来源。非上下文性的来源是 A9（离散层面）和 $L^2$ 收敛（连续层面）。

**🔷 定理 QLEM-3（Born 规则连续极限）**：在连续极限 $N 	o \infty$ 下，离散概率赋值 $P_N(x) = w(x)/Z$ 收敛为连续 Born 规则 $P(\phi) = |\langle\phi|\psiangle|^2$，非上下文性在极限下保持。

### 8.17.7 QLEM 主定理

**🔷 定理 QLEM（离散→连续量子桥梁）**

在连续极限 $N 	o \infty$（$\epsilon_N 	o 0$，$\alpha 	o 0$）下，离散差异系统 $\{0,1\}^N$ 的量子结构收敛为标准连续量子理论的全部核心结构：

| 子结构 | 离散原型 | 连续极限 | 收敛定理 |
|:---|:---|:---|:---|
| Hilbert 空间 | $\mathbb{C}^{2^N}$，内积 $\langle\phi\vert\psiangle = \sum_x \bar{\phi}\psi \cdot w/Z$ | $L^2(\mathbb{R}^3)$，标准内积 | 命题组 H + $L^2$ 紧性（⬜） |
| Born 规则 | $P(x) = w(x)/Z$ | $P(\phi) = \vert\langle\phi\vert\psiangle\vert^2$ | 定理 QLEM-3（🔷） |
| 薛定谔方程 | $\hat{U} = \prod_k e^{-i\hat{H}_k\alpha/\hbar}$ | $i\hbar\partial_t\psi = \hat{H}\psi$ | 命题 SE + 定理 QLEM-1（🔷） |
| 路径积分 | $\mathcal{K}_N = \sum_\gamma e^{iS_N[\gamma]/\hbar}$ | $\mathcal{K} = \int\mathcal{D}x\, e^{iS/\hbar}$ | 定理 QLEM-1 + QLEM-2（🔷） |
| 退相干 | $f = 0$（情形 a），$\Gamma = 
u_{	ext{coupling}}$ | Lindblad 方程 | 命题 M-3 + 定理 DM（🔷） |
| 不确定性原理 | A6 vs A7 + A1' | $\Delta x \cdot \Delta p \geq \hbar/2$ | 命题 UP-1 + 命题 CCR（🔷） |
| 自旋 | $R(2\pi) = -I$，$\mathfrak{su}(2)$ | $\hat{S}_i = \frac{\hbar}{2}\sigma_i$ | 命题 SPIN（🔷） |
| 纠缠 | A7 跨子系统循环 | $S_A > 0$ | 命题 ENT（🔷） |
| 费米统计 | $P_{ij} = -I$，$n_k \in \{0,1\}$ | 费米-狄拉克分布 | 命题 PAULI（🔷） |
| Dirac 方程 | $(i\gamma^\mu\Delta_\mu - m_0)\psi = 0$ | $(i\gamma^\mu\partial_\mu - m)\psi = 0$ | 定理 CLIFF + 命题 WEYL（🔷） |

**兼容性验证**：

- (I)+(III)：Hilbert 空间上的薛定谔方程是标准量子力学的核心。
- (II)+(III)：Born 规则与薛定谔方程兼容（幺正演化保持概率归一化）。
- (III)+(IV)：薛定谔方程与路径积分等价（标准结果）。
- (V)+(VIII)：退相干控制纠缠寿命。
- (VI)+(VII)：不确定性原理与自旋兼容。
- (IX)+(X)：费米统计与 Dirac 方程兼容（旋量的交换反对称性）。
- (III)+(IX)：多粒子薛定谔方程 $i\hbar\partial_t\Psi = \hat{H}_{	ext{total}}\Psi$ 在全同费米子情形下，$\hat{H}_{	ext{total}}$ 与交换算符 $P_{ij}$ 对易（哈密顿量不区分全同粒子），因此反对称子空间 $\mathcal{H}_-$ 是 $\hat{H}_{	ext{total}}$ 的不变子空间——薛定谔方程在反对称子空间内封闭演化。这是自旋-统计定理的非相对论版本，在离散框架中由命题 PAULI 和命题 SE 联合保证。
- (IX)+(X) 的延伸：Dirac 方程（旋量场）+ 费米统计（交换反对称性）联合给出费米子场的完整量子场论框架，对应自旋-统计定理的相对论版本。在 WorldBase 中，此对应由命题 SPIN、命题 PAULI 和命题 WEYL 联合保证。
- (I)+(II)+(III)+(V)+(VI)：量子力学的五公理（von Neumann 1932）全部涌现。

### 8.17.8 与 CL/CLEM/WLEM/FE 的平行结构

| 定理 | 对应涌现 | 极限类型 | 收敛速率 | 状态 |
|:---|:---|:---|:---|:---:|
| CL | 引力势（泊松方程） | $L^2_{	ext{loc}}$ 积分核 | $O(\epsilon_N^\alpha)$ | ✅ |
| CLEM | Maxwell 方程 | 逐点 $C^0$ | $O(\epsilon_N)$ | ✅（单向） |
| WLEM | 弱力手征结构 + 质量 | 离散代数 $	o$ 连续规范 | 离散精确 | 🔷 |
| FE | Einstein 场方程（含 $\Lambda$） | $L^2_{	ext{loc}}$ | $O(\epsilon_N)$ | 🔷 |
| QLEM | 完整量子力学 | Trotter 乘积 | $O(\alpha)$ | 🔷 |

QLEM 的特殊性在于它不是单一连续极限定理，而是十个子结构的联合涌现定理。所有子结构共享相同的公理来源（A1–A9）和相同的连续极限参数。

### 8.17.9 五种涌现的完整统一

$$\underbrace{A1	ext{–}A9}_{	ext{十条公理}} \xrightarrow{	ext{WorldBase}} \begin{cases} 	ext{广义相对论（GR）} & 	ext{定理 D + G + CL + CL-T + FE（含 }\Lambda\text{）} \\ 	ext{电磁力} & 	ext{定理 CLEM} \\ 	ext{弱力} & 	ext{定理 WLEM} \\ 	ext{强力} & 	ext{定理 S + CONF} \\ 	ext{量子力学} & 	ext{定理 QLEM} \end{cases}$$

五种涌现共享同一个离散差异空间 $\{0,1\}^N$ 和同一套公理 A1–A9，不同相互作用是同一离散结构在不同物理截面上的投影：

| 物理结构 | 主导公理 | 离散原型 | 连续理论 |
|:---|:---|:---|:---|
| 广义相对论 | A1 + A1' + A4 + A5 + A8 + A9 | 汉明势场 + 三维嵌入 + A8 真空能 | Einstein 场方程（含 $\Lambda$） |
| 电磁力 | A1' + A4 + A7 | 横向相位 + 离散外微分 | Maxwell 方程 |
| 弱力 | A6 + A9 | DAG 非厄米 + $V$-$A$ 锁定 | $SU(2)_L$ 规范理论 |
| 强力 | A8 + A4 + A9 | 中截面变易 + $\mathfrak{su}(3)$ | QCD 禁闭 |
| 量子力学 | A1' + A7 + A6 + A8 + A9 | 循环相干 + 退相干控制 | 标准 QM 全部核心结构 |

### 8.17.10 状态边界

| 命题 | 状态 | 说明 |
|:---|:---:|:---|
| 离散作用量 $S_N[\gamma]$ 的定义 | ✅ | A8 约束度 + $m_0$ + $\alpha$，量纲验证完整 |
| 路径权重 $\mathcal{W}_N = e^{iS_N/\hbar}$ | 🔷 | A1' 相位 + 离散作用量 |
| Trotter 乘积收敛（定理 QLEM-1） | 🔷（有限 $N$ 下 ✅） | $O(\alpha)$ Trotter 误差；无限维极限依赖 §8.3.4 ⬜ |
| Wick 转动公理来源（定理 QLEM-2） | 🔷（有限 $N$ 下 ✅） | A5 谱上界 + A6 谱下界；无限维极限依赖 §8.3.4 ⬜ |
| Born 规则连续极限（定理 QLEM-3） | 🔷 | A9 离散非上下文性 + $L^2$ 收敛框架 ⬜ |
| QLEM 主定理（十个子结构联合涌现） | 🔷 | 兼容性验证完整；依赖 QLEM-1/2/3 的 🔷 状态 |
| 连续泛函测度 $\mathcal{D}x(t)$ 的严格构造 | 🔶 | 依赖泛函分析标准工具（Wiener 测度/白噪声分析） |
| 无限维 Hilbert 空间完备性 | ⬜ | $L^2$ 收敛论证待补（§8.3.4） |
| 连续极限下 $\hbar$ 的精确值 | 🔶 | 依赖 $m_0$ 和 $\alpha$ 的物理确定（OPEN-06） |

---

## 8.18 当前步骤状态汇总

| 步骤 | 内容 | 状态 | 说明 |
|:---|:---|:---:|:---|
| 1.1 | 基底构造 | 🔷 | A2 二元性直接给出 |
| 1.2 | 内积定义 | 🔷 | A8 正定性 + A1′ 共轭对称性 + A5 归一化，三步严格 |
| 1.3 | 复数结构 | 🔷 | A1′ + A9，$\mathbb{C}$ 最小域 |
| 1.4 | 完备性（$N 	o \infty$） | ⬜ | $L^2$ 收敛论证待补，三阶段路线图已制定 |
| 引理 5.0 | 基底态权重独立性 | 🔷 | A8 + A1，支撑 Born 规则无循环 |
| 2a | Born 规则（基底态） | 🔷 | A8 + A9，引理 5.0 支撑，无循环 |
| 2b | Born 规则（叠加态） | 🔶 | Gleason 非上下文性连续极限待验证 |
| 桥接定理 | 经典概率 vs 量子概率 | 🔷 | A1′ 相位产生干涉项，$P_{	ext{cl}}$ 基底依赖性已标注 |
| 3 | 薛定谔方程（连续极限） | 🔷 | A7 + A5 + A1′ + A4，幺正性论证完整 |
| 3.4 | 离散哈密顿量显式验证 | 🔷 | $N=2$ 最小实例完成；一般情形由实对称矩阵保证 |
| 4 | 路径积分 | ⬜ | A4 + A6 + A7 给出骨架，极限未完成 |
| 5a | 退相干（单次转移） | 🔷 | 情形 (a) $f=0$（基底正交性），情形 (b) $f=1$，精确结果 |
| 5b | 退相干速率连续极限 | 🔷 | $\Gamma_{	ext{eff}} = 
u_{	ext{coupling}}$，弱耦合正则化模型 |
| 5c | Lindblad 方程离散原型（定理 DM） | 🔷 | A6 非幺正转移 $	o$ Kraus 完备性 $	o$ 弱耦合主方程；连续极限 🔶 |
| 6a | 不确定性原理（位置–动量） | 🔷 | A6 vs A7 + A1′，$1/2$ 来自 Cauchy-Schwarz |
| 6b | $[\hat{x},\hat{p}]=i\hbar$ 系数验证 | 🔷 | 连续极限下严格，有限 $N$ 修正 $O(\epsilon_N^2)$，系数 1 由 A4 锁定 |
| 6c | $[\hat{W},\hat{H}]=0$ 条件 | 🔶 | 依赖维度定理连续极限 + $S_N 	o O(3)$ 涌现严格化 |
| — | 泡利不相容与费米统计离散原型 | 🔷 | 命题 PAULI（§8.9），连续极限依赖 QLEM（🔶） |
| — | 量子化条件 | ✅ | A7 + A5 + A1′，离散框架内闭合 |
| — | 叠加原理 | 🔶 | A2 + A1′ + A7，严格连续极限未完成 |
| — | 自旋 | 🔷 | 命题 SPIN（§8.13），$\mathfrak{su}(2)$ 双覆盖完整 |
| — | 纠缠（多体关联） | 🔷 | 命题 ENT（§8.14），A7 跨子系统循环强制 $S_A>0$ |
| — | Dirac 方程 | 🔷 | 定理 CLIFF + 命题 WEYL（§8.16），连续偏微分形式 🔶 |
| — | QLEM 主定理（离散→连续量子桥梁） | 🔷 | 十个子结构联合涌现；泛函测度构造 🔶；无限维完备性 ⬜ |

---

## 8.19 本部分参考文献

**量子力学奠基**

Dirac, P. A. M. (1930). *The Principles of Quantum Mechanics*. Oxford University Press. （量子力学公理化框架的奠基性著作）

von Neumann, J. (1932). *Mathematische Grundlagen der Quantenmechanik*. Springer. （量子力学数学基础；Hilbert 空间框架；测量理论）

Schrödinger, E. (1926). An undulatory theory of the mechanics of atoms and molecules. *Physical Review*, 28(6), 1049–1070. （薛定谔方程原始文献）

Heisenberg, W. (1927). Über den anschaulichen Inhalt der quantentheoretischen Kinematik und Mechanik. *Zeitschrift für Physik*, 43(3–4), 172–198. （不确定性原理原始文献）

**Born 规则与测量理论**

Gleason, A. M. (1957). Measures on the closed subspaces of a Hilbert space. *Journal of Mathematics and Mechanics*, 6(6), 885–893. （Born 规则推导的数学基础；本文引理 5.0 保证非上下文性前提的无循环建立）

Bub, J. (1999). *Interpreting the Quantum World*. Cambridge University Press. （Gleason 定理与非上下文性的物理诠释）

**退相干与开放量子系统**

Lindblad, G. (1976). On the generators of quantum dynamical semigroups. *Communications in Mathematical Physics*, 48(2), 119–130. （Lindblad 方程；本文 §8.7.6 的连续极限目标）

Kraus, K. (1983). *States, Effects, and Operations: Fundamental Notions of Quantum Theory*. Springer. （Kraus 算符表示；完全正映射；本文 §8.7.6.3 的数学基础）

Zurek, W. H. (2003). Decoherence, einselection, and the quantum origins of the classical. *Reviews of Modern Physics*, 75(3), 715–775. （退相干与经典性涌现；本文命题 M-2/M-3 的离散对应）

**路径积分**

Feynman, R. P., & Hibbs, A. R. (1965). *Quantum Mechanics and Path Integrals*. McGraw-Hill. （路径积分标准框架；本文 §8.6 的连续极限目标）

Trotter, H. F. (1959). On the product of semi-groups of operators. *Proceedings of the American Mathematical Society*, 10(4), 545–551. （Trotter 乘积公式；本文定理 QLEM-1 的数学基础）

Osterwalder, K., & Schrader, R. (1973). Axioms for Euclidean Green's functions. *Communications in Mathematical Physics*, 31(2), 83–112. （OS 公理；Wick 转动的严格数学基础；本文 §8.17.5 注记的背景）

**自旋与统计**

Pauli, W. (1925). Über den Zusammenhang des Abschlusses der Elektronengruppen im Atom mit der Komplexstruktur der Spektren. *Zeitschrift für Physik*, 31(1), 765–783. （泡利不相容原理原始文献）

Fermi, E. (1926). Zur Quantelung des idealen einatomigen Gases. *Zeitschrift für Physik*, 36(11–12), 902–912. （费米-狄拉克统计原始文献）

Dirac, P. A. M. (1926). On the theory of quantum mechanics. *Proceedings of the Royal Society A*, 112(762), 661–677. （费米-狄拉克统计原始文献）

Dirac, P. A. M. (1928). The quantum theory of the electron. *Proceedings of the Royal Society A*, 117(778), 610–624. （Dirac 方程原始文献）

Bargmann, V. (1954). On unitary ray representations of continuous groups. *Annals of Mathematics*, 59(1), 1–46. （$SO(3)$ 射影表示与 $SU(2)$ 双覆盖；本文 §8.13.2 的数学基础）

**纠缠**

Bell, J. S. (1964). On the Einstein Podolsky Rosen paradox. *Physics*, 1(3), 195–200. （Bell 不等式；纠缠非定域性的实验判据；本文命题 ENT 的物理背景）

**格点量子力学**

Kogut, J., & Susskind, L. (1975). Hamiltonian formulation of Wilson's lattice gauge theories. *Physical Review D*, 11(2), 395–408. （格点对易子 $O(\epsilon^2)$ 修正；本文 §8.15.2 的格点框架背景）

**WorldBase 框架内部引用**

GR-01：WorldBase 框架第一部分（方法论与差异本体论）

GR-03：WorldBase 框架第三部分（维度约束与引力势的必然性；定理 D，$D_{	ext{eff}}=3$）

CL-01：WorldBase 框架第四部分（连续极限定理 CL；双尺度条件；Trotter 误差框架）

QCD-01：WorldBase 框架第五部分（中截面变易代数与强相互作用；$\mathfrak{su}(3)$ 闭合）

EW-01：WorldBase 框架第六部分（DAG 非厄米性与弱力手征结构；定理 W-2，$\mathfrak{su}(2)$ 闭合；命题 SPIN 的锚点）

EM-01：WorldBase 框架第七部分（横向平面、离散外微分与电磁规范结构；A1' 横向自由度）

---

*第八部分完*

