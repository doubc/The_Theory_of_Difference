"""
Klein 瓶同调群计算
目标：检验 {0,1}^4 在公理约束下的子空间是否涌现 Klein 瓶拓扑
即 H_1 是否含 Z_2 扭转项

依赖：pip install numpy scipy
不需要 gudhi，用史密斯标准型手动计算整系数同调
"""

import numpy as np


# ============================================================
# 第一层：构造 {0,1}^4 的顶点、棱、面
# ============================================================

def hamming_distance(a, b):
    return sum(x != y for x, y in zip(a, b))


def hamming_weight(v):
    return sum(v)


def all_vertices(N=4):
    """生成 {0,1}^N 的所有顶点，用 tuple 表示"""
    from itertools import product
    return list(product([0, 1], repeat=N))


def apply_A4(vertices):
    """
    A4（最小变易）：只允许 Hamming 距离为 1 的边
    返回所有合法的无向边（frozenset）
    """
    edges = set()
    n = len(vertices)
    for i in range(n):
        for j in range(i + 1, n):
            if hamming_distance(vertices[i], vertices[j]) == 1:
                edges.add(frozenset([vertices[i], vertices[j]]))
    return list(edges)


def apply_A6_dag(edges, vertices):
    """
    A6（不可逆性/DAG）：给边赋予方向
    规则：边从 Hamming 重量小的顶点指向重量大的顶点
    若重量相同（中截面内部），按字典序定向
    返回有向边列表 (from, to)
    """
    directed = []
    for e in edges:
        v_list = list(e)
        w0 = hamming_weight(v_list[0])
        w1 = hamming_weight(v_list[1])
        if w0 < w1:
            directed.append((v_list[0], v_list[1]))
        elif w0 > w1:
            directed.append((v_list[1], v_list[0]))
        else:
            # 重量相同（中截面内），按字典序
            if v_list[0] < v_list[1]:
                directed.append((v_list[0], v_list[1]))
            else:
                directed.append((v_list[1], v_list[0]))
    return directed


def apply_A7_faces(directed_edges, vertices):
    """
    A7（循环闭合）：找所有最小闭合面（三角形和四边形）
    这里只找四边形面（超立方体的自然面结构）
    四边形：四个顶点两两 Hamming 距离为 1 或 2，构成正方形
    """
    vertex_set = set(vertices)
    directed_set = set(directed_edges)
    undirected_set = set()
    for (a, b) in directed_edges:
        undirected_set.add(frozenset([a, b]))

    faces = []
    verts = list(vertices)
    n = len(verts)

    for i in range(n):
        for j in range(i + 1, n):
            for k in range(j + 1, n):
                for l in range(k + 1, n):
                    quad = [verts[i], verts[j], verts[k], verts[l]]
                    if is_square(quad, undirected_set):
                        faces.append(tuple(sorted(quad)))

    return list(set(faces))


def is_square(quad, undirected_set):
    """
    判断四个顶点是否构成超立方体的一个面（正方形）
    条件：恰好有 4 条边，每个顶点度数为 2
    """
    edges_in = []
    for i in range(4):
        for j in range(i + 1, 4):
            if frozenset([quad[i], quad[j]]) in undirected_set:
                edges_in.append((i, j))
    if len(edges_in) != 4:
        return False
    degree = [0] * 4
    for (i, j) in edges_in:
        degree[i] += 1
        degree[j] += 1
    return all(d == 2 for d in degree)


# ============================================================
# 第二层：构造链复形的边界算子（整系数）
# ============================================================

def build_boundary_operators(vertices, directed_edges, faces):
    """
    构造 ∂_1: C_1 → C_0 和 ∂_2: C_2 → C_1
    使用整系数（Smith 标准型用）

    顶点索引：vertex_idx[v] = i
    边索引：edge_idx[e] = j（有向边 (a,b) 存为 (a,b)）
    面索引：face_idx[f] = k
    """
    vertex_idx = {v: i for i, v in enumerate(vertices)}
    edge_idx = {e: i for i, e in enumerate(directed_edges)}
    face_idx = {f: i for i, f in enumerate(faces)}

    n_verts = len(vertices)
    n_edges = len(directed_edges)
    n_faces = len(faces)

    # ∂_1: C_1 → C_0
    # 对有向边 (a→b)，∂_1(e) = b - a
    d1 = np.zeros((n_verts, n_edges), dtype=int)
    for (a, b), j in edge_idx.items():
        d1[vertex_idx[b], j] += 1
        d1[vertex_idx[a], j] -= 1

    # ∂_2: C_2 → C_1
    # 对每个面，找其边界（四条有向边，带符号）
    d2 = np.zeros((n_edges, n_faces), dtype=int)
    undirected_to_directed = {}
    for (a, b) in directed_edges:
        undirected_to_directed[frozenset([a, b])] = (a, b)

    for face, k in face_idx.items():
        boundary_edges = get_face_boundary(face, undirected_to_directed)
        for (e, sign) in boundary_edges:
            if e in edge_idx:
                d2[edge_idx[e], k] += sign
            elif (e[1], e[0]) in edge_idx:
                d2[edge_idx[(e[1], e[0])], k] -= sign

    return d1, d2, vertex_idx, edge_idx, face_idx


