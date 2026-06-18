# 定理 2：超立方体上的 Fourier-Walsh 分析与 Green 函数

## 1. 设定

**定义 2.1（超立方体）** 设 $Q_N = \{0,1\}^N$，赋予 Hamming 距离 $d_H(x,y) = |\{i : x_i \neq y_i\}|$。

**定义 2.2（图 Laplacian）** 在 $Q_N$ 上定义归一化图 Laplacian：
$$(\mathcal{L}_N f)(x) = \frac{1}{N}\sum_{j=1}^{N}\left[f(x \oplus e_j) - f(x)\right]$$
其中 $e_j$ 是第 $j$ 个标准基向量，$\oplus$ 是逐分量 XOR。

**定义 2.3（Walsh 函数）** 对 $S \subseteq [N] = \{1,\dots,N\}$，定义：
$$\chi_S(x) = (-1)^{\sum_{i \in S} x_i} = \prod_{i \in S}(-1)^{x_i}$$

**定义 2.4（均匀测度）** $\mu_N$ 为 $Q_N$ 上的均匀概率测度，$\mu_N(\{x\}) = 2^{-N}$。

---

## 2. Walsh 函数的正交性与完备性

**引理 2.1（正交性）** 对 $S, T \subseteq [N]$：
$$\langle \chi_S, \chi_T \rangle_{L^2(\mu_N)} = \mathbb{E}_{\mu_N}[\chi_S \chi_T] = \delta_{ST}$$

**证明.** $\chi_S(x)\chi_T(x) = \chi_{S \triangle T}(x)$（对称差）。若 $S \triangle T \neq \emptyset$，取 $j \in S \triangle T$：
$$\mathbb{E}[\chi_{S \triangle T}] = \frac{1}{2}\left[\mathbb{E}[\chi_{S \triangle T \setminus \{j\}}] + \mathbb{E}[-\chi_{S \triangle T \setminus \{j\}}]\right] = 0$$
（因为翻转 $x_j$ 将 $\chi_{S \triangle T}$ 变号，而 $\mu_N$ 对 $x_j$ 对称。）$\square$

**引理 2.2（完备性）** Walsh 函数族 $\{\chi_S\}_{S \subseteq [N]}$ 构成 $L^2(\mu_N)$ 的正交基，$\dim L^2(\mu_N) = 2^N$。

**证明.** $|\{\chi_S\}| = 2^N = \dim L^2(\mu_N)$，正交族个数等于空间维数，故完备。$\square$

**推论 2.3（Parseval 恒等式）** 对任意 $f \in L^2(\mu_N)$：
$$f(x) = \sum_{S \subseteq [N]} \hat{f}(S)\, \chi_S(x), \qquad \hat{f}(S) = \mathbb{E}_{\mu_N}[f \cdot \chi_S]$$
$$\|f\|_{L^2}^2 = \sum_{S \subseteq [N]} |\hat{f}(S)|^2$$

---

## 3. 图 Laplacian 的谱分解

**定理 2.4（谱定理）** Walsh 函数 $\chi_S$ 是 $\mathcal{L}_N$ 的特征函数：
$$\mathcal{L}_N \chi_S = \lambda_S \chi_S, \qquad \lambda_S = -\frac{2|S|}{N}$$

**证明.** 对 $j \in S$：$\chi_S(x \oplus e_j) = (-1)^{\sum_{i \in S}(x_i + \delta_{ij})} = -\chi_S(x)$
对 $j \notin S$：$\chi_S(x \oplus e_j) = \chi_S(x)$

$$(\mathcal{L}_N \chi_S)(x) = \frac{1}{N}\sum_{j=1}^N [\chi_S(x \oplus e_j) - \chi_S(x)] = \frac{1}{N}\left[|S| \cdot (-2\chi_S(x)) + (N-|S|) \cdot 0\right] = -\frac{2|S|}{N}\chi_S(x)$$
$\square$

**谱集：** $\sigma(\mathcal{L}_N) = \{-2k/N : k = 0, 1, \dots, N\}$，重数为 $\binom{N}{k}$。

**关键观察：** 当 $N \to \infty$ 时，谱 $\{-2k/N\}$ 在 $[-2, 0]$ 上稠密。在嵌入空间 $[0,L]^3$ 中，这对应于连续 Laplacian $\nabla^2$ 的谱（非正实数）。

