# 定理 3：Krawtchouk 渐近与 Green 函数收敛

## 1. Krawtchouk-Hermite 渐近公式

**定理 3.1（Meixner 渐近，参见 Szegő §5.41）** 设 $x = N/2 + \xi\sqrt{N}/2$，$0 < \alpha < 1$ 固定，$k = \alpha N$。则：

$$K_{\alpha N}\left(\frac{N}{2} + \frac{\xi\sqrt{N}}{2}; N\right) = (-1)^{\alpha N} \cdot 2^N \cdot \sqrt{\frac{2}{\pi N}} \cdot \frac{H_{\alpha N}(\xi/\sqrt{2})}{(\alpha N)!} \cdot 2^{\alpha N/2} \cdot (1 + O(N^{-1/2}))$$

其中 $H_n$ 是 Hermite 多项式。

**更实用的形式（固定 $k$，$N \to \infty$）：** 对固定 $k \in \mathbb{N}$，$w = N/2 + t\sqrt{N}$（$t = O(1)$）：

$$K_k(w; N) = \sum_{l=0}^{k}(-1)^l \binom{w}{l}\binom{N-w}{k-l}$$

利用 $\binom{N/2 + t\sqrt{N}}{l} \approx \frac{(N/2)^l}{l!}\left(1 + \frac{2lt}{\sqrt{N}} + O(1/N)\right)$：

$$K_k(w;N) \approx \sum_{l=0}^k (-1)^l \frac{(N/2)^k}{l!(k-l)!}\left[1 + \frac{2lt}{\sqrt{N}} - \frac{2(k-l)t}{\sqrt{N}} + O(1/N)\right]$$

$$= \frac{(N/2)^k}{k!}\sum_{l=0}^k \binom{k}{l}(-1)^l \left[1 + \frac{2(2l-k)t}{\sqrt{N}} + O(1/N)\right]$$

$$= \frac{(N/2)^k}{k!}\left[\underbrace{(1-1)^k}_{= 0 \text{ if } k \geq 1} + \frac{2t}{\sqrt{N}}\sum_{l=0}^k \binom{k}{l}(-1)^l(2l-k) + O(1/N)\right]$$

对 $k \geq 1$，$(1-1)^k = 0$。计算 $\sum_l \binom{k}{l}(-1)^l(2l-k)$：

$= 2\sum_l l\binom{k}{l}(-1)^l - k\sum_l \binom{k}{l}(-1)^l = 2 \cdot k(1-1)^{k-1}(-1) - k \cdot 0$

对 $k = 1$：$= 2 \cdot 1 \cdot (-1) = -2$。对 $k \geq 2$：$= 2k \cdot (-1)^1 \cdot (1-1)^{k-1} = 0$（当 $k \geq 2$ 时 $(1-1)^{k-1} = 0$）。

**更精确地，利用生成函数方法。**

生成函数：$\sum_{k=0}^N K_k(w;N) t^k = (1-t)^w(1+t)^{N-w}$

设 $w = N/2 + s$，$s = t_0 \sqrt{N}$（$t_0 = O(1)$）：

$(1-t)^{N/2+s}(1+t)^{N/2-s} = [(1-t)(1+t)]^{N/2} \cdot \left(\frac{1-t}{1+t}\right)^s$

$= (1-t^2)^{N/2} \cdot \exp\left(s \ln\frac{1-t}{1+t}\right) = (1-t^2)^{N/2} \cdot \exp\left(-2s\left[t + \frac{t^3}{3} + \frac{t^5}{5} + \dots\right]\right)$

设 $t = u/\sqrt{N}$：

$(1-u^2/N)^{N/2} \to e^{-u^2/2}$

$\exp\left(-2s\left[\frac{u}{\sqrt{N}} + \frac{u^3}{3N^{3/2}} + \dots\right]\right) = \exp\left(-\frac{2su}{\sqrt{N}} + O(N^{-1})\right) = \exp(-2t_0 u + O(N^{-1}))$

所以：
$$\sum_{k=0}^N K_k(N/2 + t_0\sqrt{N}; N) \frac{u^k}{N^{k/2}} \to e^{-u^2/2 - 2t_0 u} = e^{-(u+t_0)^2/2 + t_0^2} \cdot e^{-t_0^2}$$

等等，$e^{-u^2/2 - 2t_0 u} = e^{-(u+2t_0)^2/2 + 2t_0^2}$。

