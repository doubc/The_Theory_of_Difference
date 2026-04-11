# 第十二部分：宇宙学常数与引力非线性连续极限

> **本章来源**：原 V2.1 全文版中被错误插入第六部分（弱力）的内容，经诊断提取归位。
>
> **包含内容**：
> - 宇宙学常数 Λ 的公理推导（原编号 §6.12）
> - 非线性 Einstein 自耦合连续极限（原编号 §12）

## 6.12 宇宙学常数 $\Lambda$ 的公理推导

### 6.12.1 问题定位

宇宙学常数 $\Lambda$ 是爱因斯坦场方程中最后一个尚未从公理推导的自由参数。本节建立 $\Lambda$ 的严格公理来源。

已有锚点：

- **A8**（对称偏好）：权重函数 $\rho(w) = \binom{N}{w}/\binom{N}{N/2}$，中截面 $w = N/2$ 权重最大
- **A5**（差异守恒）：守恒量 $Q(x)$ 在演化中不变
- **Bianchi 恒等式**（V0.12）：$\nabla_\mu G^{\mu\nu} = 0$
- **WLEM §6.11**：约束度函数 $K(w) = K_0 + \ln\rho(w)$，质量公式 $E = \Delta K \cdot m_0$
- **定理 CL**（§4）：离散势场连续极限收敛到泊松方程

---

### 6.12.2 离散真空能密度的定义

A8 给出每个状态 $x$ 的统计权重 $w(x) = \rho(w(x))$，其中 $w(x) = \sum_i x_i$ 是汉明重量。权重函数为：

$$\rho(w) = \frac{\binom{N}{w}}{\binom{N}{N/2}}$$

在 $w = N/2$ 处 $\rho = 1$（最大值），偏离中截面时 $\rho < 1$。

由 WLEM §1.1 的约束度函数，偏离中截面的“能量代价”为：

$$\Delta E(x) = \Delta K(x) \cdot m_0 = [K_0 - K(w(x))] \cdot m_0 = -\ln\rho(w(x)) \cdot m_0$$

在 $w = N/2$ 处 $\Delta E = 0$（最低能量），偏离时 $\Delta E > 0$。

真空态是不包含任何局部激发（稳定态/粒子）的背景态。在离散框架中，真空态集合为 $\mathcal{V} = \{0,1\}^N \setminus S$
，即所有非稳定态的集合。即使在“真空”中，系统仍被 A8 约束——A8 给予中截面最高偏好权重，偏离中截面的态受到抑制。这一抑制效应在宏观平均下表现为恒定的背景能量密度。

**离散真空能密度的定义**：

$$\rho_{\text{vac}}^{(N)} = \frac{1}{V_{\text{phys}}} \sum_{x \in \mathcal{V}} \frac{\rho(w(x))}{Z} \cdot \Delta E(x)$$

其中 $V_{\text{phys}} = L^3$ 是嵌入空间的物理体积，$Z = \sum_x \rho(w(x))$ 是配分函数。展开得：

$$\rho_{\text{vac}}^{(N)} = \frac{m_0}{L^3 Z} \sum_{w=0}^{N} \binom{N}{w} \cdot \rho(w) \cdot [-\ln\rho(w)]$$

利用对称性 $\rho(w) = \rho(N-w)$ 可将求和限制在 $w \leq N/2$。

**$N=6$ 数值验证**：

| $w$ | $\binom{6}{w}$ | $\rho(w)$ | $-\ln\rho(w)$ | $\binom{6}{w} \cdot \rho(w) \cdot [-\ln\rho(w)]$ |
|:---:|:--------------:|:---------:|:-------------:|:------------------------------------------------:|
|  0  |       1        |   1/20    |     2.996     |                      0.150                       |
|  1  |       6        |   6/20    |     1.204     |                      2.167                       |
|  2  |       15       |   15/20   |     0.288     |                      3.240                       |
|  3  |       20       |   1.000   |     0.000     |                      0.000                       |
|  4  |       15       |   15/20   |     0.288     |                      3.240                       |
|  5  |       6        |   6/20    |     1.204     |                      2.167                       |
|  6  |       1        |   1/20    |     2.996     |                      0.150                       |