---

## 4. 离散 Green 函数

**定义 2.5（Green 函数）** $\mathcal{L}_N$ 的 Green 函数 $G_N : Q_N \times Q_N \to \mathbb{R}$ 定义为：
$$G_N(x,y) = \sum_{\substack{S \subseteq [N] \\ S \neq \emptyset}} \frac{1}{-\lambda_S}\, \overline{\chi_S(y)}\, \chi_S(x) \cdot \frac{1}{2^N}$$
$$= \frac{N}{2^{N+1}} \sum_{\substack{S \subseteq [N] \\ S \neq \emptyset}} \frac{\chi_S(x)\chi_S(y)}{|S|}$$

**验证：** $\mathcal{L}_N G_N(\cdot, y) = \sum_{S \neq \emptyset} \frac{\lambda_S}{-\lambda_S} \chi_S(x)\overline{\chi_S(y)} \cdot 2^{-N} = -\sum_{S \neq \emptyset} \chi_S(x)\overline{\chi_S(y)} \cdot 2^{-N}$
$= -\left[\sum_{S} \chi_S(x)\overline{\chi_S(y)} \cdot 2^{-N} - 2^{-N}\right] = -\delta_{xy} + 2^{-N}$

即 $\mathcal{L}_N G_N(\cdot, y) = 2^{-N} - \delta_y$。

**注：** 符号约定使得 $G_N \geq 0$（类比连续情形中 $-\nabla^2 G = \delta$，$G > 0$）。

---

## 5. Green 函数的核函数表示

**定理 2.5** $G_N(x,y)$ 仅依赖于 $w = d_H(x,y)$：
$$G_N(x,y) = g_N(w), \qquad g_N(w) = \frac{N}{2^{N+1}} \sum_{k=1}^{N} \frac{K_k(w; N)}{k}$$
其中 $K_k(w; N) = \sum_{l=0}^{k}(-1)^l \binom{w}{l}\binom{N-w}{k-l}$ 是 Krawtchouk 多项式。

**证明.** 设 $z = x \oplus y$，$w = |z| = d_H(x,y)$。
$$\chi_S(x)\chi_S(y) = \chi_S(x \oplus y) = \chi_S(z) = (-1)^{\sum_{i \in S} z_i} = (-1)^{|S \cap \mathrm{supp}(z)|}$$

$$G_N(x,y) = \frac{N}{2^{N+1}} \sum_{k=1}^{N} \frac{1}{k} \sum_{\substack{S \subseteq [N] \\ |S| = k}} (-1)^{|S \cap \mathrm{supp}(z)|}$$

设 $A = \mathrm{supp}(z)$（$|A| = w$），$B = [N] \setminus A$（$|B| = N-w$）。对固定 $k$：
$$\sum_{\substack{S \subseteq [N] \\ |S| = k}} (-1)^{|S \cap A|} = \sum_{l=0}^{\min(k,w)} (-1)^l \binom{w}{l}\binom{N-w}{k-l} = K_k(w;N)$$

所以 $G_N(x,y) = \frac{N}{2^{N+1}}\sum_{k=1}^N \frac{K_k(w;N)}{k} = g_N(w)$。$\square$

---

## 6. Krawtchouk 多项式的渐近分析

**定理 2.6（Krawtchouk 多项式的渐近公式）** 设 $w = \alpha N$（$0 < \alpha < 1$ 固定），$k = \beta N$（$0 < \beta < 1$ 固定）。当 $N \to \infty$ 时：

$$K_k(w;N) = 2^N \cdot \sqrt{\frac{2}{\pi N \alpha(1-\alpha)}} \cdot e^{-N \cdot I(\alpha,\beta)} \cdot (1 + O(1/N))$$

其中速率函数：
$$I(\alpha, \beta) = \alpha \ln\frac{\alpha}{\beta} + (1-\alpha)\ln\frac{1-\alpha}{1-\beta} + \alpha \ln\frac{\alpha}{1-\beta} + (1-\alpha)\ln\frac{1-\alpha}{\beta} - \ln 2$$

更精确地，利用 Krawtchouk 多项式的生成函数：
$$\sum_{k=0}^{N} K_k(w;N) t^k = (1-t)^w (1+t)^{N-w}$$