设 $v = u + 2t_0$：$= e^{-v^2/2 + 2t_0^2}$。

这意味着 $K_k(N/2 + t_0\sqrt{N}; N)$ 在 $k$ 固定、$N \to \infty$ 时的行为由 Hermite 多项式控制。

**精确渐近（$k$ 固定，$N \to \infty$）：**

$$K_k(N/2 + t_0\sqrt{N}; N) = \frac{(-N)^k}{2^k k!} H_k(t_0\sqrt{2}) + O(N^{k-1/2})$$

其中 $H_k$ 是概率论 Hermite 多项式（$H_0 = 1$，$H_1 = x$，$H_2 = x^2 - 1$，$H_3 = x^3 - 3x$，...）。

**验证（$k = 1$）：**
$K_1(w;N) = N - 2w = -2t_0\sqrt{N}$
$(-N)^1/(2 \cdot 1!) \cdot H_1(t_0\sqrt{2}) = -N/2 \cdot t_0\sqrt{2} = -t_0 N/\sqrt{2}$

不匹配。让我修正系数。

实际上，利用精确公式 $K_1(w;N) = N - 2w = -2s = -2t_0\sqrt{N}$，和 $H_1(x) = x$：

$K_1 = -2t_0\sqrt{N}$，而 $(-N)/(2) \cdot t_0\sqrt{2} = -t_0\sqrt{2}N/2$。

需要 $-2t_0\sqrt{N} = c \cdot N \cdot t_0\sqrt{2}$，即 $c = -2\sqrt{N}/(N\sqrt{2}) = -\sqrt{2}/\sqrt{N}$。

所以 $K_1 = -\sqrt{2/N} \cdot N \cdot H_1(t_0\sqrt{2}) + O(1) = -\sqrt{2N} \cdot t_0\sqrt{2} + O(1) = -2t_0\sqrt{N} + O(1)$ ✓

**正确的渐近公式：** 对固定 $k$，$w = N/2 + t_0\sqrt{N}$：

$$K_k(w;N) = \left(-\sqrt{\frac{N}{2}}\right)^k \frac{H_k(t_0\sqrt{2})}{k!} + O(N^{(k-1)/2})$$

其中 $H_k$ 是概率论 Hermite 多项式。

---

## 2. Green 函数在中截面附近的渐近

**定理 3.2** 设 $x, y \in Q_N$，$w = d_H(x,y) = N/2 + t_0\sqrt{N}$（$t_0 = O(1)$）。则：

$$\tilde{G}_N(x,y) = \frac{3}{2^{N+1}} \sum_{k=1}^{N} \frac{K_k(w;N)}{k}$$

$$= \frac{3}{2^{N+1}} \left[\sum_{k=1}^{K_0} \frac{K_k(w;N)}{k} + \sum_{k=K_0+1}^{N} \frac{K_k(w;N)}{k}\right]$$

对固定截断 $K_0$，第一项的渐近由 Hermite 多项式给出：

$$\sum_{k=1}^{K_0} \frac{K_k(w;N)}{k} = \sum_{k=1}^{K_0} \frac{(-\sqrt{N/2})^k H_k(t_0\sqrt{2})}{k \cdot k!} + O(N^{(K_0-1)/2})$$

**问题：** 这个求和的主项随 $K_0$ 增长，而 $K_0$ 可以取到 $O(N)$。需要对所有 $k$ 求和。

---

## 3. 完整求和的渐近

**定理 3.3（Green 函数的缩放极限）** 设 $w = N/2 + t_0\sqrt{N}$。则：

$$\tilde{G}_N(w) = \frac{3}{2^{N+1}} \sum_{k=1}^N \frac{K_k(w;N)}{k} = \frac{3}{\sqrt{2\pi N}} \int_0^\infty \frac{e^{-u^2/2} \cdot e^{-2t_0 u}}{u}\,du + O(N^{-1})$$

**证明.** 利用生成函数和 Mellin 变换技巧。

$\sum_{k=1}^N \frac{K_k(w;N)}{k} = \sum_{k=1}^N \frac{1}{k} [z^k](1-z)^w(1+z)^{N-w}$

其中 $[z^k]$ 表示 $z^k$ 的系数提取。利用 $\frac{1}{k} = \int_0^1 z^{k-1}\,dz$：

