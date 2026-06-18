# 02-worldbase 连续极限严格化：诊断报告与修正路线图

## 一、核心发现

通过严格计算，发现原始 `04-continuous-limit.md` 中 **引理 CL-0 的 η_N 表达式存在代数错误**，导致后续整个"离散→连续"桥梁的地基不稳。

---

## 二、错误定位

### 引理 CL-0 的原始陈述

> 对任意 $x, y \in \{0,1\}^N$，设 $\mathbf{u} = \iota_\varepsilon(x)$，$\mathbf{v} = \iota_\varepsilon(y)$，则：
> $$d_H(x,y) = \frac{n}{L^2}|\mathbf{u} - \mathbf{v}|^2 + \eta_N(x,y)$$
> 其中 $\eta_N(x,y) = -2\sum_{k=1}^{3}\sum_{\substack{i < j \\ i,j \in G_k}}(x_i - y_i)(x_j - y_j)$

### 严格重推

设 $a_i = x_i - y_i$，$W_k = \sum_{i \in G_k} a_i$，$D = \sum_i a_i^2 = d_H(x,y)$。

**Step 1：** 展开 $|\mathbf{u}-\mathbf{v}|^2$：
$$|\mathbf{u}-\mathbf{v}|^2 = \varepsilon^2 \sum_{k=1}^3 W_k^2 = \frac{L^2}{n^2}\sum_{k=1}^3 W_k^2$$

**Step 2：** 计算 $\frac{n}{L^2}|\mathbf{u}-\mathbf{v}|^2$：
$$\frac{n}{L^2}|\mathbf{u}-\mathbf{v}|^2 = \frac{1}{n}\sum_{k=1}^3 W_k^2$$

**Step 3：** 展开 $W_k^2$：
$$W_k^2 = \left(\sum_{i \in G_k} a_i\right)^2 = \sum_{i \in G_k} a_i^2 + 2\sum_{\substack{i < j \\ i,j \in G_k}} a_i a_j$$

**Step 4：** 对 $k$ 求和：
$$\sum_{k=1}^3 W_k^2 = D + 2\sum_{k=1}^3 \sum_{\substack{i < j \\ i,j \in G_k}} a_i a_j$$

**Step 5：** 因此：
$$\frac{n}{L^2}|\mathbf{u}-\mathbf{v}|^2 = \frac{D}{n} + \frac{2}{n}\sum_{k=1}^3 \sum_{\substack{i < j \\ i,j \in G_k}} a_i a_j$$

**Step 6：** 计算 $d_H - \frac{n}{L^2}|\mathbf{u}-\mathbf{v}|^2$：
$$d_H - \frac{n}{L^2}|\mathbf{u}-\mathbf{v}|^2 = D - \frac{D}{n} - \frac{2}{n}\sum_{k=1}^3 \sum_{\substack{i < j \\ i,j \in G_k}} a_i a_j$$

$$= \frac{n-1}{n}\,D - \frac{2}{n}\sum_{k=1}^3 \sum_{\substack{i < j \\ i,j \in G_k}} a_i a_j$$

### 结论

正确的 $\eta_N$ 应为：

$$\boxed{\eta_N^{\text{correct}} = \frac{n-1}{n}\,d_H(x,y) - \frac{2}{n}\sum_{k=1}^3 \sum_{\substack{i < j \\ i,j \in G_k}} (x_i - y_i)(x_j - y_j)}$$

**而非**原始声称的 $\eta_N = -2\sum_k \sum_{i<j} a_i a_j$。

---

## 三、错误的影响

### 3.1 η_N 不是小量

原始文档 §4.3.2 声称：
> "$\eta_N$ 的统计平均为零...宏观平均后交叉项相互抵消"

实际上，$\eta_N^{\text{correct}}$ 包含主项 $\frac{n-1}{n}\,d_H$，其量级为 $O(N)$，**不可忽略**。

### 3.2 嵌入映射的信息损失