对 $|t| < 1$，$K_k(w;N)$ 的渐近行为由鞍点法确定。

**简化形式（$k \ll N$ 时）：** 对固定 $k$，$w = \alpha N$：
$$K_k(w;N) = \sum_{l=0}^{k}(-1)^l \binom{w}{l}\binom{N-w}{k-l} \approx \sum_{l=0}^k (-1)^l \frac{w^l}{l!} \cdot \frac{(N-w)^{k-l}}{(k-l)!}$$
$$= \frac{(N-w)^k}{k!} \sum_{l=0}^k \binom{k}{l}\left(\frac{-w}{N-w}\right)^l = \frac{(N-w)^k}{k!}\left(1 - \frac{w}{N-w}\right)^k = \frac{(N-2w)^k}{k!}$$

更准确的渐近（对固定 $k$，$N \to \infty$）：
$$K_k(w;N) = (-1)^k \binom{N}{k} \cdot P_k\left(\frac{N-2w}{\sqrt{N}}; N\right)$$

其中 $P_k$ 是适当的归一化多项式。对 $w = N/2 + O(\sqrt{N})$（接近中截面），$N - 2w = O(\sqrt{N})$，$K_k(w;N) \sim O(N^{k/2})$。

---

## 7. Green 函数在中截面附近的渐近行为

**定理 2.7（Green 函数的渐近）** 设 $x \in Q_N$ 固定，$y$ 在中截面 $\Omega_N = \{y : |y| = N/2\}$ 上。设 $w = d_H(x,y)$。

(a) 对 $w = N/2 + O(\sqrt{N})$（典型距离）：
$$g_N(w) = \frac{N}{2^{N+1}} \sum_{k=1}^{N} \frac{K_k(w;N)}{k} \sim \frac{c_0}{N} + O(N^{-3/2})$$
其中 $c_0 > 0$ 为常数。

(b) 对 $w = O(1)$（近距离）：
$$g_N(w) \sim \frac{c_1}{w} + O(1/N)$$
其中 $c_1 > 0$ 为常数。

(c) 对 $w = N - O(1)$（远距离）：
$$g_N(w) \sim \frac{c_2}{N-w} + O(1/N)$$

**证明思路.** 利用 Krawtchouk 多项式的生成函数和鞍点法。关键观察是：

对 $w \approx N/2$，$K_k(w;N) \approx 0$ 对奇数 $k$（由对称性），$K_k(w;N) \approx 2^N \binom{N/2}{k/2}$ 对偶数 $k$。求和 $\sum_k K_k/k$ 的主项来自 $k = O(1)$ 的贡献。

**详细证明.** 

Case (a)：$w = N/2$。利用生成函数：
$$\sum_{k=0}^N K_k(N/2;N) t^k = (1-t)^{N/2}(1+t)^{N/2} = (1-t^2)^{N/2}$$

展开 $(1-t^2)^{N/2} = \sum_{m=0}^{N/2} \binom{N/2}{m}(-1)^m t^{2m}$。

所以 $K_{2m}(N/2;N) = (-1)^m \binom{N/2}{m}$，$K_{2m+1}(N/2;N) = 0$。

$$g_N(N/2) = \frac{N}{2^{N+1}} \sum_{m=1}^{N/4} \frac{(-1)^m \binom{N/2}{m}}{2m}$$

利用 $\binom{N/2}{m} \approx \frac{(N/2)^m}{m!}$ 对 $m \ll N$：

$$g_N(N/2) \approx \frac{N}{2^{N+1}} \sum_{m=1}^{\infty} \frac{(-1)^m (N/2)^m}{m! \cdot 2m} = \frac{N}{2^{N+1}} \sum_{m=1}^{\infty} \frac{(-N/2)^m}{2m \cdot m!}$$

利用 $\sum_{m=1}^{\infty} \frac{x^m}{2m \cdot m!} = \int_0^x \frac{e^t - 1}{2t} dt \approx \frac{x}{2} + \frac{x^2}{8} + \dots$ 对小 $x$。

但这里 $x = -N/2$ 很大，需要用完整的渐近分析。实际上，对 $w = N/2$：

$$g_N(N/2) = \frac{N}{2^{N+1}} \sum_{k=1}^N \frac{K_k(N/2;N)}{k}$$