$$\sum_{k=1}^N \frac{K_k(w;N)}{k} = \sum_{k=1}^N \int_0^1 z^{k-1}\,dz \cdot [z^k](1-z)^w(1+z)^{N-w}$$

$$= \int_0^1 \frac{1}{z} \sum_{k=1}^N z^k [z^k](1-z)^w(1+z)^{N-w}\,dz$$

$$= \int_0^1 \frac{(1-z)^w(1+z)^{N-w} - 1}{z}\,dz$$

（减去 $k=0$ 项 $K_0 = 1$ 的贡献。）

设 $w = N/2 + s$，$s = t_0\sqrt{N}$：

$(1-z)^{N/2+s}(1+z)^{N/2-s} = (1-z^2)^{N/2} \cdot \left(\frac{1-z}{1+z}\right)^s$

设 $z = u/\sqrt{N}$（$u \in [0, \sqrt{N}]$）：

$(1-u^2/N)^{N/2} \approx e^{-u^2/2}$

$\frac{1-z}{1+z} = \frac{1-u/\sqrt{N}}{1+u/\sqrt{N}} \approx 1 - \frac{2u}{\sqrt{N}} + O(1/N)$

$\left(\frac{1-z}{1+z}\right)^s \approx \exp\left(s \cdot \left(-\frac{2u}{\sqrt{N}}\right)\right) = e^{-2t_0 u}$

$dz = du/\sqrt{N}$

$$\sum_{k=1}^N \frac{K_k(w;N)}{k} \approx \int_0^{\sqrt{N}} \frac{e^{-u^2/2 - 2t_0 u} - 1}{u/\sqrt{N}} \cdot \frac{du}{\sqrt{N}} = \int_0^{\sqrt{N}} \frac{e^{-u^2/2 - 2t_0 u} - 1}{u}\,du$$

当 $\sqrt{N} \to \infty$：

$$\to \int_0^{\infty} \frac{e^{-u^2/2 - 2t_0 u} - 1}{u}\,du$$

注意积分在 $u = 0$ 处有可去奇点（被积函数在 $u \to 0$ 时趋于 $-2t_0$），在 $u \to \infty$ 时趋于 $-1/u$（积分发散！）。

**发散问题：** $\int_1^\infty \frac{-1}{u}\,du = -\infty$。

这说明直接替换 $z = u/\sqrt{N}$ 不够精细。需要更仔细的分析。

**修正：** 利用恒等式 $\frac{1}{k} = \int_0^\infty e^{-kt}\,dt$：

$$\sum_{k=1}^N \frac{K_k(w;N)}{k} = \int_0^\infty \sum_{k=1}^N K_k(w;N) e^{-kt}\,dt$$

$$= \int_0^\infty \left[(1-e^{-t})^w(1+e^{-t})^{N-w} - 1\right]\,dt$$

设 $e^{-t} = z$，$t = -\ln z$，$dt = -dz/z$：

$$= \int_0^1 \frac{(1-z)^w(1+z)^{N-w} - 1}{z}\,dz$$

这与之前的表达式相同。问题在于被积函数在 $z \to 0$ 时趋于 $0$（因为 $(1-z)^w(1+z)^{N-w} \to 1$），所以积分在 $z = 0$ 处收敛。在 $z = 1$ 处，$(1-z)^w \to 0$（当 $w > 0$），$(1+z)^{N-w} \to 2^{N-w}$，所以被积函数趋于 $-1/1 = -1$。积分 $\int_0^1 (-1)\,dz = -1$ 是有限的。

**重新分析：**

$$I = \int_0^1 \frac{(1-z)^w(1+z)^{N-w} - 1}{z}\,dz$$

对 $z$ 小的区域（$z = O(1/\sqrt{N})$）用鞍点展开，对 $z$ 大的区域用精确估计。

设 $f(z) = (1-z)^w(1+z)^{N-w} = e^{w\ln(1-z) + (N-w)\ln(1+z)}$。

$\ln f(z) = w\ln(1-z) + (N-w)\ln(1+z)$

$\approx w(-z - z^2/2) + (N-w)(z - z^2/2)$

$= (N-2w)z - Nz^2/2$

$= -2sz - Nz^2/2$（其中 $s = w - N/2 = t_0\sqrt{N}$）

$= -2t_0\sqrt{N}z - Nz^2/2$

设 $z = u/\sqrt{N}$：

$\ln f = -2t_0 u - u^2/2$

$f = e^{-2t_0 u - u^2/2}$