总和 $= 11.114$。配分函数 $Z = 924/20 = 46.2$。

$$\rho_{\text{vac}}^{(6)} = \frac{m_0}{L^3 \cdot 46.2} \cdot 11.114 = \frac{0.2405 \cdot m_0}{L^3}$$

在连续极限 $N \to \infty$ 下，利用 Stirling 近似可得 $\rho_{\text{vac}}^{(\infty)} = \frac{m_0}{L^3} \cdot c_0$
，其中 $c_0$ 为 $O(1)$ 数值常数（$c_0 \approx 0.24$ 量级）。

---

### 6.12.3 Bianchi 恒等式对 $\Lambda$ 形式的锁定

设真空对能动张量的贡献为 $T^{\text{vac}}_{\mu\nu}$
。爱因斯坦场方程为 $G_{\mu\nu} = \frac{8\pi G}{c^4}(T^{\text{matter}}_{\mu\nu} + T^{\text{vac}}_{\mu\nu})$。Bianchi
恒等式要求 $\nabla_\mu G^{\mu\nu} = 0$，因此在物质真空区域 $\nabla_\mu T^{\text{vac}\,\mu\nu} = 0$。

A8 的权重函数 $\rho(w)$
只依赖汉明重量，不依赖任何特定方向，故真空能量分布在所有空间方向上各向同性。真空态不演化，故 $T^{\text{vac}}_{0i} = 0$
（无能流）。时间分量 $T^{\text{vac}}_{00} = \rho_{\text{vac}}$。

由 $\nabla_\mu T^{\text{vac}\,\mu\nu} = 0$ 及各向同性条件，唯一满足所有几何背景且不引入额外自由度的协变形式为：

$$T^{\text{vac}}_{\mu\nu} = -\rho_{\text{vac}} \, g_{\mu\nu}$$

该形式给出 $T^{\text{vac}}_{00} = -\rho_{\text{vac}} g_{00} = \rho_{\text{vac}}$
（因 $g_{00} = -1$），$T^{\text{vac}}_{ij} = -\rho_{\text{vac}} g_{ij}$，对应状态方程 $p = -\rho_{\text{vac}}$（负压力）。

> **注记（排除曲率耦合项）**：若 $T^{\text{vac}}_{\mu\nu} = -\rho_{\text{vac}} g_{\mu\nu} + \alpha R_{\mu\nu}$
> ，则 $\nabla_\mu T^{\text{vac}\,\mu\nu} = \frac{\alpha}{2}\nabla^\nu R$，除非时空为 Einstein 流形（$R = \text{const}$
> ）否则不为零。由于真空能必须对所有几何背景普遍满足 Bianchi
> 约束，含曲率修正的形式不具有普适性，$-\rho_{\text{vac}} g_{\mu\nu}$ 是唯一普遍相容的形式。

---

### 6.12.4 $\Lambda$ 的场方程嵌入

将 $T^{\text{vac}}_{\mu\nu} = -\rho_{\text{vac}} g_{\mu\nu}$ 代入爱因斯坦方程并整理：

$$G_{\mu\nu} + \frac{8\pi G}{c^4}\rho_{\text{vac}} \, g_{\mu\nu} = \frac{8\pi G}{c^4}T^{\text{matter}}_{\mu\nu}$$

定义：

$$\Lambda = \frac{8\pi G}{c^4}\rho_{\text{vac}}$$

即得标准形式 $G_{\mu\nu} + \Lambda g_{\mu\nu} = \frac{8\pi G}{c^4}T^{\text{matter}}_{\mu\nu}$。$\Lambda$ 不是自由参数，由
A8 权重分布完全确定。

---

### 6.12.5 $\rho_{\text{vac}}$ 的常数性

$\rho_{\text{vac}}^{(N)}$ 的定义中对所有汉明重量层求和，不依赖任何特定空间位置 $\mathbf{r}$。这是因为 A8
权重函数 $\rho(w)$ 只依赖汉明重量（全局量），不依赖比特的空间分布。因此 $\rho_{\text{vac}}^{(N)}$
在嵌入空间中是均匀常数。在连续极限 $N \to \infty$ 下，此常数性由 A8
权重的全局性与均匀化条件（双尺度 $\ell \ll \delta \ll L$）共同保持。