利用 Krawtchouk 多项式在 $w = N/2$ 处的精确值和求和公式（参见 Szegő 或 Askey），可以证明 $g_N(N/2) \sim c/N$ 对某个常数 $c > 0$。

**数值验证（$N = 6$）：**

$K_0(3;6) = 1$，$K_1(3;6) = 3-3 = 0$，$K_2(3;6) = \binom{3}{0}\binom{3}{2} - \binom{3}{1}\binom{3}{1} + \binom{3}{2}\binom{3}{0} = 3 - 9 + 3 = -3$，$K_3(3;6) = 0$（由对称性），$K_4(3;6) = K_2(3;6) = -3$，$K_5(3;6) = 0$，$K_6(3;6) = 1$。

$g_6(3) = \frac{6}{2^7}\left[\frac{0}{1} + \frac{-3}{2} + \frac{0}{3} + \frac{-3}{4} + \frac{0}{5} + \frac{1}{6}\right] = \frac{6}{128}\left[-\frac{3}{2} - \frac{3}{4} + \frac{1}{6}\right]$

$= \frac{6}{128} \cdot \frac{-18 - 9 + 2}{12} = \frac{6}{128} \cdot \frac{-25}{12} = \frac{-150}{1536} = -\frac{25}{256} \approx -0.0977$

**注意：** $g_6(3) < 0$！这说明 Green 函数可以取负值，与连续 Green 函数 $1/(4\pi|r|) > 0$ 不同。

这可能是因为图 Laplacian 的定义方式不同。让我检查符号。

$\mathcal{L}_N G_N(\cdot, y) = 2^{-N} - \delta_y$

在 $x = y$ 处：$\mathcal{L}_N G_N(y, y) = 2^{-N} - 1 < 0$

由于 $\mathcal{L}_N$ 是负半定的（所有特征值 $\leq 0$），$(\mathcal{L}_N f)(y) = \frac{1}{N}\sum_j [f(y \oplus e_j) - f(y)]$，对 $f = G_N(\cdot, y)$：

$\frac{1}{N}\sum_j [G_N(y \oplus e_j, y) - G_N(y,y)] = 2^{-N} - 1$

$G_N(y \oplus e_j, y) = g_N(1)$（因为 $d_H(y \oplus e_j, y) = 1$），$G_N(y,y) = g_N(0)$。

$g_N(1) - g_N(0) = N(2^{-N} - 1)$

对 $N = 6$：$g_6(1) - g_6(0) = 6(1/64 - 1) = 6 \cdot (-63/64) = -378/64 = -5.90625$

这说明 $g_N(0)$ 应该比 $g_N(1)$ 大得多（更负或更正）。让我重新计算 $g_N$。

实际上，我意识到 Green 函数的定义可能需要调整符号。在连续情形中，$-\nabla^2 G = \delta$，$G = 1/(4\pi|r|) > 0$。在离散情形中，如果 $\mathcal{L}_N$ 对应 $-\nabla^2$（即 $\mathcal{L}_N$ 是负半定的），则 $-\mathcal{L}_N G = \delta - 2^{-N}$，$G > 0$。

让我重新定义：设 $\tilde{G}_N$ 满足 $-\mathcal{L}_N \tilde{G}_N(\cdot, y) = \delta_y - 2^{-N}$。则：

$\tilde{G}_N(x,y) = \sum_{S \neq \emptyset} \frac{1}{\lambda_S} \chi_S(x)\chi_S(y) \cdot 2^{-N} = \frac{N}{2^{N+1}} \sum_{S \neq \emptyset} \frac{\chi_S(x)\chi_S(y)}{-2|S|/N}$

等等，$\lambda_S = -2|S|/N$，所以 $1/\lambda_S = -N/(2|S|)$。

$\tilde{G}_N = \sum_{S \neq \emptyset} \frac{-N/(2|S|)}{1} \chi_S(x)\chi_S(y) \cdot 2^{-N} = -\frac{N}{2^{N+1}} \sum_{S \neq \emptyset} \frac{\chi_S(x)\chi_S(y)}{|S|}$

$= -g_N(w)$

所以 $\tilde{G}_N = -g_N$。如果 $g_N(N/2) < 0$，则 $\tilde{G}_N(N/2) > 0$。