def get_face_boundary(face, undirected_to_directed):
    """
    给定面的四个顶点，找其边界的四条有向边（带符号）
    沿正方形的边界走一圈，按 A6 定向确定符号
    """
    verts = list(face)
    # 找正方形的四条边
    edges_in = []
    for i in range(4):
        for j in range(i + 1, 4):
            key = frozenset([verts[i], verts[j]])
            if key in undirected_to_directed:
                edges_in.append((verts[i], verts[j]))

    if len(edges_in) != 4:
        return []

    # 构造正方形的有序边界（找一条哈密顿路径）
    # 建邻接表
    adj = {v: [] for v in verts}
    for (a, b) in edges_in:
        adj[a].append(b)
        adj[b].append(a)

    # 从第一个顶点出发，走一圈
    cycle = [verts[0]]
    visited = {verts[0]}
    current = verts[0]
    for _ in range(3):
        for nb in adj[current]:
            if nb not in visited:
                cycle.append(nb)
                visited.add(nb)
                current = nb
                break

    if len(cycle) != 4:
        return []

    # 生成四条有向边（沿循环方向）
    boundary = []
    for i in range(4):
        a = cycle[i]
        b = cycle[(i + 1) % 4]
        key = frozenset([a, b])
        if key in undirected_to_directed:
            canonical = undirected_to_directed[key]
            if canonical == (a, b):
                boundary.append(((a, b), +1))
            else:
                boundary.append(((b, a), -1))

    return boundary


# ============================================================
# 第三层：Smith 标准型 → 整系数同调群
# ============================================================

def smith_normal_form(M):
    """
    计算整数矩阵的 Smith 标准型
    返回对角元素列表（即不变因子）
    """
    M = M.copy().astype(int)
    m, n = M.shape
    diag = []
    row_start = 0
    col_start = 0

    while row_start < m and col_start < n:
        # 找非零元素
        pivot_found = False
        for i in range(row_start, m):
            for j in range(col_start, n):
                if M[i, j] != 0:
                    # 交换到左上角
                    M[[row_start, i]] = M[[i, row_start]]
                    M[:, [col_start, j]] = M[:, [j, col_start]]
                    pivot_found = True
                    break
            if pivot_found:
                break

        if not pivot_found:
            break

        # 迭代消元直到只有 pivot 位置非零
        changed = True
        while changed:
            changed = False
            # 消去同行
            for j in range(col_start + 1, n):
                if M[row_start, j] != 0:
                    q = M[row_start, j] // M[row_start, col_start]
                    M[:, j] -= q * M[:, col_start]
                    if M[row_start, j] != 0:
                        M[:, [col_start, j]] = M[:, [j, col_start]]
                    changed = True
            # 消去同列
            for i in range(row_start + 1, m):
                if M[i, col_start] != 0:
                    q = M[i, col_start] // M[row_start, col_start]
                    M[i, :] -= q * M[row_start, :]
                    if M[i, col_start] != 0:
                        M[[row_start, i]] = M[[i, row_start]]
                    changed = True

        pivot = M[row_start, col_start]
        if pivot < 0:
            M[row_start, :] = -M[row_start, :]
            pivot = -pivot
        diag.append(pivot)
        row_start += 1
        col_start += 1

    return diag


def compute_homology(d1, d2):
    """
    从边界算子计算整系数同调群 H_0, H_1, H_2

    H_n = ker(∂_n) / im(∂_{n+1})

    用 Smith 标准型分析：
    - 对角元为 1 的位置：贡献自由消去
    - 对角元 > 1 的位置：贡献 Z_d 扭转
    - 零对角元（或超出范围）：贡献自由 Z
    """
    results = {}

    # H_0: ker(∂_0) / im(∂_1)
    # ker(∂_0) = C_0（∂_0 = 0）
    # im(∂_1) 的秩 = rank(d1)
    n_verts = d1.shape[0]
    diag_d1 = smith_normal_form(d1)
    rank_d1 = sum(1 for x in diag_d1 if x != 0)
    # H_0 的自由秩 = n_verts - rank_d1（连通分量数）
    h0_free = n_verts - rank_d1
    results['H_0'] = f"Z^{h0_free}" if h0_free > 1 else "Z"

    # H_1: ker(∂_1) / im(∂_2)
    n_edges = d1.shape[1]
    # ker(∂_1) 的维数 = n_edges - rank(d1)
    ker_d1_rank = n_edges - rank_d1

    diag_d2 = smith_normal_form(d2)
    rank_d2 = sum(1 for x in diag_d2 if x != 0)
    # im(∂_2) 的秩 = rank(d2)
    # H_1 的自由秩
    h1_free = ker_d1_rank - rank_d2
    # 扭转项：diag_d2 中大于 1 的元素
    torsion = [x for x in diag_d2 if x > 1]

    h1_str = ""
    if h1_free > 0:
        h1_str += f"Z^{h1_free}" if h1_free > 1 else "Z"
    for t in torsion:
        h1_str += f" ⊕ Z_{t}" if h1_str else f"Z_{t}"
    results['H_1'] = h1_str if h1_str else "0"

    # H_2: ker(∂_2) / im(∂_3)
    # im(∂_3) = 0（没有三维面）
    n_faces = d2.shape[1]
    h2_free = n_faces - rank_d2
    results['H_2'] = f"Z^{h2_free}" if h2_free > 1 else ("Z" if h2_free == 1 else "0")

    return results