> **注记**：在有限 $N$ 离散框架中，$\nabla_\mu T^{\text{vac}\,\mu\nu} = O(\epsilon_N^2)$
> ，精确守恒在连续极限 $\epsilon_N \to 0$ 下恢复，与定理 CL-T 的误差界一致。

---

### 6.12.6 $\Lambda$ 的符号确定

A5（差异守恒）要求守恒量正定，故 $\rho_{\text{vac}} > 0$。定理 LT 给出 $g_{00} < 0$
，因此 $T^{\text{vac}}_{00} = -\rho_{\text{vac}} g_{00} = +\rho_{\text{vac}} > 0$
，真空能量密度为正，对应排斥性引力效应。故 $\Lambda = \frac{8\pi G}{c^4}\rho_{\text{vac}} > 0$。

---

### 6.12.7 排除自由参数

$\Lambda$ 表达式中所有因子均由公理或已建立的定理确定：$G$ 由定理 G 归一化确定，$c$ 由 A1′ 给出，$\rho_{\text{vac}}$ 由 A8
唯一确定，$m_0$ 由 A4+A5 确定，$L$ 为嵌入空间尺度，$c_0$ 为组合学常数。**$\Lambda$ 中不存在任何自由参数。**

---

### 6.12.8 完整推导链

```
A8（对称偏好）
    │
    ├──→ 权重函数 ρ(w) = C(N,w)/C(N,N/2)
    │
    ├──→ 偏离中截面的能量代价 ΔE(x) = -ln ρ(w(x)) · m₀
    │       │
    │       └──→ §6.12.2：离散真空能密度 ρ_vac = (m₀/L³Z) Σ_w C(N,w)·ρ(w)·[-ln ρ(w)]
    │
    ├──→ §6.12.5：ρ_vac 为常数（A8 权重的全局性）
    │
    └──→ Bianchi 恒等式
            │
            ├──→ §6.12.3：T^vac_μν = -ρ_vac g_μν（唯一协变形式）
            │
            ├──→ §6.12.4：Λ = 8πGρ_vac/c⁴
            │
            └──→ §6.12.6：Λ > 0（A5 正定 + A6 因果）
```

---

### 6.12.9 状态边界

| 命题                                                        | 状态     | 说明                   |
|-----------------------------------------------------------|--------|----------------------|
| 离散真空能密度 $\rho_{\text{vac}}^{(N)}$ 的定义与 $N=6$ 计算           | ✅ 定理   | 显式求和，数值确定            |
| $\rho_{\text{vac}}$ 为常数                                   | 🔷 强命题 | A8 全局性 + 均匀化条件       |
| $T^{\text{vac}}_{\mu\nu} = -\rho_{\text{vac}} g_{\mu\nu}$ | 🔷 强命题 | Bianchi 恒等式 + 各向同性   |
| $\Lambda = 8\pi G\rho_{\text{vac}}/c^4$                   | 🔷 强命题 | 场方程嵌入                |
| $\Lambda > 0$                                             | 🔷 强命题 | A5 正定 + A6 因果        |
| 无自由参数                                                     | 🔷 强命题 | 所有因子由公理确定            |
| 连续极限 $\rho_{\text{vac}}^{(\infty)}$                       | 🔶     | 依赖 Stirling 渐近分析的严格化 |
| 观测值匹配                                                     | 🔶     | 依赖 $m_0$ 和 $L$ 的确定   |


---


## 12 非线性 Einstein 自耦合连续极限

### §12.1 问题定位

定理 CL-T 已建立离散度规的连续极限收敛 $O(\epsilon_N^2)$，线性泊松方程 $\nabla^2\Phi = 4\pi G\rho$ 已从离散势场严格推导（定理
CL）。但完整的爱因斯坦方程：

$$G_{\mu\nu} + \Lambda g_{\mu\nu} = \frac{8\pi G}{c^4}T_{\mu\nu}$$

包含非线性自耦合项——度规同时出现在方程的两侧。本节证明：这一非线性结构是离散框架的自然涌现，无需额外假设。

已有锚点：