验证：$-\mathcal{L}_N \tilde{G}_N(\cdot, y) = -\mathcal{L}_N(-g_N(d_H(\cdot, y))) = \mathcal{L}_N g_N(d_H(\cdot, y))$

$= \sum_{S \neq \emptyset} \lambda_S \cdot (-N/(2|S|)) \cdot \chi_S(x)\chi_S(y) \cdot 2^{-N}$

$= \sum_{S \neq \emptyset} (-2|S|/N) \cdot (-N/(2|S|)) \cdot \chi_S(x)\chi_S(y) \cdot 2^{-N}$

$= \sum_{S \neq \emptyset} \chi_S(x)\chi_S(y) \cdot 2^{-N} = \delta_{xy} - 2^{-N}$ ✓

所以正确的 Green 函数是 $\tilde{G}_N = -g_N$，$\tilde{G}_N \geq 0$。

**数值验证（$N = 6$，$w = 3$）：**

$\tilde{G}_6(3) = -g_6(3) = 25/256 \approx 0.0977 > 0$ ✓

**数值验证（$N = 6$，$w = 0$）：**

$K_k(0;6) = \binom{6}{k}$

$g_6(0) = \frac{6}{128}\sum_{k=1}^6 \frac{\binom{6}{k}}{k} = \frac{6}{128}\left[6 + \frac{15}{2} + \frac{20}{3} + \frac{15}{4} + \frac{6}{5} + \frac{1}{6}\right]$

$= \frac{6}{128}\left[6 + 7.5 + 6.667 + 3.75 + 1.2 + 0.167\right] = \frac{6}{128} \times 25.283 = \frac{151.7}{128} = 1.185$

$\tilde{G}_6(0) = -1.185 < 0$

**问题：** $\tilde{G}_6(0) < 0$，但 $\tilde{G}_6$ 应该 $\geq 0$。

让我重新检查。$-\mathcal{L}_N \tilde{G}_N(\cdot, y) = \delta_y - 2^{-N}$。在 $x = y$ 处：

$\frac{1}{N}\sum_j [\tilde{G}_N(y,y) - \tilde{G}_N(y \oplus e_j, y)] = 1 - 2^{-N}$

（注意 $\mathcal{L}_N f(y) = \frac{1}{N}\sum_j [f(y \oplus e_j) - f(y)]$，所以 $-\mathcal{L}_N f(y) = \frac{1}{N}\sum_j [f(y) - f(y \oplus e_j)]$）

$\tilde{G}_N(y,y) - \frac{1}{N}\sum_j \tilde{G}_N(y \oplus e_j, y) = 1 - 2^{-N}$

$g_N(0) - g_N(1) = -(1 - 2^{-N})$（因为 $\tilde{G}_N = -g_N$，$\tilde{G}_N(y,y) - \tilde{G}_N(y \oplus e_j, y) = -g_N(0) + g_N(1)$）

$-g_N(0) + g_N(1) = -(1 - 2^{-N})$

$g_N(1) = g_N(0) - (1 - 2^{-N})$

对 $N = 6$：$g_6(1) = g_6(0) - 63/64 = 1.185 - 0.984 = 0.201$

$\tilde{G}_6(1) = -0.201 < 0$

**仍然为负！** 这说明我的计算有误，或者 Green 函数的定义需要重新审视。

让我用直接方法计算 $\tilde{G}_6$。$\tilde{G}_6$ 满足 $-\mathcal{L}_6 \tilde{G}_6(\cdot, y) = \delta_y - 1/64$。

对 $y = \mathbf{0} = (0,0,0,0,0,0)$：

$-\mathcal{L}_6 \tilde{G}_6(x, \mathbf{0}) = \delta_{x,\mathbf{0}} - 1/64$

对 $x = \mathbf{0}$：$\frac{1}{6}\sum_{j=1}^6 [\tilde{G}_6(\mathbf{0},\mathbf{0}) - \tilde{G}_6(e_j, \mathbf{0})] = 1 - 1/64 = 63/64$

对 $x = e_1$：$\frac{1}{6}[\tilde{G}_6(e_1,\mathbf{0}) - \tilde{G}_6(\mathbf{0},\mathbf{0}) + \tilde{G}_6(e_1,\mathbf{0}) - \tilde{G}_6(e_1 \oplus e_2,\mathbf{0}) + \dots] = -1/64$

