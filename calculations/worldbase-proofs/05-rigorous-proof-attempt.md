# 连续极限严格证明 — 最终策略

## 放弃的路径及原因

| 路径 | 失败原因 |
|---|---|
| 分块嵌入 + η_N 小量 | η_N = O(N)，不是小量 |
| 随机游走 + Trotter-Kato | 中截面约束 Σx_i = N/2 引入长程相关，不收敛到 BM |
| Fourier-Walsh + Green 函数 | 图维数 N ≠ 嵌入维数 3，Green 函数行为不同 |

## 采用的路径：直接积分 + 分布收敛

**核心思路：** 不证明逐点收敛，而是证明对任意光滑测试函数 φ，积分 ∫Φ_N·φ 收敛到 ∫Φ·φ。这在分布意义下足够。

---

## 定理 CL-NEW：宏观势场的分布收敛

### 设定

- $N = 3n$，$Q_N = \{0,1\}^N$
- 嵌入 $\iota : Q_N \to [0,L]^3$，$\iota(x)_k = \frac{L}{n}\sum_{i \in G_k} x_i$
- 源集 $S_N \subset Q_N$，$|S_N| = M_N$，其嵌入像 $\{\iota(s) : s \in S_N\}$ 在 $[0,L]^3$ 中以密度 $\rho(\mathbf{r})$ 分布
- 离散势场：$\Phi_N(x) = -\sum_{s \in S_N} \frac{1}{d_H(x,s)}$
- 宏观势场（连续）：$\bar{\Phi}(\mathbf{r}) = -\int_{[0,L]^3} \frac{\rho(\mathbf{r}')}{|\mathbf{r}-\mathbf{r}'|} d^3r'$

### 陈述

设 $\rho \in C([0,L]^3)$，$\rho \geq 0$。对任意 $\phi \in C_c^\infty((0,L)^3)$：

$$\lim_{N \to \infty} \frac{1}{M_N} \sum_{x \in Q_N} \Phi_N(x) \cdot \phi(\iota(x)) = \int_{[0,L]^3} \bar{\Phi}(\mathbf{r}) \phi(\mathbf{r}) d^3r$$

### 证明

**Step 1：展开 $\Phi_N$**

$$\frac{1}{M_N}\sum_{x \in Q_N} \Phi_N(x) \phi(\iota(x)) = -\frac{1}{M_N}\sum_{x \in Q_N}\sum_{s \in S_N} \frac{\phi(\iota(x))}{d_H(x,s)}$$

$$= -\frac{1}{M_N}\sum_{s \in S_N}\sum_{x \in Q_N} \frac{\phi(\iota(x))}{d_H(x,s)}$$

**Step 2：内层求和的渐近**

对固定 $s \in S_N$，设 $\mathbf{v} = \iota(s)$。求和：
$$I_N(s) := \sum_{x \in Q_N} \frac{\phi(\iota(x))}{d_H(x,s)}$$

将 $x$ 按汉明距离 $w = d_H(x,s)$ 分组：
$$I_N(s) = \sum_{w=1}^{N} \frac{1}{w} \sum_{\substack{x \in Q_N \\ d_H(x,s) = w}} \phi(\iota(x))$$

**Step 3：汉明球上的求和**

内层求和 $\sum_{d_H(x,s)=w} \phi(\iota(x))$ 是汉明球 $H_w(s) = \{x : d_H(x,s) = w\}$ 上 $\phi \circ \iota$ 的和。

汉明球的大小：$|H_w(s)| = \binom{N}{w}$。

**关键引理（汉明球的嵌入分布）：** 对 $x$ 均匀分布在 $H_w(s)$ 上，$\iota(x)$ 的分布在 $[0,L]^3$ 中近似为：

$$\iota(x)_k \approx \iota(s)_k + \frac{L}{n}\cdot\frac{w_k}{2} + O(\sqrt{w_k/n})$$

其中 $w_k = |\{j \in G_k : x_j \neq s_j}|$ 是块 $G_k$ 中不同的比特数，$w_1 + w_2 + w_3 = w$。

对固定的 $w$，$(w_1, w_2, w_3)$ 的分布近似为多项分布 $\text{Multinomial}(w; 1/3, 1/3, 1/3)$。所以 $\mathbb{E}[w_k] = w/3$，$\text{Var}(w_k) = 2w/9$。

因此 $\iota(x) \approx \iota(s) + \frac{Lw}{6n}\mathbf{1} + O(L\sqrt{w}/n)$，其中 $\mathbf{1} = (1,1,1)$。

**Step 4：连续近似**

在 $N \to \infty$ 极限下，汉明球 $H_w(s)$ 的嵌入像在 $\iota(s)$ 附近形成一个"壳"，半径约为 $r_w = L\sqrt{w/(3n)}$（因为 $|\iota(x) - \iota(s)|^2 \approx \frac{L^2}{n^2}\sum_k w_k^2 \approx \frac{L^2}{n^2}\cdot\frac{w^2}{3}$，等等，这需要更仔细的计算）。

让我直接计算。对 $x \in H_w(s)$，设 $a_j = x_j - s_j \in \{-1, 0, +1\}$，$d_H = \sum |a_j| = w$。

$$|\iota(x) - \iota(s)|^2 = \frac{L^2}{n^2}\sum_{k=1}^3 \left(\sum_{j \in G_k} a_j\right)^2$$

设 $A_k = \sum_{j \in G_k} a_j$。则 $|A_k| \leq w_k$，且 $\sum_k |A_k| \leq w$（但不等于 $w$，因为 $a_j$ 有正有负）。

对 $x$ 均匀分布在 $H_w(s)$ 上：$\mathbb{E}[A_k] = 0$（正负对称），$\text{Var}(A_k) = w_k$（近似）。所以 $\mathbb{E}[|\iota(x) - \iota(s)|^2] \approx \frac{L^2}{n^2}\sum_k w_k = \frac{L^2 w}{n^2}$。

因此嵌入距离 $|\iota(x) - \iota(s)| \approx L\sqrt{w}/n$。

**Step 5：黎曼和转换**

$$I_N(s) = \sum_{w=1}^N \frac{1}{w} \sum_{x \in H_w(s)} \phi(\iota(x))$$

$$\approx \sum_{w=1}^N \frac{\binom{N}{w}}{w} \cdot \mathbb{E}_{x \in H_w(s)}[\phi(\iota(x))]$$

设 $r = L\sqrt{w}/n$（嵌入距离）。则 $\phi(\iota(x)) \approx \phi(\mathbf{v} + r\hat{\mathbf{n}})$，其中 $\hat{\mathbf{n}}$ 是随机方向。

在球面平均下：
$$\mathbb{E}[\phi(\mathbf{v} + r\hat{\mathbf{n}})] \approx \phi(\mathbf{v}) + \frac{r^2}{6}\nabla^2\phi(\mathbf{v}) + O(r^4)$$

**Step 6：求和的渐近**

$$I_N(s) \approx \sum_{w=1}^N \frac{\binom{N}{w}}{w}\left[\phi(\mathbf{v}) + \frac{L^2 w}{6n^2}\nabla^2\phi(\mathbf{v}) + O(w^2/n^4)\right]$$

$$= \phi(\mathbf{v})\sum_{w=1}^N \frac{\binom{N}{w}}{w} + \frac{L^2}{6n^2}\nabla^2\phi(\mathbf{v})\sum_{w=1}^N \binom{N}{w} + O(1/n)$$

利用恒等式 $\sum_{w=1}^N \frac{\binom{N}{w}}{w} = \sum_{w=1}^N \frac{1}{w}\binom{N}{w}$ 和 $\sum_{w=0}^N \binom{N}{w} = 2^N$。

**关键恒等式：** $\sum_{w=1}^N \frac{\binom{N}{w}}{w} = \frac{2^N - 1}{N} \cdot \frac{N}{1} = ...$

实际上，$\sum_{w=1}^N \frac{\binom{N}{w}}{w} = \int_0^1 \frac{(1+t)^N - 1}{t} dt$（利用 $\frac{1}{w} = \int_0^1 t^{w-1} dt$）。

$= \int_0^1 \frac{(1+t)^N - 1}{t} dt$

对大 $N$：$(1+t)^N \approx e^{Nt}$ 对 $t$ 小。积分 $\approx \int_0^1 \frac{e^{Nt} - 1}{t} dt \approx \int_0^{N} \frac{e^u - 1}{u} du \approx e^N / N$（主导项）。

更精确地：$\sum_{w=1}^N \frac{\binom{N}{w}}{w} = \frac{2^N}{N}(1 + O(1/N))$（可以用归纳法证明）。

所以：
$$I_N(s) \approx \frac{2^N}{N}\phi(\mathbf{v}) + \frac{2^N L^2}{6n^2}\nabla^2\phi(\mathbf{v}) + O(2^N/n)$$

**Step 7：对 $s$ 求平均**

$$\frac{1}{M_N}\sum_{s \in S_N} I_N(s) \approx \frac{2^N}{NM_N}\sum_{s \in S_N}\phi(\iota(s)) + \frac{2^N L^2}{6n^2 M_N}\sum_{s \in S_N}\nabla^2\phi(\iota(s)) + O(2^N/n)$$

如果 $S_N$ 以密度 $\rho$ 分布，则：
$$\frac{1}{M_N}\sum_{s \in S_N}\phi(\iota(s)) \to \frac{1}{|[0,L]^3|}\int \phi(\mathbf{r})\rho(\mathbf{r})d^3r = \frac{1}{L^3}\int \phi\rho$$

**Step 8：匹配连续表达式**

在连续 Poisson 方程中：
$$\int \bar{\Phi}(\mathbf{r})\phi(\mathbf{r})d^3r = -\int\int \frac{\rho(\mathbf{r}')}{|\mathbf{r}-\mathbf{r}'|}\phi(\mathbf{r})d^3r d^3r'$$

$= -\int \rho(\mathbf{r}') \left[\int \frac{\phi(\mathbf{r})}{|\mathbf{r}-\mathbf{r}'|}d^3r\right] d^3r'$

$= -\int \rho(\mathbf{r}') G[\phi](\mathbf{r}') d^3r'$

其中 $G[\phi](\mathbf{r}') = \int \frac{\phi(\mathbf{r})}{|\mathbf{r}-\mathbf{r}'|}d^3r$ 是 $\phi$ 的 Newton 势。

**从 Step 6-7：**
$$\frac{1}{M_N}\sum_x \Phi_N(x)\phi(\iota(x)) \approx -\frac{2^N}{NM_N}\sum_s \phi(\iota(s)) - \frac{2^N L^2}{6n^2 M_N}\sum_s \nabla^2\phi(\iota(s))$$

第一项 $\propto \int \phi\rho$，第二项 $\propto \int (\nabla^2\phi)\rho$。

但连续表达式是 $\int \bar{\Phi}\phi = -\int \rho \cdot G[\phi]$。这不直接匹配——需要进一步分析。

**问题：** 离散势场的形式是 $1/d_H$（核），而连续势场的形式是 $1/|r-r'|$（核）。两者不同。需要证明的是 $1/d_H$ 的"平均效应"等价于 $1/|r-r'|$。

---

## 关键洞察

**$1/d_H$ 和 $1/|r-r'|$ 的关系不是逐点近似，而是积分等价。**

具体地说：$1/d_H$ 的"球面平均"在嵌入空间中等价于 $1/|r-r'|$ 的球面平均。

证明这个等价性是整个论证的核心。它不依赖 η_N 的逐点控制，而是依赖汉明球的统计性质。

**下一步：** 严格证明 Step 6 中的渐近公式，特别是 $\sum_{w} \frac{\binom{N}{w}}{w} \cdot g(w)$ 对一般函数 $g$ 的渐近行为。