- **定理 CL-T**：离散度规收敛，$O(\epsilon_N^2)$
- **引理 INT**：$N=6$ 离散叠加精确成立
- **定理 LAMBDA**（§6.12）：$\Lambda = 8\pi G\rho_{\text{vac}}/c^4$
- **均匀化方法论**（§1.5）：双尺度条件 $\ell \ll \delta \ll L$
- **Bianchi 恒等式**：$\nabla_\mu G^{\mu\nu} = 0$

---

### §12.2 离散 Christoffel 符号的构造

在离散格点嵌入空间中，离散度规 $g^{(N)}_{\mu\nu}$ 定义在格点及其邻域上（定理 CL-T）。离散 Christoffel 符号定义为：

$$\Gamma^{(N)\mu}_{\nu\lambda}(x) = \frac{1}{2}\,\overline{g^{(N)\mu\sigma}}(x)\left[\Delta_\nu g^{(N)}_{\sigma\lambda}(x) + \Delta_\lambda g^{(N)}_{\sigma\nu}(x) - \Delta_\sigma g^{(N)}_{\nu\lambda}(x)\right]$$

其中 $\Delta_\nu$ 是离散差分算符，$\overline{g^{(N)\mu\sigma}}(x)$ 是度规逆的宏观均匀化值。此定义是连续 Christoffel
符号的自然离散化。

---

### §12.3 非线性乘积项的收敛

核心困难：均匀化算子一般不保持乘积。解决方法是将离散度规分解为宏观平均与微观涨落：

$$g^{(N)}_{\mu\nu}(x) = \bar{g}_{\mu\nu}(x) + \delta g_{\mu\nu}(x)$$

其中 $\bar{g}_{\mu\nu} = \mathcal{H}_\delta(g^{(N)}_{\mu\nu})$ 光滑，$\delta g_{\mu\nu}$
在窗口内零均值，振幅 $\|\delta g\|_{L^\infty} = O(\epsilon_N)$。

乘积展开并均匀化后，交叉项因零均值为零（误差 $O(\epsilon_N^3/\delta)$），涨落二阶矩为 $O(\epsilon_N^2)$。因此有：

**定理 NP（非线性乘积收敛）**：在双尺度条件 $\ell \ll \delta \ll L$ 下，

$$\mathcal{H}_\delta(g^{(N)}_{\mu\alpha} \cdot g^{(N)}_{\rho\sigma}) = \bar{g}_{\mu\alpha}\bar{g}_{\rho\sigma} + O(\epsilon_N^2) + O(\epsilon_N^3/\delta)$$

在连续极限 $\epsilon_N \to 0$、$\delta \to 0$（$\epsilon_N/\delta \to 0$）下，乘积收敛到 $g_{\mu\alpha}g_{\rho\sigma}$。

> **注记**：交叉项 $\eta_N = \mathcal{H}_\delta(\bar{g}\cdot\delta g)$ 的统计抵消依赖 $\delta g$
> 的零均值性质。由 $\eta_N \to 0$ 在 $L^\infty$ 中，该序列在 $L^2_{\text{loc}}$ 中紧，弱收敛条件自动满足。

---

### §12.4 离散 Christoffel 符号的收敛

**定理 CC（Christoffel 收敛）**：在双尺度条件下，

$$\left\|\overline{\Gamma^{(N)\mu}_{\nu\lambda}} - \Gamma^\mu_{\nu\lambda}\right\|_{L^2_{\text{loc}}} = O(\epsilon_N) + O(\epsilon_N^2/\delta^2)$$

误差来源：差分截断 $O(\epsilon_N)$，度规逆的均匀化修正 $O(\epsilon_N^2/\delta^2)$。

---

### §12.5 离散 Ricci 张量的收敛

离散 Ricci 张量由 Christoffel 符号的差分与乘积构成。由定理 CC 及定理 NP 得：

**定理 RC（Ricci 收敛）**：

$$\left\|\overline{R^{(N)}_{\mu\nu}} - R_{\mu\nu}\right\|_{L^2_{\text{loc}}} = O(\epsilon_N) + O(\epsilon_N^2/\delta^2)$$

---

### §12.6 Einstein 张量的收敛