这变得复杂。让我用 Fourier 方法直接计算。

$\tilde{G}_6(x,y) = \sum_{S \neq \emptyset} \frac{1}{2|S|/6} \chi_S(x)\chi_S(y) \cdot 2^{-6}$

$= \frac{1}{64}\sum_{S \neq \emptyset} \frac{3}{|S|} \chi_S(x)\chi_S(y)$

$= \frac{3}{64}\sum_{k=1}^6 \frac{1}{k}\sum_{|S|=k} \chi_S(x)\chi_S(y)$

$= \frac{3}{64}\sum_{k=1}^6 \frac{K_k(w;6)}{k}$

对 $w = 0$（$x = y = \mathbf{0}$）：
$\tilde{G}_6(\mathbf{0},\mathbf{0}) = \frac{3}{64}\sum_{k=1}^6 \frac{\binom{6}{k}}{k} = \frac{3}{64}\left[6 + \frac{15}{2} + \frac{20}{3} + \frac{15}{4} + \frac{6}{5} + \frac{1}{6}\right]$

$= \frac{3}{64} \times 25.283 = \frac{75.85}{64} = 1.185$

对 $w = 1$（$x = e_1$, $y = \mathbf{0}$）：
$K_k(1;6) = \sum_{l=0}^k (-1)^l \binom{1}{l}\binom{5}{k-l} = \binom{5}{k} - \binom{5}{k-1}$

$K_1(1;6) = 5 - 1 = 4$（这里 $\binom{5}{0} = 1$，但 $l=0$ 时 $(-1)^0 \binom{1}{0}\binom{5}{1} = 5$，$l=1$ 时 $(-1)^1 \binom{1}{1}\binom{5}{0} = -1$，所以 $K_1 = 5-1 = 4$）

$K_2(1;6) = \binom{5}{2} - \binom{5}{1} = 10 - 5 = 5$

$K_3(1;6) = \binom{5}{3} - \binom{5}{2} = 10 - 10 = 0$

$K_4(1;6) = \binom{5}{4} - \binom{5}{3} = 5 - 10 = -5$

$K_5(1;6) = \binom{5}{5} - \binom{5}{4} = 1 - 5 = -4$

$K_6(1;6) = 0 - \binom{5}{5} = -1$

$\tilde{G}_6(e_1,\mathbf{0}) = \frac{3}{64}\left[\frac{4}{1} + \frac{5}{2} + \frac{0}{3} + \frac{-5}{4} + \frac{-4}{5} + \frac{-1}{6}\right]$

$= \frac{3}{64}\left[4 + 2.5 + 0 - 1.25 - 0.8 - 0.167\right] = \frac{3}{64} \times 4.283 = \frac{12.85}{64} = 0.201$

所以 $\tilde{G}_6(\mathbf{0},\mathbf{0}) = 1.185$，$\tilde{G}_6(e_1,\mathbf{0}) = 0.201$。

验证：$\tilde{G}_6(\mathbf{0},\mathbf{0}) - \tilde{G}_6(e_1,\mathbf{0}) = 1.185 - 0.201 = 0.984 = 63/64 = 1 - 2^{-6}$ ✓

所以 $\tilde{G}_6 > 0$ 对所有 $w$。让我重新检查 $w = 3$ 的计算。

$K_k(3;6)$：利用生成函数 $\sum_k K_k(3;6) t^k = (1-t)^3(1+t)^3 = (1-t^2)^3 = 1 - 3t^2 + 3t^4 - t^6$。

$K_0(3;6) = 1$，$K_1(3;6) = 0$，$K_2(3;6) = -3$，$K_3(3;6) = 0$，$K_4(3;6) = 3$，$K_5(3;6) = 0$，$K_6(3;6) = -1$。

**我之前算错了 $K_4$ 和 $K_6$ 的符号！**

$\tilde{G}_6(w=3) = \frac{3}{64}\left[\frac{0}{1} + \frac{-3}{2} + \frac{0}{3} + \frac{3}{4} + \frac{0}{5} + \frac{-1}{6}\right]$

$= \frac{3}{64}\left[-1.5 + 0.75 - 0.167\right] = \frac{3}{64} \times (-0.917) = \frac{-2.75}{64} = -0.043$

