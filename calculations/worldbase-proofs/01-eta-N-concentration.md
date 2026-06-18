# 定理 1：交叉项 η_N 的统计抵消（严格证明）

## 1. 设定

**定义 1.1（分块嵌入）** 设 $N = 3n$，$n \in \mathbb{N}$。将坐标索引集 $[N] = \{1,\dots,N\}$ 均分为三组：
$$G_k = \{(k-1)n + 1,\ \dots,\ kn\}, \qquad k = 1,2,3$$
格点间距 $\varepsilon_N = L/n$。嵌入映射 $\iota_\varepsilon : \{0,1\}^N \to [0,L]^3$ 定义为：
$$\iota_\varepsilon(x)_k = \varepsilon_N \sum_{i \in G_k} x_i, \qquad k = 1,2,3$$

**定义 1.2（中截面）** 中截面 $\Omega_N \subset \{0,1\}^N$ 定义为：
$$\Omega_N = \left\{x \in \{0,1\}^N : \sum_{i=1}^N x_i = \frac{N}{2}\right\}$$
假设 $N$ 为偶数（否则取 $\lfloor N/2 \rfloor$）。$\Omega_N$ 上赋予均匀概率测度 $\mu_N$。

**定义 1.3（交叉项）** 对固定参考态 $y \in \Omega_N$，定义：
$$\eta_N(x) := -2 \sum_{k=1}^{3} \sum_{\substack{i < j \\ i,j \in G_k}} (x_i - y_i)(x_j - y_j)$$

**引理 CL-0（已证）** 对任意 $x, y \in \{0,1\}^N$，设 $\mathbf{u} = \iota_\varepsilon(x)$，$\mathbf{v} = \iota_\varepsilon(y)$，则：
$$d_H(x,y) = \frac{n}{L^2}|\mathbf{u} - \mathbf{v}|^2 + \eta_N(x,y)$$

---

## 2. 主定理

**定理 1（η_N 浓缩不等式）** 设 $y \in \Omega_N$ 固定，$\eta_N : \Omega_N \to \mathbb{Z}$ 如定义 1.3。则：

(a) **零期望：** $\mathbb{E}_{\mu_N}[\eta_N] = 0$

(b) **方差界：** $\mathrm{Var}_{\mu_N}(\eta_N) = O(N^2)$

(c) **指数尾界：** 对任意 $t > 0$，
$$\mu_N\left(|\eta_N| \geq t\right) \leq 2\exp\left(-\frac{t^2}{2CN^2}\right)$$
其中 $C > 0$ 为绝对常数。

(d) **宏观平均下的收敛：** 设 $\delta = \delta(N)$ 满足 $\varepsilon_N \ll \delta \ll L$，对任意 $\mathbf{r} \in [0,L]^3$，定义：
$$\bar{\eta}_N(\mathbf{r}) := \frac{1}{|A_\delta(\mathbf{r})|} \sum_{x:\, \iota_\varepsilon(x) \in A_\delta(\mathbf{r})} \eta_N(x)$$
其中 $A_\delta(\mathbf{r}) = \{x \in \Omega_N : |\iota_\varepsilon(x) - \mathbf{r}| < \delta\}$。则对任意 $\gamma > 0$：
$$\mu_N\left(|\bar{\eta}_N(\mathbf{r})| \geq \gamma\right) \leq 2\exp\left(-\frac{c \cdot |A_\delta(\mathbf{r})| \cdot \gamma^2}{N^2}\right)$$
当 $|A_\delta(\mathbf{r})| \gg N^2 / \gamma^2$ 时，$\bar{\eta}_N(\mathbf{r}) \xrightarrow{\mu_N} 0$。

---

## 3. 证明

### 3.1 零期望（定理 1(a)）

**证明.** 展开交叉项：
$$\eta_N(x) = -2 \sum_{k=1}^{3} \sum_{\substack{i < j \\ i,j \in G_k}} (x_i - y_i)(x_j - y_j)$$

对固定 $k$、固定 $i < j$（$i,j \in G_k$），考虑 $\mathbb{E}_{\mu_N}[(x_i - y_i)(x_j - y_j)]$。

设 $a_i = x_i - y_i \in \{-1, 0, +1\}$。在中截面 $\Omega_N$ 上，$\sum_{i=1}^N x_i = N/2$。

**Claim：** $\mathbb{E}_{\mu_N}[a_i a_j] = 0$ 对所有 $i \neq j$。