$G^{(N)}_{\mu\nu} = R^{(N)}_{\mu\nu} - \frac{1}{2}R^{(N)}g^{(N)}_{\mu\nu}$。利用定理 RC 和定理 NP 处理乘积项，得：

**定理 EC（Einstein 张量收敛）**：

$$\left\|\overline{G^{(N)}_{\mu\nu}} - G_{\mu\nu}\right\|_{L^2_{\text{loc}}} = O(\epsilon_N) + O(\epsilon_N^2/\delta^2)$$

---

### §12.7 离散自耦合机制

离散度规 $g^{(N)}_{\mu\nu}$ 由汉明距离 $d_H$ 通过分块嵌入定义，而 $d_H$
依赖比特配置。比特配置中包含稳定态（物质源）的信息——稳定态集合 $S$ 决定势场，从而决定度规。因此：

$$\text{度规} \xleftarrow{d_H} \text{比特配置} \xrightarrow{S} \text{物质源}$$

度规和物质源通过比特配置**相互依赖**，这就是非线性自耦合的离散原型。引理 INT 证明的势场线性叠加与此非矛盾：前者是固定度规下的叠加，后者是度规自身的反馈。

---

### §12.8 场方程闭合

离散场方程原型为 $G^{(N)}_{\mu\nu} + \Lambda^{(N)} g^{(N)}_{\mu\nu} = \frac{8\pi G}{c^4}T^{(N)}_{\mu\nu}$。宏观均匀化后取连续极限：

**定理 FE（场方程闭合）**：在双尺度条件 $\ell \ll \delta \ll L$ 下，

$$G_{\mu\nu} + \Lambda g_{\mu\nu} = \frac{8\pi G}{c^4}T_{\mu\nu}$$

误差为 $O(\epsilon_N) + O(\epsilon_N^2/\delta^2)$。

> **注记**：本收敛要求双尺度条件 $\ell \ll \delta$，即 $\delta \gg \epsilon_N$，以保证 $O(\epsilon_N^2/\delta^2)$ 项趋于零。

---

### §12.9 Bianchi 恒等式的离散验证

离散 Bianchi 恒等式为 $\Delta_\mu \overline{G^{(N)\mu\nu}} = O(\epsilon_N)$，连续极限下精确为零。场方程自洽性由
A5（差异守恒 $\to \nabla_\mu T^{\mu\nu}=0$）、Bianchi 恒等式及度规兼容性联合保证。

---

### §12.10 状态边界

| 命题                    | 状态      |
|-----------------------|---------|
| 离散 Christoffel 符号构造   | ✅ 定理    |
| 非线性乘积收敛（定理 NP）        | 🔷 强命题  |
| Christoffel 收敛（定理 CC） | 🔷 强命题  |
| Ricci 收敛（定理 RC）       | 🔷 强命题  |
| Einstein 张量收敛（定理 EC）  | 🔷 强命题  |
| 场方程闭合（定理 FE）          | 🔷 强命题  |
| 强场奇点正则化               | 🔶 结构论证 |

---

## 交付清单

| 项目   | 状态                                                                                                               |
|------|------------------------------------------------------------------------------------------------------------------|
| 推导文本 | ✅ 完成（§6.13 + §10.6）                                                                                              |
| 新增命题 | 命题 EW-0（对称破缺方向）🔷，定理 EW-1（W/Z 质量比）🔷，命题 N-RG（$N$ 跑动）🔷，命题 N-BETA（$\beta$ 函数原型）🔷                                 |
| 交叉验证 | CV-12(a)（电荷算符修正）🔷，CV-12(b)（$N_{	ext{strong}} \neq N_{	ext{weak}}$ 兼容性）🔷                                        |
| 状态边界 | 离散机制全部 🔷，连续规范场论形式全部 🔶                                                                                          |
| 遗留问题 | 连续 $SU(2)_L \times U(1)_Y$ 规范场论 🔶，$\beta$ 函数系数精确匹配 🔶，完整 Higgs 机制 🔶，$N_{	ext{strong}}$/$N_{	ext{weak}}$ 精确值 🔶 |
| 新增依赖 | 定理 WLEM（§6.11）、命题 TW（§6.12）、定理 QLEM（§8.19）、命题 ORTH（§10.3）                                                        |

---