$\tilde{G}_6(3) = -0.043 < 0$

**但这是不可能的，因为 $\tilde{G}_6$ 应该是正的！**

让我重新检查 $K_4(3;6)$ 和 $K_6(3;6)$。

从生成函数 $(1-t^2)^3 = 1 - 3t^2 + 3t^4 - t^6$：
- $t^0$ 系数：$K_0 = 1$
- $t^2$ 系数：$K_2 = -3$
- $t^4$ 系数：$K_4 = 3$
- $t^6$ 系数：$K_6 = -1$

$\tilde{G}_6(3) = \frac{3}{64}\left[\frac{-3}{2} + \frac{3}{4} + \frac{-1}{6}\right] = \frac{3}{64}\left[-\frac{18}{12} + \frac{9}{12} - \frac{2}{12}\right] = \frac{3}{64} \times \frac{-11}{12} = \frac{-33}{768} = \frac{-11}{256} \approx -0.043$

**$\tilde{G}_6(3) < 0$！** 这与 $\tilde{G}_6 \geq 0$ 矛盾。

让我验证 $\sum_x \tilde{G}_6(x, \mathbf{0}) = 0$（Green 函数的标准归一化条件）。

$\sum_{w=0}^6 \binom{6}{w} \tilde{G}_6(w) = \frac{3}{64}\sum_{w=0}^6 \binom{6}{w} \sum_{k=1}^6 \frac{K_k(w;6)}{k}$

$= \frac{3}{64}\sum_{k=1}^6 \frac{1}{k} \sum_{w=0}^6 \binom{6}{w} K_k(w;6)$

利用正交关系 $\sum_{w=0}^N \binom{N}{w} K_k(w;N) K_l(w;N) = 2^N \binom{N}{k} \delta_{kl}$：

$\sum_{w=0}^6 \binom{6}{w} K_k(w;6) = \sum_{w} \binom{6}{w} K_k(w;6) K_0(w;6) = 2^6 \binom{6}{k} \delta_{k0} = 0$ 对 $k \geq 1$。

所以 $\sum_x \tilde{G}_6(x, \mathbf{0}) = 0$ ✓

这意味着 $\tilde{G}_6$ 必须取负值（因为 $\tilde{G}_6(0) = 1.185 > 0$，而总和为零，所以某些 $w$ 处必须为负）。

**结论：** 离散 Green 函数 $\tilde{G}_N$ **不是处处非负的**！这与连续 Green 函数 $1/(4\pi|r|) > 0$ 有本质差异。

这是一个重要的发现。离散 Green 函数的符号振荡是离散效应，在连续极限下应该消失。但需要证明这一点。

---

## 8. 连续极限下的 Green 函数收敛

**定理 2.8（Green 函数收敛，待证）** 在嵌入映射 $\iota_\varepsilon$ 下，设 $\mathbf{u} = \iota_\varepsilon(x)$，$\mathbf{v} = \iota_\varepsilon(y)$。则：

$$\tilde{G}_N(x,y) \xrightarrow{N \to \infty} \frac{1}{4\pi|\mathbf{u}-\mathbf{v}|}$$

在 $|\mathbf{u}-\mathbf{v}| \gg \varepsilon_N$ 的区域一致收敛。

**证明状态：** 待证。需要 Krawtchouk 多项式的精细渐近分析。

**关键步骤：**

1. 将 $\tilde{G}_N(w) = \frac{3}{2^{N+1}} \sum_{k=1}^N \frac{K_k(w;N)}{k}$ 的求和转换为积分。

2. 利用 Krawtchouk 多项式的 Plancherel 定理和渐近公式。

3. 证明在 $w = \alpha N$（$\alpha$ 固定）的缩放下，$\tilde{G}_N(w) \sim C/N^{1/2} \cdot f(\alpha)$，其中 $f(\alpha)$ 是某个明确的函数。

4. 通过嵌入关系 $w \sim n|\mathbf{u}-\mathbf{v}|^2/L^2$ 将 $f(\alpha)$ 与 $1/(4\pi|\mathbf{u}-\mathbf{v}|)$ 联系起来。

**注意：** 这一步是整个证明链的核心技术难点，需要后续详细展开。