*Proof of Claim.* 对 $\Omega_N$ 上的均匀分布，$(x_i, x_j)$ 的联合分布为：
$$\mu_N(x_i = 1, x_j = 1) = \frac{\binom{N-2}{N/2-2}}{\binom{N}{N/2}} = \frac{(N/2)(N/2-1)}{N(N-1)}$$
$$\mu_N(x_i = 1, x_j = 0) = \mu_N(x_i = 0, x_j = 1) = \frac{(N/2)^2}{N(N-1)}$$
$$\mu_N(x_i = 0, x_j = 0) = \frac{(N/2)(N/2-1)}{N(N-1)}$$

设 $y_i, y_j \in \{0,1\}$ 固定。计算 $\mathbb{E}[a_i a_j] = \mathbb{E}[(x_i - y_i)(x_j - y_j)]$：
$$= \mathbb{E}[x_i x_j] - y_i \mathbb{E}[x_j] - y_j \mathbb{E}[x_i] + y_i y_j$$

在中截面上 $\mathbb{E}[x_i] = 1/2$，$\mathbb{E}[x_i x_j] = \frac{(N/2)(N/2-1)}{N(N-1)} = \frac{N/2-1}{2(N-1)}$。

因此：
$$\mathbb{E}[a_i a_j] = \frac{N/2-1}{2(N-1)} - \frac{y_i}{2} - \frac{y_j}{2} + y_i y_j$$

对 $y_i, y_j$ 的四种情况：
- $y_i = y_j = 0$：$\frac{N/2-1}{2(N-1)} = \frac{1}{4} - \frac{1}{4(N-1)} \neq 0$

**等等，这不为零！** 让我重新检查。

实际上 $\mathbb{E}[x_i x_j] = \frac{\binom{N-2}{N/2-2}}{\binom{N}{N/2}} = \frac{(N/2)(N/2-1)}{N(N-1)} = \frac{N-2}{4(N-1)}$。

所以对 $y_i = y_j = 0$：
$$\mathbb{E}[a_i a_j] = \frac{N-2}{4(N-1)} = \frac{1}{4} - \frac{1}{4(N-1)}$$

这确实不为零。**Claim 需要修正。**

**修正的 Claim：** $\mathbb{E}_{\mu_N}[\eta_N] \neq 0$ 一般情况下。但 $|\mathbb{E}[\eta_N]| = O(N)$。

更精确地：
$$\mathbb{E}[\eta_N] = -2 \sum_{k=1}^{3} \sum_{\substack{i < j \\ i,j \in G_k}} \mathbb{E}[a_i a_j]$$

对 $y_i = y_j = 0$（或 $y_i = y_j = 1$），$\mathbb{E}[a_i a_j] = \frac{1}{4} - \frac{1}{4(N-1)} = \frac{N-2}{4(N-1)}$。

对 $y_i \neq y_j$（一个为 0 一个为 1），$\mathbb{E}[a_i a_j] = \frac{N-2}{4(N-1)} - \frac{1}{2} + 0 = -\frac{N}{4(N-1)}$。

设在块 $G_k$ 中，$y$ 有 $m_k$ 个 1。则 $|G_k| = n$，块 $G_k$ 中有 $m_k$ 个 $y_i = 1$ 和 $n - m_k$ 个 $y_i = 0$。

块 $G_k$ 的贡献：
$$\sum_{\substack{i < j \\ i,j \in G_k}} \mathbb{E}[a_i a_j] = \binom{m_k}{2} \cdot \frac{N-2}{4(N-1)} + \binom{n-m_k}{2} \cdot \frac{N-2}{4(N-1)} + m_k(n-m_k) \cdot \left(-\frac{N}{4(N-1)}\right)$$

$$= \frac{N-2}{4(N-1)} \left[\binom{m_k}{2} + \binom{n-m_k}{2}\right] - \frac{N}{4(N-1)} m_k(n-m_k)$$

$$= \frac{1}{4(N-1)} \left[(N-2)\binom{m_k}{2} + (N-2)\binom{n-m_k}{2} - N \cdot m_k(n-m_k)\right]$$

展开 $\binom{m_k}{2} + \binom{n-m_k}{2} = \frac{m_k^2 - m_k + (n-m_k)^2 - (n-m_k)}{2} = \frac{m_k^2 + (n-m_k)^2 - n}{2}$

$= \frac{2m_k^2 - 2nm_k + n^2 - n}{2}$

所以：
$$(N-2) \cdot \frac{2m_k^2 - 2nm_k + n^2 - n}{2} - N \cdot m_k(n-m_k)$$
$$= \frac{(N-2)(2m_k^2 - 2nm_k + n^2 - n) - 2N m_k(n-m_k)}{2}$$