# ============================================================
# 主程序
# ============================================================

def run(N=4, midplane_only=False):
    print(f"{'=' * 60}")
    print(f"计算 {{0,1}}^{N} 在公理约束下的同调群")
    print(f"{'=' * 60}")

    vertices = all_vertices(N)

    # 可选：只取中截面（A8 偏好）
    if midplane_only:
        mid = N // 2
        vertices = [v for v in vertices if hamming_weight(v) == mid]
        print(f"[A8 约束] 只取中截面（Hamming 重量 = {mid}），顶点数：{len(vertices)}")
    else:
        print(f"全空间顶点数：{len(vertices)}")

    # A4：构造无向边
    edges_undirected = apply_A4(vertices)
    print(f"[A4] 无向边数：{len(edges_undirected)}")

    # A6：给边定向
    directed_edges = apply_A6_dag(edges_undirected, vertices)
    print(f"[A6] 有向边数：{len(directed_edges)}")

    # A7：构造面
    faces = apply_A7_faces(directed_edges, vertices)
    print(f"[A7] 面数（四边形）：{len(faces)}")

    # 构造边界算子
    d1, d2, _, _, _ = build_boundary_operators(vertices, directed_edges, faces)
    print(f"\n边界算子维度：")
    print(f"  ∂_1: {d1.shape[0]} × {d1.shape[1]}  (顶点 × 边)")
    print(f"  ∂_2: {d2.shape[0]} × {d2.shape[1]}  (边 × 面)")

    # 验证 ∂_1 ∘ ∂_2 = 0
    check = d1 @ d2
    if np.all(check == 0):
        print(f"\n[验证] ∂_1 ∘ ∂_2 = 0  ✓")
    else:
        print(f"\n[警告] ∂_1 ∘ ∂_2 ≠ 0，边界算子有误！")
        print(check)

    # 计算同调群
    homology = compute_homology(d1, d2)

    print(f"\n{'=' * 60}")
    print(f"同调群结果：")
    print(f"{'=' * 60}")
    for k, v in homology.items():
        print(f"  {k} = {v}")

    # 判断拓扑类型
    print(f"\n{'=' * 60}")
    print(f"拓扑判断：")
    print(f"{'=' * 60}")
    h1 = homology['H_1']
    h2 = homology['H_2']

    if 'Z_2' in h1 and 'Z' in h1 and 'Z^' not in h1.replace('Z_2', ''):
        print(f"  H_1 含 Z ⊕ Z_2 → Klein 瓶特征！")
    elif h1 == 'Z ⊕ Z' or h1 == 'Z^2':
        print(f"  H_1 = Z² → 环面（Torus）特征")
    elif h1 == 'Z':
        print(f"  H_1 = Z → 圆柱或 Möbius 带特征")
    elif h1 == '0':
        print(f"  H_1 = 0 → 单连通（球面或收缩空间）")
    else:
        print(f"  H_1 = {h1} → 需要进一步分析")

    if h2 == '0':
        print(f"  H_2 = 0 → 非可定向或无三维空腔（Klein 瓶/射影平面）")
    elif h2 == 'Z':
        print(f"  H_2 = Z → 可定向闭曲面（环面/球面）")

    return homology


if __name__ == "__main__":
    # 实验一：完整 {0,1}^4，全部公理
    print("\n【实验一】完整 {0,1}^4（A4 + A6 + A7）")
    h_full = run(N=4, midplane_only=False)

    # 实验二：只取中截面（A8 约束）
    print("\n【实验二】中截面子空间（A4 + A6 + A7 + A8）")
    h_mid = run(N=4, midplane_only=True)

    # 实验三：N=3 对照组
    print("\n【实验三】{0,1}^3 对照（A4 + A6 + A7）")
    h_3 = run(N=3, midplane_only=False)