$\frac{f - 1}{z} = \frac{e^{-2t_0 u - u^2/2} - 1}{u/\sqrt{N}}$

$dz = du/\sqrt{N}$

$I \approx \int_0^{\sqrt{N}} \frac{e^{-2t_0 u - u^2/2} - 1}{u/\sqrt{N}} \cdot \frac{du}{\sqrt{N}} = \int_0^{\sqrt{N}} \frac{e^{-2t_0 u - u^2/2} - 1}{u}\,du$

当 $\sqrt{N} \to \infty$，$e^{-u^2/2} \to 0$ 对大 $u$，所以：

$I \to \int_0^{\infty} \frac{e^{-2t_0 u - u^2/2} - 1}{u}\,du$

在 $u = 0$ 处：$e^0 - 1 = 0$，$\frac{e^{-2t_0 u - u^2/2} - 1}{u} \to -2t_0$（可去奇点）。

在 $u \to \infty$ 处：$e^{-u^2/2} \to 0$，$\frac{-1}{u}$，积分 $\int_1^\infty \frac{-1}{u}\,du$ 发散！

**但原始积分 $I$ 是有限的！** 这说明鞍点近似在大 $z$ 区域不适用。

**正确的处理：** 将积分分成两部分：

$I = \int_0^{1/\sqrt{N}} \frac{f-1}{z}\,dz + \int_{1/\sqrt{N}}^1 \frac{f-1}{z}\,dz = I_1 + I_2$

$I_1$ 用鞍点展开：$I_1 \approx \int_0^1 \frac{e^{-2t_0 u - u^2/2} - 1}{u}\,du$（截断到 $u = \sqrt{N} \cdot 1/\sqrt{N} = 1$）

$I_2$ 用 $f(z) = O((1-z)^w)$ 的衰减：对 $z > 1/\sqrt{N}$，$f(z) \to 0$ 指数快，$I_2 \approx -\int_{1/\sqrt{N}}^1 \frac{1}{z}\,dz = -\ln\sqrt{N} = -\frac{1}{2}\ln N$

**所以：** $I \approx \int_0^1 \frac{e^{-2t_0 u - u^2/2} - 1}{u}\,du - \frac{1}{2}\ln N + O(1)$

**这意味着 $\sum_k K_k/k$ 的主项是 $-\frac{1}{2}\ln N$！**

$$\tilde{G}_N(w) = \frac{3}{2^{N+1}} \left[-\frac{1}{2}\ln N + O(1)\right]$$

但这给出 $\tilde{G}_N \to 0$ 指数快（因为 $2^{N+1}$ 在分母），这不是 $1/r$ 的行为。

**问题出在归一化。** $2^{N+1}$ 的因子来自于 Walsh 展开的归一化。在嵌入空间中，需要将 $\tilde{G}_N$ 乘以适当的缩放因子。

**正确的缩放：** 离散 Green 函数 $\tilde{G}_N$ 的连续类比是 $G_N \cdot V_N$，其中 $V_N = 2^N$ 是 $Q_N$ 的"体积"。所以：

$$\hat{G}_N := 2^N \cdot \tilde{G}_N = \frac{3 \cdot 2^N}{2^{N+1}} \sum_{k=1}^N \frac{K_k(w;N)}{k} = \frac{3}{2} \sum_{k=1}^N \frac{K_k(w;N)}{k}$$

$\hat{G}_N(w) = \frac{3}{2} I(w)$，其中 $I(w) = \int_0^1 \frac{(1-z)^w(1+z)^{N-w} - 1}{z}\,dz$

对 $w = N/2 + t_0\sqrt{N}$：$I \approx -\frac{1}{2}\ln N + C(t_0)$

$\hat{G}_N \approx -\frac{3}{4}\ln N + \frac{3}{2}C(t_0)$

**这仍然不是 $1/r$ 的行为。** 离散 Green 函数的渐近是对数型的（在三维中连续 Green 函数是 $1/r$，但离散版本在高维超立方体上的行为不同）。

---

## 4. 诊断：嵌入维数与有效维数的关系

**关键洞察：** 超立方体 $\{0,1\}^N$ 的图论维数是 $N$（每个节点有 $N$ 个邻居），但嵌入空间是三维的。Green 函数的行为取决于图的维数，而非嵌入空间的维数。