设 $m_k = n/2 + \delta_k$（$\delta_k$ 是偏离均值的量）。则 $m_k(n-m_k) = n^2/4 - \delta_k^2$，$m_k^2 + (n-m_k)^2 = n^2/2 + 2\delta_k^2$。

代入得 $2m_k^2 - 2nm_k + n^2 - n = n^2 + 4\delta_k^2 - n - 2n(n/2 + \delta_k) = n^2 + 4\delta_k^2 - n - n^2 - 2n\delta_k = 4\delta_k^2 - n - 2n\delta_k$。

嗯，这变得很复杂。让我换个策略。

**关键洞察：** $\mathbb{E}[\eta_N]$ 不为零这一事实意味着我需要将 $\eta_N$ 分解为中心部分和偏差部分：

$$\eta_N = (\eta_N - \mathbb{E}[\eta_N]) + \mathbb{E}[\eta_N]$$

**偏差部分** $\mathbb{E}[\eta_N]$ 是确定性的，可以显式计算，量级为 $O(N)$。

**中心部分** $\tilde{\eta}_N = \eta_N - \mathbb{E}[\eta_N]$ 的方差可以用 concentration 不等式控制。

**对宏观平均的影响：** $\mathbb{E}[\eta_N] = O(N)$ 是一个确定性的修正项，可以通过重新定义嵌入映射的归一化常数来吸收，或者在最终的误差估计中作为一个 $O(1/N)$ 的修正出现（因为 $d_H = O(N)$，所以 $\mathbb{E}[\eta_N]/d_H = O(1)$，但宏观平均后这个比值趋于常数）。

**实际上，让我重新审视这个问题。**

在引理 CL-0 的关系式 $d_H = (n/L^2)|\mathbf{u}-\mathbf{v}|^2 + \eta_N$ 中：
- $d_H$ 的典型值是 $O(N)$
- $(n/L^2)|\mathbf{u}-\mathbf{v}|^2$ 的典型值也是 $O(N)$（因为 $|\mathbf{u}-\mathbf{v}| \sim L$，$n/L^2 \cdot L^2 = n = N/3$）
- $\eta_N$ 的典型值是 $O(\sqrt{N^2}) = O(N)$（标准差）

所以 $\eta_N / d_H = O(1)$，**不能忽略**！

这意味着原始文档中"$\eta_N$ 的统计平均为零，宏观平均后交叉项相互抵消"的说法**需要修正**。

**正确的处理方式：**

1. $\eta_N$ 的期望不为零，而是 $O(N)$。
2. $\eta_N$ 的方差是 $O(N^2)$，标准差是 $O(N)$。
3. 相对量 $\eta_N / d_H$ 的期望和标准差都是 $O(1)$。
4. 在宏观平均下，$\bar{\eta}_N$ 的期望仍为 $O(N)$，但方差缩小为 $O(N^2 / |A_\delta|)$。
5. **$\eta_N$ 不能被忽略，而是需要被显式处理。**

**修正后的策略：**

不将 $\eta_N$ 视为"噪声"，而是将其纳入主项。具体地：

$$\frac{1}{d_H(x,s)} = \frac{1}{\frac{n}{L^2}|\mathbf{u}-\mathbf{v}|^2 + \eta_N} = \frac{L^2}{n} \cdot \frac{1}{|\mathbf{u}-\mathbf{v}|^2 + \frac{L^2}{n}\eta_N}$$

设 $\xi_N = \frac{L^2}{n}\eta_N$，则 $\xi_N = O(L^2)$（因为 $\eta_N = O(N) = O(3n)$，$\xi_N = O(L^2 \cdot 3) = O(L^2)$）。

在宏观平均下：
$$\left\langle \frac{1}{d_H} \right\rangle \approx \frac{L^2}{n} \cdot \left\langle \frac{1}{|\mathbf{u}-\mathbf{v}|^2 + \xi_N} \right\rangle$$

如果 $\xi_N$ 的涨落相对于 $|\mathbf{u}-\mathbf{v}|^2$ 很小（当 $|\mathbf{u}-\mathbf{v}| \gg L$ 时成立，但这不总是成立），则可以用 Taylor 展开。

**但这引入了新的复杂性。让我重新考虑整个问题的正确提法。**

---

## 4. 重新审视：正确的收敛框架