**反例：** $N = 6$，$n = 2$，取 $x = (1,0,1,0,1,0)$，$y = (0,1,0,1,0,1)$。
- $d_H(x,y) = 6$
- $W_1 = W_2 = W_3 = 0$（每个块内 $a_i$ 之和为零）
- $|\mathbf{u}-\mathbf{v}|^2 = 0$
- $\frac{n}{L^2}|\mathbf{u}-\mathbf{v}|^2 = 0$

嵌入后的距离为零，但汉明距离为 $N$。嵌入 $\iota_\varepsilon$ **不是单射**，丢失了块内的精细结构。

### 3.3 级联效应

以下依赖引理 CL-0 的结果均需重新审查：
- **引理 CL-1**（宏观平均势的收敛）：收敛论证依赖 $\eta_N$ 可忽略
- **定理 CL**（§4.8）：完整陈述中的误差估计依赖上述引理
- **§4.10**（有限格点度规）：连续极限依赖定理 CL
- **§4.11**（Lorentz 变换涌现）：引理 LT-2/LT-5 依赖定理 CL

---

## 四、修正路线图

### 方案 A：离散位势论路径（推荐）

**核心思想：** 不通过分块嵌入建立"汉明距离 ≈ 欧氏距离"的桥梁，而是直接在 $\{0,1\}^N$ 上使用 Fourier-Walsh 分析，证明离散势场在适当缩放下收敛到连续势场。

**步骤：**

1. **Walsh 展开**：将 $1/d_H$（视为 $\{0,1\}^N \times \{0,1\}^N$ 上的核函数）展开为 Walsh 函数的级数。

2. **谱分析**：利用 Krawtchouk 多项式的渐近公式，计算各阶 Fourier 系数在 $N \to \infty$ 下的行为。

3. **嵌入后的收敛**：将 Walsh 函数在嵌入空间 $[0,L]^3$ 中识别为 Fourier 模态，建立离散 Walsh 谱与连续 Fourier 谱的对应。

4. **Green 函数收敛**：证明图 Laplacian 的 Green 函数（适当缩放后）收敛到连续 Green 函数 $1/(4\pi|\mathbf{r}-\mathbf{r}'|)$。

5. **Poisson 方程恢复**：从连续 Green 函数的性质恢复 $\nabla^2 \bar{\Phi} = 4\pi G\rho$。

**优点：** 数学严格，不引入信息损失的嵌入。
**难点：** 需要 Krawtchouk 多项式的精细渐近分析。

### 方案 B：随机游走路径

**核心思想：** $\{0,1\}^N$ 上的简单随机游走在嵌入空间中收敛到 Brownian motion（Donsker 原理），离散 Green 函数收敛到连续 Green 函数。

**优点：** 有成熟的概率论工具。
**难点：** 需要证明嵌入后的随机游走确实收敛到 Brownian motion（需要验证不变原理的条件）。

### 方案 C：修正分块嵌入

**核心思想：** 保留分块嵌入框架，但修正 $\eta_N$ 的处理方式。

**关键修正：**
- 承认 $\eta_N$ 包含 $O(N)$ 的主项
- 将势场定义修正为 $\Phi_N(x) = -\sum_s f(d_H(x,s))$，其中 $f$ 是适当的缩放函数
- 或者重新定义嵌入方案，使其保持更多信息

---

## 五、下一步行动

**优先执行方案 A**，因为：
1. Fourier-Walsh 分析在超立方体上有完整理论
2. 不依赖可能有信息损失的嵌入
3. Krawtchouk 多项式的渐近公式是已知的（参见 Szegő, Askey 等人的经典结果）
4. 可以直接建立离散 Poisson 方程与连续 Poisson 方程的联系

**需要验证的数学工具：**
- Krawtchouk 多项式的 Plancherel 公式
- 超几何分布的 concentration 不等式
- 图 Laplacian 谱的渐近分布
- 离散→连续的 Γ-收敛框架