在 $N$ 维超立方体上，随机游走的 Green 函数的行为是：
- 对 $N \geq 3$：$G_N(w) \sim C_N$（有界，不随距离增长）
- 对 $N = 2$：$G_N(w) \sim \ln d_H$（对数增长）
- 对 $N = 1$：$G_N(w) \sim d_H$（线性增长）

这与连续空间中 $\mathbb{R}^d$ 上 Green 函数的行为一致：
- $d \geq 3$：$G \sim 1/r^{d-2}$
- $d = 2$：$G \sim \ln r$
- $d = 1$：$G \sim r$

**所以 $\{0,1\}^N$ 上的 Green 函数行为对应 $N$ 维空间，而非三维！**

将 $N$ 维离散结构嵌入三维连续空间后，Green 函数不会收敛到三维的 $1/r$。它会收敛到 $N$ 维的 $1/r^{N-2}$（在嵌入空间中），但由于 $N \to \infty$，这个行为变得非常奇异。

**这是整个"从离散到连续"证明策略的根本困难。**

---

## 5. 正确的物理解释

WorldBase 框架的物理图像是：
1. 离散比特空间 $\{0,1\}^N$ 是基本的
2. 三维连续空间是宏观涌现的
3. 引力势 $\Phi \propto -1/r$ 是宏观有效描述

**正确的数学路径不是**证明离散 Green 函数收敛到连续 Green 函数，而是：

**证明宏观平均势（在三维嵌入空间中对微观自由度求平均后）满足三维 Poisson 方程。**

这需要：
1. 定义正确的宏观平均操作（在嵌入空间中对块内自由度求平均）
2. 证明宏观平均后的势场满足有效方程
3. 确定有效方程的形式

**这正是均匀化理论（homogenization theory）的思路。**

---

## 6. 均匀化路径

**设定：** 在 $\{0,1\}^N$ 上定义势场 $\Phi_N$，通过嵌入 $\iota_\varepsilon$ 将其视为 $[0,L]^3$ 上格点函数。在宏观尺度 $\delta \gg \varepsilon_N$ 上求平均，得到宏观势 $\bar{\Phi}_N$。

**均匀化定理的框架（参见 Jikov-Kozlov-Oleinik）：**

设 $A^\varepsilon(x)$ 是周期为 $\varepsilon$ 的系数矩阵，$\nabla \cdot (A^\varepsilon \nabla u^\varepsilon) = f$。当 $\varepsilon \to 0$ 时，$u^\varepsilon \to u^0$，其中 $u^0$ 满足 $\nabla \cdot (A^0 \nabla u^0) = f$，$A^0$ 是均匀化系数。

**在 WorldBase 的语境中：**
- "周期结构"是块嵌入的格点结构
- "系数矩阵"由公理 A1-A9 确定的转移权重决定
- "均匀化极限"给出宏观有效方程

**关键问题：** 离散势场 $\Phi_N$ 是否满足某个离散 PDE（在 $\{0,1\}^N$ 上），使得该 PDE 在嵌入空间中的均匀化极限给出 Poisson 方程？

**答案取决于 $\Phi_N$ 的定义方式。** 如果 $\Phi_N$ 定义为图 Laplacian 的 Green 函数，则均匀化理论直接适用。如果 $\Phi_N$ 定义为 $1/d_H$ 的和，则需要额外的论证。

---

## 7. 总结与下一步

### 已完成的分析：

1. ✅ 发现原始 $\eta_N$ 公式的代数错误
2. ✅ 建立 Fourier-Walsh 分析框架
3. ✅ 计算图 Laplacian 的谱和 Green 函数
4. ✅ 发现离散 Green 函数的符号振荡现象
5. ✅ 识别"图维数 ≠ 嵌入维数"的根本困难

### 核心结论：

**原始文档的证明策略（通过汉明距离→欧氏距离的桥梁 + 黎曼和收敛）存在根本性问题。** 正确的路径是均匀化理论，而非直接的黎曼和逼近。

### 下一步：

1. 建立 $\{0,1}^N$ 上的均匀化定理（将块结构视为"微结构"）
2. 确定均匀化后的有效方程（是否为 Poisson 方程）
3. 证明均匀化系数由公理 A1-A9 确定
4. 计算点源极限下的有效势

**技术难度：高。** 需要将经典均匀化理论（$\mathbb{R}^d$ 上的周期结构）推广到超立方体上的图结构。这是一个开放的数学问题。