**核心问题：** 从离散势场 $\Phi_N(x) = -\sum_{s \in S_N} 1/d_H(x,s)$ 到连续势场 $\bar{\Phi}(\mathbf{r}) = -\int \rho(\mathbf{r}')/|\mathbf{r}-\mathbf{r}'| \, d^3r'$ 的收敛，不应当通过"逐项近似"来证明，而应当通过**整体方法**。

**正确路径：** 使用图论中的离散位势论（discrete potential theory）。

**定义 4.1（超立方体上的图 Laplacian）** 在 $\{0,1\}^N$ 上定义图 Laplacian：
$$(\Delta_N f)(x) = \frac{1}{N}\sum_{j=1}^{N} [f(x \oplus e_j) - f(x)]$$
其中 $e_j$ 是第 $j$ 个标准基向量，$\oplus$ 是逐分量模 2 加法。

**定义 4.2（离散 Green 函数）** 图 Laplacian 的 Green 函数 $G_N(x,y)$ 满足：
$$\Delta_N G_N(\cdot, y) = \delta_y - \frac{1}{2^N}$$
（归一化条件：$\sum_x G_N(x,y) = 0$）

**关键事实（Fourier 分析在 $\{0,1\}^N$ 上）：**

Walsh 函数 $\chi_S(x) = (-1)^{\sum_{i \in S} x_i}$（$S \subseteq [N]$）是 $\Delta_N$ 的特征函数：
$$\Delta_N \chi_S = \left(\frac{|S|}{N} - 1\right) \chi_S + \frac{|S|}{N}\chi_S = \frac{2|S|}{N}\chi_S - \chi_S$$

等等，让我重新计算。对 $f = \chi_S$：
$$(\Delta_N \chi_S)(x) = \frac{1}{N}\sum_{j=1}^{N} [\chi_S(x \oplus e_j) - \chi_S(x)]$$

$\chi_S(x \oplus e_j) = (-1)^{\sum_{i \in S}(x_i + \delta_{ij} \bmod 2)} = (-1)^{\sum_{i \in S} x_i + [j \in S]} = \chi_S(x) \cdot (-1)^{[j \in S]}$

所以 $\chi_S(x \oplus e_j) - \chi_S(x) = \chi_S(x)[(-1)^{[j \in S]} - 1]$

对 $j \in S$：$(-1)^1 - 1 = -2$
对 $j \notin S$：$(-1)^0 - 1 = 0$

因此：
$$(\Delta_N \chi_S)(x) = \frac{1}{N} \cdot |S| \cdot (-2) \cdot \chi_S(x) = -\frac{2|S|}{N} \chi_S(x)$$

所以 $\Delta_N \chi_S = -\frac{2|S|}{N} \chi_S$。

**特征值：** $\lambda_S = -\frac{2|S|}{N}$，对应特征函数 $\chi_S$。

**Green 函数：**
$$G_N(x,y) = \sum_{S \subseteq [N], S \neq \emptyset} \frac{1}{-\lambda_S} \chi_S(x)\chi_S(y) \cdot \frac{1}{2^N}$$
$$= \frac{1}{2^N} \sum_{S \neq \emptyset} \frac{N}{2|S|} \chi_S(x)\chi_S(y)$$

$$= \frac{N}{2^{N+1}} \sum_{S \neq \emptyset} \frac{\chi_S(x)\chi_S(y)}{|S|}$$

利用 $\chi_S(x)\chi_S(y) = \chi_S(x \oplus y) = (-1)^{d_H(x \oplus y, \mathbf{0}) \cdot S}$（更准确地说，$= (-1)^{\sum_{i \in S}(x_i \oplus y_i)}$）。

设 $z = x \oplus y$，$w = |z| = d_H(x,y)$。则：
$$G_N(x,y) = \frac{N}{2^{N+1}} \sum_{S \neq \emptyset} \frac{(-1)^{\sum_{i \in S} z_i}}{|S|}$$

$$= \frac{N}{2^{N+1}} \sum_{k=1}^{N} \frac{1}{k} \sum_{\substack{S \subseteq [N] \\ |S| = k}} (-1)^{\sum_{i \in S} z_i}$$

对固定 $z$ 有 $w$ 个 1，设 $A = \{i : z_i = 1\}$（$|A| = w$），$B = [N] \setminus A$（$|B| = N-w$）。

$$\sum_{\substack{S \subseteq [N] \\ |S| = k}} (-1)^{\sum_{i \in S} z_i} = \sum_{\substack{S \subseteq [N] \\ |S| = k}} (-1)^{|S \cap A|}$$

$$= \sum_{l=0}^{\min(k,w)} (-1)^l \binom{w}{l}\binom{N-w}{k-l}$$

这是 Krawtchouk 多项式的值：$K_k(w; N) = \sum_{l=0}^{k} (-1)^l \binom{w}{l}\binom{N-w}{k-l}$。

所以：
$$G_N(x,y) = \frac{N}{2^{N+1}} \sum_{k=1}^{N} \frac{K_k(d_H(x,y); N)}{k}$$

这是一个精确公式，但不容易直接看出连续极限。

**替代方法：随机游走**

$\{0,1\}^N$ 上的简单随机游走在每一步等概率翻转一个坐标位。该随机游走的 Green 函数就是上面的 $G_N$。

在连续极限 $N \to \infty$ 下，嵌入后的随机游走收敛到 $[0,L]^3$ 上的 Brownian motion（由 Donsker 不变原理）。离散 Green 函数收敛到连续 Green 函数。

**但这个路径太长了，需要单独一篇论文。让我回到原始问题的更直接的处理。**

---

## 5. 直接方法：修正后的收敛证明

**策略：** 不试图证明 $\eta_N \to 0$，而是证明在正确的归一化下，离散势场的**主项**收敛到连续势场。

**定理 1'（修正版，η_N 的控制）**

设 $y \in \Omega_N$ 固定，$\eta_N$ 如定义 1.3。则：

(a) $|\mathbb{E}_{\mu_N}[\eta_N]| \leq CN$，其中 $C$ 依赖于 $y$ 在各块中的 1 的分布。

(b) $\mathrm{Var}_{\mu_N}(\eta_N) \leq C'N^2$

(c) 对宏观平均 $\bar{\eta}_N(\mathbf{r})$（在 $|A_\delta| \gg 1$ 个点上平均）：
$$|\mathbb{E}[\bar{\eta}_N(\mathbf{r})]| \leq CN, \qquad \mathrm{Var}(\bar{\eta}_N(\mathbf{r})) \leq \frac{C'N^2}{|A_\delta(\mathbf{r})|}$$

**证明.** 

(a) 的计算已在 §3.1 中开始。关键观察是 $\mathbb{E}[\eta_N]$ 依赖于 $y$ 的具体配置，但总是 $O(N)$。

(b) 的方差计算需要 $\mathrm{Var}(\eta_N) = 4 \sum \mathrm{Cov}(a_i a_j, a_{i'} a_{j'})$。由于每项 $|a_i a_j| \leq 1$，且总共有 $O(N^2)$ 个交叉项对，方差最多为 $O(N^4)$。但利用中截面上的负相关性（$\mathrm{Cov}(x_i, x_j) < 0$ 当 $\sum x_i$ 固定时），可以将方差压缩到 $O(N^2)$。

**方差的严格计算：**

$\eta_N = -2\sum_{k} \sum_{i<j \in G_k} a_i a_j$，其中 $a_i = x_i - y_i$。

设 $W_k = \sum_{i \in G_k} a_i$（块 $G_k$ 中 $a_i$ 的和）。则：
$$\eta_N = -2\sum_{k=1}^{3} \frac{W_k^2 - \sum_{i \in G_k} a_i^2}{2} = -\sum_{k=1}^{3} W_k^2 + \sum_{k=1}^{3}\sum_{i \in G_k} a_i^2$$

$$= -\sum_{k=1}^{3} W_k^2 + \sum_{i=1}^{N} a_i^2$$

现在 $a_i = x_i - y_i$，$a_i^2 = |x_i - y_i| \in \{0, 1\}$。设 $D = \sum_{i=1}^N a_i^2 = d_H(x,y)$（$x$ 和 $y$ 的汉明距离）。

所以：
$$\eta_N = D - \sum_{k=1}^{3} W_k^2$$

其中 $D = d_H(x,y)$，$W_k = \sum_{i \in G_k}(x_i - y_i)$。

**这是一个关键简化！**

现在 $\eta_N = D - \sum_k W_k^2$，而 $d_H = (n/L^2)|\mathbf{u}-\mathbf{v}|^2 + \eta_N$，验证：
$$(n/L^2)|\mathbf{u}-\mathbf{v}|^2 = (n/L^2) \cdot L^2/n^2 \cdot \sum_k W_k^2 = \frac{1}{n}\sum_k W_k^2$$

等等，$|\mathbf{u}-\mathbf{v}|^2 = \varepsilon^2 \sum_k W_k^2 = (L/n)^2 \sum_k W_k^2$。

$(n/L^2)|\mathbf{u}-\mathbf{v}|^2 = (n/L^2)(L^2/n^2)\sum_k W_k^2 = \frac{1}{n}\sum_k W_k^2$

所以 $d_H = \frac{1}{n}\sum_k W_k^2 + \eta_N = \frac{1}{n}\sum_k W_k^2 + D - \sum_k W_k^2 = D + (1/n - 1)\sum_k W_k^2$

但这应该等于 $D = d_H$，所以 $(1/n - 1)\sum_k W_k^2 = 0$，即 $\sum_k W_k^2 = 0$。

**矛盾！** 这说明我的分解有误。让我重新检查。

引理 CL-0 的正确形式应该是：
$$d_H(x,y) = \frac{n}{L^2}|\mathbf{u}-\mathbf{v}|^2 + \eta_N(x,y)$$

其中 $|\mathbf{u}-\mathbf{v}|^2 = \varepsilon^2 \sum_k \left(\sum_{i \in G_k}(x_i - y_i)\right)^2 = \varepsilon^2 \sum_k W_k^2$

$\frac{n}{L^2}|\mathbf{u}-\mathbf{v}|^2 = \frac{n}{L^2} \cdot \frac{L^2}{n^2} \sum_k W_k^2 = \frac{1}{n}\sum_k W_k^2$

所以 $d_H = \frac{1}{n}\sum_k W_k^2 + \eta_N$。

但 $d_H = D = \sum_{i=1}^N (x_i - y_i)^2 = \sum_i a_i^2$。

而 $\sum_k W_k^2 = \sum_k \left(\sum_{i \in G_k} a_i\right)^2 = \sum_k \left[\sum_i a_i^2 + 2\sum_{i<j \in G_k} a_i a_j\right] = D + 2\sum_k \sum_{i<j \in G_k} a_i a_j$

所以 $\frac{1}{n}\sum_k W_k^2 = \frac{D}{n} + \frac{2}{n}\sum_k \sum_{i<j \in G_k} a_i a_j$

$d_H = \frac{D}{n} + \frac{2}{n}\sum_k \sum_{i<j \in G_k} a_i a_j + \eta_N$

$\eta_N = D - \frac{D}{n} - \frac{2}{n}\sum_k \sum_{i<j \in G_k} a_i a_j = D(1 - 1/n) - \frac{2}{n}\sum_k \sum_{i<j \in G_k} a_i a_j$

但原始文档说 $\eta_N = -2\sum_k \sum_{i<j \in G_k} a_i a_j$。

让我重新检查引理 CL-0 的证明。

$(u_k - v_k)^2 = \varepsilon^2 \left(\sum_{i \in G_k} a_i\right)^2 = \varepsilon^2 \left[\sum_{i \in G_k} a_i^2 + 2\sum_{i<j \in G_k} a_i a_j\right]$

$|\mathbf{u}-\mathbf{v}|^2 = \varepsilon^2 \sum_k \left[\sum_{i \in G_k} a_i^2 + 2\sum_{i<j \in G_k} a_i a_j\right] = \varepsilon^2 \left[D + 2\sum_k \sum_{i<j \in G_k} a_i a_j\right]$

$\frac{n}{L^2}|\mathbf{u}-\mathbf{v}|^2 = \frac{n \varepsilon^2}{L^2}\left[D + 2\sum_k \sum_{i<j \in G_k} a_i a_j\right] = \frac{1}{n}\left[D + 2\sum_k \sum_{i<j \in G_k} a_i a_j\right]$

所以 $d_H = D = \frac{1}{n}\left[D + 2\sum_k \sum_{i<j \in G_k} a_i a_j\right] + \eta_N$

$\eta_N = D - \frac{D}{n} - \frac{2}{n}\sum_k \sum_{i<j \in G_k} a_i a_j = D\left(1 - \frac{1}{n}\right) - \frac{2}{n}\sum_k \sum_{i<j \in G_k} a_i a_j$

**这与原始文档中 $\eta_N = -2\sum_k \sum_{i<j \in G_k} a_i a_j$ 不一致！**

原始文档的引理 CL-0 声称：
$$d_H(x,y) = \frac{n}{L^2}|\mathbf{u}-\mathbf{v}|^2 + \eta_N$$
$$\eta_N = -2\sum_{k=1}^{3}\sum_{\substack{i < j \\ i,j \in G_k}}(x_i - y_i)(x_j - y_j)$$

但根据我的计算，正确的公式应该是：
$$\eta_N = D\left(1 - \frac{1}{n}\right) - \frac{2}{n}\sum_k \sum_{i<j \in G_k} a_i a_j$$

或者等价地：
$$d_H = \frac{n}{L^2}|\mathbf{u}-\mathbf{v}|^2 + D\left(1 - \frac{1}{n}\right) - \frac{2}{n}\sum_k \sum_{i<j \in G_k} a_i a_j$$

**原始文档的引理 CL-0 的证明中有一个代数错误。**

让我仔细重新推导：

$(u_k - v_k)^2 = \varepsilon^2 W_k^2$

$|\mathbf{u}-\mathbf{v}|^2 = \varepsilon^2 \sum_k W_k^2$

$\frac{n}{L^2}|\mathbf{u}-\mathbf{v}|^2 = \frac{n}{L^2} \cdot \frac{L^2}{n^2} \sum_k W_k^2 = \frac{1}{n}\sum_k W_k^2$

$d_H - \frac{n}{L^2}|\mathbf{u}-\mathbf{v}|^2 = D - \frac{1}{n}\sum_k W_k^2$

$= D - \frac{1}{n}\sum_k \left(\sum_{i \in G_k} a_i\right)^2$

$= D - \frac{1}{n}\sum_k \left[\sum_{i \in G_k} a_i^2 + 2\sum_{i<j \in G_k} a_i a_j\right]$

$= D - \frac{D}{n} - \frac{2}{n}\sum_k \sum_{i<j \in G_k} a_i a_j$

$= \frac{n-1}{n}D - \frac{2}{n}\sum_k \sum_{i<j \in G_k} a_i a_j$

当 $n \gg 1$ 时，$(n-1)/n \approx 1$，所以主项是 $D$ 本身。这意味着：

$$\eta_N := d_H - \frac{n}{L^2}|\mathbf{u}-\mathbf{v}|^2 = \frac{n-1}{n}D - \frac{2}{n}\sum_k \sum_{i<j \in G_k} a_i a_j$$

**这不是原始文档中的 $-2\sum_k \sum_{i<j \in G_k} a_i a_j$。**

原始文档的公式 $\eta_N = -2\sum_k \sum_{i<j \in G_k} a_i a_j$ 对应的应该是：
$$d_H = \frac{n}{L^2}|\mathbf{u}-\mathbf{v}|^2 - 2\sum_k \sum_{i<j \in G_k} a_i a_j$$

但根据上面的推导，$\frac{n}{L^2}|\mathbf{u}-\mathbf{v}|^2 = \frac{D}{n} + \frac{2}{n}\sum_k \sum_{i<j \in G_k} a_i a_j$，所以：

$\frac{n}{L^2}|\mathbf{u}-\mathbf{v}|^2 - 2\sum_k \sum_{i<j \in G_k} a_i a_j = \frac{D}{n} + \frac{2}{n}\sum_k \sum_{i<j \in G_k} a_i a_j - 2\sum_k \sum_{i<j \in G_k} a_i a_j$

$= \frac{D}{n} + \left(\frac{2}{n} - 2\right)\sum_k \sum_{i<j \in G_k} a_i a_j$

$= \frac{D}{n} - \frac{2(n-1)}{n}\sum_k \sum_{i<j \in G_k} a_i a_j$

这不等于 $D$（除非 $\sum_k \sum_{i<j \in G_k} a_i a_j$ 取特定值）。

**结论：原始文档的引理 CL-0 的 $\eta_N$ 表达式有误。**

正确的表达式应该是：
$$\eta_N = \frac{n-1}{n}D - \frac{2}{n}\sum_k \sum_{i<j \in G_k} a_i a_j$$

或等价地：
$$d_H = \frac{1}{n}\sum_k W_k^2 + \frac{n-1}{n}D - \frac{2}{n}\sum_k \sum_{i<j \in G_k} a_i a_j$$

这可以通过 $\sum_k W_k^2 = D + 2\sum_k \sum_{i<j} a_i a_j$ 来验证。

**这个发现意味着原始证明框架需要重大修正。** $\eta_N$ 不仅仅是交叉项，还包含一个 $O(D)$ 的主项。

---

## 6. 正确的关系式

**定理 1''（正确版：汉明距离与嵌入距离的关系）**

对任意 $x, y \in \{0,1\}^N$：
$$d_H(x,y) = \frac{1}{n}\sum_{k=1}^{3} W_k^2 + \frac{n-1}{n} D - \frac{2}{n}\sum_{k=1}^{3}\sum_{\substack{i < j \\ i,j \in G_k}} a_i a_j$$

其中 $a_i = x_i - y_i$，$W_k = \sum_{i \in G_k} a_i$，$D = \sum_i a_i^2 = d_H(x,y)$。

等价地：
$$d_H(x,y) = \frac{n}{L^2}|\mathbf{u}-\mathbf{v}|^2 + \underbrace{\frac{n-1}{n}d_H(x,y) - \frac{2}{n}\sum_{k=1}^{3}\sum_{\substack{i < j \\ i,j \in G_k}} a_i a_j}_{\displaystyle =: \eta_N^{\text{correct}}}$$

**注：** 这意味着 $\eta_N^{\text{correct}}$ 包含 $d_H$ 本身！这不是一个"小修正"，而是一个 $O(N)$ 的量。原始文档将 $\eta_N$ 视为小量的假设**不成立**。

**但这也意味着 $d_H$ 和 $(n/L^2)|\mathbf{u}-\mathbf{v}|^2$ 之间的关系需要重新理解。**

实际上，让我直接验证：$d_H = \sum_i a_i^2$，$(n/L^2)|\mathbf{u}-\mathbf{v}|^2 = \frac{1}{n}\sum_k W_k^2$。

当 $n$ 很大时，如果 $a_i$ 是"随机的"（在中截面上），则 $W_k = \sum_{i \in G_k} a_i$ 是 $O(\sqrt{n})$ 的量，$\sum_k W_k^2 = O(n) = O(N/3)$。而 $D = d_H = O(N)$。

所以 $\frac{1}{n}\sum_k W_k^2 = O(1)$，但 $D = O(N)$。

**这意味着 $(n/L^2)|\mathbf{u}-\mathbf{v}|^2 \neq d_H$，两者相差 $O(N)$！**

让我用一个具体例子验证。设 $N = 6$，$n = 2$，$G_1 = \{1,2\}$，$G_2 = \{3,4\}$，$G_3 = \{5,6\}$。

$x = (1,0,1,0,1,0)$，$y = (0,1,0,1,0,1)$。$a = (1,-1,1,-1,1,-1)$。$D = 6$。

$W_1 = 1+(-1) = 0$，$W_2 = 0$，$W_3 = 0$。$\sum_k W_k^2 = 0$。

$(n/L^2)|\mathbf{u}-\mathbf{v}|^2 = 0$，但 $d_H = 6$。

**这证实了 $(n/L^2)|\mathbf{u}-\mathbf{v}|^2$ 和 $d_H$ 之间可以有很大的差异。**

在这个例子中，$x$ 和 $y$ 在每个块内恰好互补，所以嵌入后的距离为零，但汉明距离为 $N$。这说明嵌入映射 $\iota_\varepsilon$ **不是**等距的，信息损失很大。

**根本问题：** 分块嵌入 $\iota_\varepsilon$ 将每个块的 $n$ 个坐标求和为一个连续坐标，丢失了块内的精细结构。两个点可以在嵌入空间中重合（$|\mathbf{u}-\mathbf{v}| = 0$）但汉明距离很大（$d_H = O(N)$）。

**这意味着原始文档的整个"从汉明距离到欧氏距离"的桥梁有根本性问题。**

---

## 7. 诊断总结

经过严格计算，发现原始文档 `04-continuous-limit.md` 中存在以下关键问题：

### 问题 1：引理 CL-0 的 $\eta_N$ 表达式有误

原始声称：$\eta_N = -2\sum_k \sum_{i<j \in G_k} a_i a_j$

正确表达式：$\eta_N = \frac{n-1}{n}D - \frac{2}{n}\sum_k \sum_{i<j \in G_k} a_i a_j$

其中 $D = d_H(x,y)$。

### 问题 2：$\eta_N$ 不是小量

原始假设 $\eta_N$ 在宏观平均后趋于零。但实际上 $\eta_N = O(N)$（因为包含 $D = O(N)$ 的主项），不能忽略。

### 问题 3：嵌入映射的信息损失

分块嵌入 $\iota_\varepsilon$ 不是单射：$2^N$ 个离散点被映射到 $(n+1)^3 \approx (N/3+1)^3$ 个格点上，每个格点对应约 $2^N / (N/3)^3$ 个原始点。嵌入后的"距离"与汉明距离有本质差异。

### 问题 4：$1/r^2$ 到 $1/r$ 的转换

原始文档声称通过"径向积分"将 $1/r^2$ 核转换为 $1/r$ 势。但这个论证依赖于定理 G（$\Phi \propto -1/r$），而定理 G 本身依赖于连续极限，形成循环论证。

---

## 8. 修正方向

**方向 A：放弃分块嵌入，直接使用离散位势论**

在 $\{0,1\}^N$ 上直接定义势场，使用图 Laplacian 的 Green 函数，然后证明其在适当缩放下收敛到连续 Green 函数。

优点：数学严格，不引入信息损失。
缺点：需要重新建立从离散 Green 函数到 Newton 势的桥梁。

**方向 B：修正嵌入方案**

使用更精细的嵌入（例如，不将坐标分组求和，而是使用随机投影或 Johnson-Lindenstrauss 引理），保持距离关系。

**方向 C：保留分块嵌入但修正论证**

承认 $\eta_N$ 不是小量，重新设计收敛证明。关键是在宏观平均下，$\eta_N$ 的**涨落**（而非绝对值）趋于零。

**建议：方向 A 最有希望，因为离散位势论在超立方体上有成熟的工具（Fourier-Walsh 分析）。**
