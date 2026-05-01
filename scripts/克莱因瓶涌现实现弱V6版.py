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


def apply_A6_dag_weak(edges, vertices):
    """
    弱化版 A6：
    - 跨越中截面的边（重量不同）：有向（低→高）
    - 中截面内部的边（重量相同）：保留双向（两个方向都加入）
    这对应"不可逆性只约束跨截面演化，截面内部可逆"
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
            # 重量相同：保留双向
            directed.append((v_list[0], v_list[1]))
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


def apply_A1_prime_quotient(vertices, N=4):
    """
    A1'（横向涌现）定义的等价关系：
    两个顶点等价，当且仅当它们在所有"纵向比特"上相同，
    只在"横向比特对"上相差一个完整的对翻转。

    对 N=4，定义横向对为 (0,1) 和 (2,3)：
    - 比特 0 和比特 1 构成第一个横向对
    - 比特 2 和比特 3 构成第二个横向对

    等价关系：v ~ w 当且仅当
    v 和 w 在某个横向对上互换（01↔10），其余比特不变
    这对应 U(1) 相位旋转的离散版本
    """
    # 横向对定义
    pairs = [(0, 1), (2, 3)]

    # 构造等价类（union-find）
    parent = {v: v for v in vertices}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(x, y):
        px, py = find(x), find(y)
        if px != py:
            parent[px] = py

    # 对每个横向对，把互换的顶点合并
    for v in vertices:
        for (i, j) in pairs:
            if v[i] != v[j]:  # 01 或 10 状态
                # 构造互换后的顶点
                w = list(v)
                w[i], w[j] = w[j], w[i]
                w = tuple(w)
                if w in set(vertices):
                    union(v, w)

    # 构造商空间：每个等价类取一个代表元
    classes = {}
    for v in vertices:
        rep = find(v)
        if rep not in classes:
            classes[rep] = []
        classes[rep].append(v)

    return classes


def run_quotient(N=4):
    print(f"\n{'=' * 60}")
    print(f"【实验五】商空间（A1' 等价关系 + A4 + A6 + A7）")
    print(f"{'=' * 60}")

    vertices = all_vertices(N)
    classes = apply_A1_prime_quotient(vertices, N)

    # 代表元作为商空间的顶点
    rep_vertices = list(classes.keys())
    print(f"原始顶点数：{len(vertices)}")
    print(f"等价类数（商空间顶点数）：{len(rep_vertices)}")

    # 显示等价类
    print(f"\n等价类结构：")
    for rep, members in classes.items():
        if len(members) > 1:
            print(f"  {rep} ~ {[m for m in members if m != rep]}")

    # 在商空间上施加 A4
    edges_q = set()
    rep_set = set(rep_vertices)

    def get_rep(v):
        # 找 v 所在等价类的代表元
        for rep, members in classes.items():
            if v in members:
                return rep
        return v

    # 原始边映射到商空间
    original_edges = apply_A4(vertices)
    for e in original_edges:
        v_list = list(e)
        r0 = get_rep(v_list[0])
        r1 = get_rep(v_list[1])
        if r0 != r1:
            edges_q.add(frozenset([r0, r1]))

    edges_q = list(edges_q)
    print(f"\n[A4 + 商] 无向边数：{len(edges_q)}")

    # A6 定向
    directed_q = apply_A6_dag(edges_q, rep_vertices)
    print(f"[A6] 有向边数：{len(directed_q)}")

    # A7 面
    faces_q = apply_A7_faces(directed_q, rep_vertices)
    print(f"[A7] 面数：{len(faces_q)}")

    if len(directed_q) == 0:
        print("无边，无法计算同调。")
        return

    # 边界算子
    d1_q, d2_q, _, _, _ = build_boundary_operators(
        rep_vertices, directed_q, faces_q)

    check = d1_q @ d2_q
    print(f"[验证] ∂_1∘∂_2=0: {np.all(check == 0)}")

    # 同调群
    h = compute_homology(d1_q, d2_q)
    print(f"\n同调群结果：")
    for k, v in h.items():
        print(f"  {k} = {v}")

    # 判断
    print(f"\n拓扑判断：")
    h1 = h['H_1']
    h2 = h['H_2']
    if 'Z_2' in h1:
        print(f"  ***​ H_1 含 Z_2 扭转 → Klein 瓶或射影平面特征！​***")
    elif h1 in ['Z^2', 'Z ⊕ Z']:
        print(f"  H_1 = Z² → 环面特征")
    elif h1 == 'Z':
        print(f"  H_1 = Z → Möbius 带或圆柱特征")
    elif h1 == '0':
        print(f"  H_1 = 0 → 单连通")
    print(f"  H_2 = {h2}")


def run_klein_bottle_explicit():
    """
    实验六：显式 Klein 瓶粘合

    策略：在 {0,1}^4 中选一个自然的正方形面，
    按 Klein 瓶粘合规则（一对同向、一对反向）合并顶点，
    然后计算商空间的同调群。

    选取的正方形：比特 0 和比特 1 变化，比特 2=比特 3=0
    四个顶点：
        v00 = (0,0,0,0)
        v10 = (1,0,0,0)
        v01 = (0,1,0,0)
        v11 = (1,1,0,0)

    Klein 瓶粘合规则（标准定向）：
        上边 v00→v10，下边 v01→v11（同向粘合）：v00~v01, v10~v11
        左边 v00→v01，右边 v10→v11（反向粘合）：v00~v11, v10~v01

    合并后四个顶点变成一个等价类 [v00]
    其余顶点（比特2或3非零）保持独立
    """
    print(f"\n{'=' * 60}")
    print(f"【实验六】显式 Klein 瓶粘合（正方形对边反向识别）")
    print(f"{'=' * 60}")

    vertices = all_vertices(4)

    # Klein 瓶粘合：选比特2=比特3=0 的面
    klein_face = {
        (0, 0, 0, 0), (1, 0, 0, 0), (0, 1, 0, 0), (1, 1, 0, 0)
    }

    # Union-Find
    parent = {v: v for v in vertices}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(x, y):
        px, py = find(x), find(y)
        if px != py:
            parent[px] = py

    # Klein 瓶粘合规则：四个顶点全部合并
    # （上下同向 + 左右反向 → 所有顶点等价）
    verts_face = list(klein_face)
    for i in range(len(verts_face)):
        for j in range(i + 1, len(verts_face)):
            union(verts_face[i], verts_face[j])

    # 构造等价类
    classes = {}
    for v in vertices:
        rep = find(v)
        if rep not in classes:
            classes[rep] = []
        classes[rep].append(v)

    rep_vertices = list(classes.keys())
    print(f"原始顶点数：{len(vertices)}")
    print(f"商空间顶点数：{len(rep_vertices)}")
    print(f"\n等价类结构：")
    for rep, members in classes.items():
        if len(members) > 1:
            print(f"  {rep} ~ {[m for m in members if m != rep]}")

    def get_rep(v):
        r = find(v)
        return r

    # 在商空间上施加 A4
    original_edges = apply_A4(vertices)
    edges_q = set()
    for e in original_edges:
        v_list = list(e)
        r0 = get_rep(v_list[0])
        r1 = get_rep(v_list[1])
        if r0 != r1:
            edges_q.add(frozenset([r0, r1]))
    edges_q = list(edges_q)
    print(f"\n[A4 + 商] 无向边数：{len(edges_q)}")

    # A6 定向
    directed_q = apply_A6_dag(edges_q, rep_vertices)
    print(f"[A6] 有向边数：{len(directed_q)}")

    # A7 面
    faces_q = apply_A7_faces(directed_q, rep_vertices)
    print(f"[A7] 面数：{len(faces_q)}")

    if len(directed_q) == 0:
        print("无边，无法计算同调。")
        return

    # 边界算子
    d1_q, d2_q, _, _, _ = build_boundary_operators(
        rep_vertices, directed_q, faces_q)

    check = d1_q @ d2_q
    print(f"[验证] ∂_1∘∂_2=0: {np.all(check == 0)}")
    if not np.all(check == 0):
        print("警告：边界算子不满足 ∂²=0，面的定向有问题。")
        return

    # 同调群
    h = compute_homology(d1_q, d2_q)
    print(f"\n同调群结果：")
    for k, v in h.items():
        print(f"  {k} = {v}")

    # 判断
    print(f"\n拓扑判断：")
    h1 = h['H_1']
    h2 = h['H_2']
    if 'Z_2' in h1:
        print(f"  ***​ H_1 含 Z_2 扭转 → Klein 瓶或射影平面特征！​***")
        if h2 == '0':
            print(f"  H_2 = 0 → 非可定向，倾向 Klein 瓶（而非环面）")
    elif h1 in ['Z^2', 'Z ⊕ Z']:
        print(f"  H_1 = Z² → 环面特征（可定向）")
    elif h1 == 'Z':
        print(f"  H_1 = Z → Möbius 带或圆柱特征")
    elif h1 == '0':
        print(f"  H_1 = 0 → 单连通，无非平凡圈")
    print(f"  H_2 = {h2}")

    # 额外分析：检查 Klein 瓶粘合边的命运
    print(f"\n--- Klein 瓶粘合面的分析 ---")
    print(f"被粘合的四个顶点合并为一个等价类。")
    print(f"原正方形的四条边在商空间中变为自环（两端点相同），被 A4 过滤掉。")
    print(f"Klein 瓶的拓扑特征需要通过与该等价类相连的外部边来体现。")

    return h


def run_klein_bottle_2d():
    """
    实验七：纯 2D Klein 瓶（不嵌入 {0,1}^4）

    直接构造 Klein 瓶的标准三角剖分，
    验证代码的同调计算是否能正确识别 Klein 瓶。

    Klein 瓶标准三角剖分（最小剖分需要 8 个三角形，6 个顶点）：
    使用正方形粘合的 CW 复形表示（4 个顶点，2 条边，1 个面）

    更简单：用已知的 Klein 瓶 CW 复形直接输入边界算子
    Klein 瓶的 CW 结构：
        - 1 个 0-cell（顶点 v）
        - 2 个 1-cell（边 a, b）
        - 1 个 2-cell（面 F，边界 = a + b + a - b = 2a）

    边界算子：
        ∂_1(a) = v - v = 0
        ∂_1(b) = v - v = 0
        ∂_2(F) = 2a（Klein 瓶粘合规则的代数表达）

    同调群：
        H_0 = Z（连通）
        H_1 = ker(∂_1) / im(∂_2) = Z² / <2a> = Z_2 ⊕ Z
        H_2 = ker(∂_2) = 0（因为 ∂_2(F)=2a≠0）
    """
    print(f"\n{'=' * 60}")
    print(f"【实验七】Klein 瓶标准 CW 复形（基准验证）")
    print(f"{'=' * 60}")
    print(f"使用 Klein 瓶的最小 CW 分解：1 顶点，2 边，1 面")
    print(f"∂_2(F) = 2a（Klein 瓶粘合的代数表达）")

    # 直接构造边界算子
    # C_0: {v}, C_1: {a, b}, C_2: {F}
    # ∂_1: C_1 → C_0
    d1 = np.array([[0, 0]], dtype=int)  # 1×2，全零（自环）
    # ∂_2: C_2 → C_1
    d2 = np.array([[2], [0]], dtype=int)  # 2×1，∂_2(F) = 2a + 0b

    print(f"\n∂_1 = {d1}")
    print(f"∂_2 = {d2.T}  (转置显示)")

    check = d1 @ d2
    print(f"∂_1∘∂_2 = {check}，验证: {np.all(check == 0)}")

    h = compute_homology(d1, d2)
    print(f"\n同调群结果：")
    for k, v in h.items():
        print(f"  {k} = {v}")

    print(f"\n拓扑判断：")
    h1 = h['H_1']
    if 'Z_2' in h1:
        print(f"  ***​ H_1 含 Z_2 → Klein 瓶特征正确识别！代码验证通过 ✓ ​***")
    else:
        print(f"  H_1 = {h1}，预期 Z ⊕ Z_2，代码可能有 Bug！")

    return h


def run_klein_bottle_with_loops():
    """
    实验八：允许自环边的 Klein 瓶商空间

    修正实验六的核心问题：
    在商空间中保留自环边（两端点相同的边），
    并按 Klein 瓶粘合规则赋予正确定向。

    策略：
    1. 先构造商空间（同实验六）
    2. 对原正方形的四条边，不过滤自环，
       而是按 Klein 瓶规则赋予带符号系数
    3. 把自环边加入 C_1，∂_1(自环) = 0
    4. 构造包含自环的面（原正方形面），
       ∂_2(F) = +a + b + a - b = 2a
    5. 计算完整同调群
    """
    print(f"\n{'=' * 60}")
    print(f"【实验八】Klein 瓶商空间（保留自环，显式粘合方向）")
    print(f"{'=' * 60}")

    vertices = all_vertices(4)

    # 同实验六：合并 Klein 面的四个顶点
    parent = {v: v for v in vertices}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(x, y):
        px, py = find(x), find(y)
        if px != py:
            parent[px] = py

    klein_verts = [
        (0, 0, 0, 0), (1, 0, 0, 0), (0, 1, 0, 0), (1, 1, 0, 0)
    ]
    for i in range(len(klein_verts)):
        for j in range(i + 1, len(klein_verts)):
            union(klein_verts[i], klein_verts[j])

    def get_rep(v):
        return find(v)

    rep_set = list(set(get_rep(v) for v in vertices))
    rep_index = {r: i for i, r in enumerate(rep_set)}
    v_rep = get_rep((0, 0, 0, 0))  # Klein 面合并后的代表元
    print(f"商空间顶点数：{len(rep_set)}")
    print(f"Klein 面代表元：{v_rep}")

    # ── 外部边（非自环）──────────────────────────────────
    original_edges = apply_A4(vertices)
    ext_edges = []
    for e in original_edges:
        vl = list(e)
        r0, r1 = get_rep(vl[0]), get_rep(vl[1])
        if r0 != r1:
            ext_edges.append(frozenset([r0, r1]))
    ext_edges = list(set(ext_edges))
    ext_directed = apply_A6_dag(ext_edges, rep_set)
    print(f"外部有向边数：{len(ext_directed)}")

    # ── Klein 面的自环边（带粘合方向）────────────────────
    # 按 Klein 瓶粘合规则，原正方形四条有向边映射为：
    #   (0,0,0,0)→(1,0,0,0)  →  自环 a，系数 +1
    #   (0,1,0,0)→(1,1,0,0)  →  自环 a，系数 +1（同向）
    #   (0,0,0,0)→(0,1,0,0)  →  自环 b，系数 +1
    #   (1,0,0,0)→(1,1,0,0)  →  自环 b，系数 -1（反向）
    # 自环 a 和 b 是两条不同的 1-cell（即使端点相同）
    # 用特殊标记区分
    loop_a = ('loop', v_rep, 'a')  # 代表水平方向粘合
    loop_b = ('loop', v_rep, 'b')  # 代表垂直方向粘合
    all_directed = ext_directed + [loop_a, loop_b]

    # ── 面的构造 ──────────────────────────────────────────
    # 外部面（同实验六）
    ext_faces = apply_A7_faces(ext_directed, rep_set)

    # Klein 瓶面（原正方形）：
    # 边界 = +a + b + a - b = 2a
    # 用带符号的边列表表示：[(+1, loop_a), (+1, loop_b), (+1, loop_a), (-1, loop_b)]
    # 但链复形中每条边只出现一次，系数叠加：
    # ∂_2(F_klein) 在 loop_a 上系数 = +2，在 loop_b 上系数 = 0
    klein_face_cell = ('klein_face',)

    print(f"外部面数：{len(ext_faces)}")
    print(f"Klein 面：1 个（∂_2 在 loop_a 系数=+2，loop_b 系数=0）")

    # ── 构造完整边界算子 ──────────────────────────────────
    # 索引
    all_verts = rep_set
    n0 = len(all_verts)
    v_idx = {v: i for i, v in enumerate(all_verts)}

    all_edges = all_directed  # ext_directed + [loop_a, loop_b]
    n1 = len(all_edges)
    e_idx = {e: i for i, e in enumerate(all_edges)}

    all_faces = ext_faces + [klein_face_cell]
    n2 = len(all_faces)

    print(f"\n链复形维数：C_0={n0}, C_1={n1}, C_2={n2}")

    # ∂_1: C_1 → C_0
    d1 = np.zeros((n0, n1), dtype=int)
    for j, e in enumerate(all_edges):
        if e[0] == 'loop':
            # 自环：∂_1 = 0（端点相同）
            pass
        else:
            # 有向边 (src, tgt)
            src, tgt = e
            d1[v_idx[tgt], j] += 1
            d1[v_idx[src], j] -= 1

    # ∂_2: C_2 → C_1
    d2 = np.zeros((n1, n2), dtype=int)
    for k, f in enumerate(all_faces):
        if f == ('klein_face',):
            # Klein 瓶面：∂_2(F) = 2*loop_a + 0*loop_b
            d2[e_idx[loop_a], k] += 2
            # loop_b 系数为 0，不写
        else:
            # 普通面（四边形）：四条有向边带符号
            edges_of_face = f  # 由 apply_A7_faces 返回的格式
            # 需要重新构造面的边界
            # apply_A7_faces 返回的是 frozenset of directed edges
            # 这里需要调整接口
            pass

    # 注意：apply_A7_faces 的返回格式需要检查
    # 先用简化版：只验证 Klein 面的贡献
    print(f"\n--- 简化验证：只含 Klein 面和自环边 ---")
    print(f"构造最小链复形：C_0={{v}}, C_1={{a,b}}, C_2={{F}}")
    print(f"直接调用实验七的逻辑验证 Klein 瓶同调")


def run_experiment_9():
    """
    实验九：含自环的完整 Klein 瓶商空间同调计算

    在实验八的框架上，补全外部面的 ∂_2 构造，
    得到完整的边界算子，计算 H_0, H_1, H_2。

    关键修改：
    - apply_A7_faces 返回的每个面是一个 frozenset of (src, tgt) 有向边
    - 需要把这些有向边映射到 all_edges 的索引，带符号 ±1
    - 自环边 loop_a, loop_b 不会出现在外部面的边界里
    - Klein 面的 ∂_2 手动指定：loop_a 系数 +2，其余 0
    """
    print(f"\n{'=' * 60}")
    print(f"【实验九】完整含自环 Klein 瓶商空间同调")
    print(f"{'=' * 60}")

    vertices = all_vertices(4)

    # ── 1. 商空间构造（同实验六/八）──────────────────────
    parent = {v: v for v in vertices}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(x, y):
        px, py = find(x), find(y)
        if px != py:
            parent[px] = py

    klein_verts = [(0, 0, 0, 0), (1, 0, 0, 0), (0, 1, 0, 0), (1, 1, 0, 0)]
    for i in range(len(klein_verts)):
        for j in range(i + 1, len(klein_verts)):
            union(klein_verts[i], klein_verts[j])

    def get_rep(v):
        return find(v)

    rep_set = list(set(get_rep(v) for v in vertices))
    rep_set.sort()
    v_rep = get_rep((0, 0, 0, 0))
    v_idx = {v: i for i, v in enumerate(rep_set)}
    n0 = len(rep_set)
    print(f"C_0 顶点数：{n0}，Klein 代表元：{v_rep}")

    # ── 2. 外部边与自环边 ─────────────────────────────────
    original_edges = apply_A4(vertices)
    ext_edges_set = set()
    for e in original_edges:
        vl = list(e)
        r0, r1 = get_rep(vl[0]), get_rep(vl[1])
        if r0 != r1:
            ext_edges_set.add(frozenset([r0, r1]))
    ext_edges = list(ext_edges_set)
    ext_directed = apply_A6_dag(ext_edges, rep_set)

    loop_a = ('loop', v_rep, 'a')
    loop_b = ('loop', v_rep, 'b')
    all_edges = ext_directed + [loop_a, loop_b]
    n1 = len(all_edges)
    e_idx = {e: i for i, e in enumerate(all_edges)}
    print(f"C_1 边数：{n1}（外部 {len(ext_directed)} + 自环 2）")

    # ── 3. 面的构造 ───────────────────────────────────────
    # apply_A7_faces 返回的面格式：
    # 每个面是一个 frozenset，包含四条有向边 (src, tgt)
    # 需要确认实际格式，这里先打印一个样本
    ext_faces_raw = apply_A7_faces(ext_directed, rep_set)
    if ext_faces_raw:
        sample = list(ext_faces_raw)[0]
        print(f"\napply_A7_faces 返回样本类型：{type(sample)}")
        print(f"样本内容：{sample}")

    klein_face_id = 'klein_face'
    all_faces = list(ext_faces_raw) + [klein_face_id]
    n2 = len(all_faces)
    f_idx = {f: i for i, f in enumerate(all_faces)}
    print(f"C_2 面数：{n2}（外部 {len(ext_faces_raw)} + Klein 面 1）")

    # ── 4. ∂_1 矩阵 ───────────────────────────────────────
    d1 = np.zeros((n0, n1), dtype=int)
    for j, e in enumerate(all_edges):
        if isinstance(e, tuple) and e[0] == 'loop':
            pass  # 自环：∂_1 = 0
        else:
            src, tgt = e
            d1[v_idx[tgt], j] += 1
            d1[v_idx[src], j] -= 1

    # ── 5. ∂_2 矩阵 ───────────────────────────────────────
    d2 = np.zeros((n1, n2), dtype=int)

    for k, f in enumerate(all_faces):
        if f == klein_face_id:
            # Klein 瓶面：∂_2(F) = 2·loop_a + 0·loop_b
            d2[e_idx[loop_a], k] = 2
        else:
            # 外部面：从面的边界提取有向边，带符号 ±1
            # 需要根据 apply_A7_faces 的实际返回格式来写
            # 情况 A：如果 f 是 frozenset of (src, tgt) 有向边
            if isinstance(f, frozenset):
                for edge in f:
                    if isinstance(edge, tuple) and len(edge) == 2:
                        src, tgt = edge
                        fwd = (src, tgt)
                        rev = (tgt, src)
                        if fwd in e_idx:
                            d2[e_idx[fwd], k] += 1
                        elif rev in e_idx:
                            d2[e_idx[rev], k] -= 1
                        # 如果两者都不在，说明边不在 C_1 里，跳过
            # 情况 B：如果 f 是别的格式，在样本打印后手动调整

    # ── 6. 验证 ∂_1∘∂_2 = 0 ──────────────────────────────
    check = d1 @ d2
    ok = np.all(check == 0)
    print(f"\n[验证] ∂_1∘∂_2 = 0: {ok}")
    if not ok:
        nonzero = np.argwhere(check != 0)
        print(f"非零位置（前5个）：{nonzero[:5]}")
        print(f"对应面：{[all_faces[j] for _, j in nonzero[:5]]}")
        print(f"警告：∂²≠0，面的定向有问题，同调结果不可信。")
        print(f"需要检查 apply_A7_faces 的返回格式并修正符号。")
        # 仍然输出结果供参考，但标注不可信
        print(f"（以下结果仅供参考，不可信）")

    # ── 7. 同调群 ─────────────────────────────────────────
    h = compute_homology(d1, d2)
    print(f"\n同调群结果：")
    for key, val in h.items():
        print(f"  {key} = {val}")

    # ── 8. 判断 ───────────────────────────────────────────
    print(f"\n拓扑判断：")
    h1 = h['H_1']
    h2 = h['H_2']

    if not ok:
        print(f"  ∂²≠0，结果不可信，需修正面的定向符号后重跑。")
    elif 'Z_2' in h1:
        print(f"  ***​ H_1 含 Z_2 扭转！​***")
        print(f"  这来自显式编码的 Klein 面（∂_2=2a），不是公理自发涌现。")
        print(f"  H_1 的完整结构：{h1}")
        print(f"  H_2 = {h2}")
        if h2 == '0':
            print(f"  H_2=0 与 Klein 瓶一致（非可定向曲面）。")
        else:
            print(f"  H_2≠0，说明商空间不是纯粹的 Klein 瓶，")
            print(f"  还有来自超立方体骨架的额外拓扑结构。")
    elif h1 == '0':
        print(f"  H_1=0，Klein 面的贡献被外部结构抵消，或定向符号仍有问题。")
    else:
        print(f"  H_1={h1}，不含 Z_2 扭转。")
        print(f"  Klein 面未能在当前商空间中产生扭转——")
        print(f"  可能原因：外部圈与 Klein 圈之间存在边界关系。")

    # ── 9. 关键诊断：loop_a 在同调中的命运 ──────────────
    print(f"\n--- loop_a 的同调分析 ---")
    la_idx = e_idx[loop_a]
    lb_idx = e_idx[loop_b]
    print(f"loop_a 在 ∂_1 中的列（应全为0）：{d1[:, la_idx].tolist()}")
    print(f"loop_b 在 ∂_1 中的列（应全为0）：{d1[:, lb_idx].tolist()}")
    print(f"loop_a 在 ∂_2 中的行（Klein 面系数）：{d2[la_idx, :].tolist()}")
    print(f"loop_b 在 ∂_2 中的行（应全为0）：{d2[lb_idx, :].tolist()}")

    # loop_a 在 ker(∂_1) 中（因为 ∂_1(loop_a)=0）
    # loop_a 在 im(∂_2) 中当且仅当存在面 F 使得 ∂_2(F) 含 loop_a
    # Klein 面给出 ∂_2(F_klein) = 2·loop_a，所以 2·loop_a ∈ im(∂_2)
    # 这正是 Z_2 扭转的来源
    print(f"\nloop_a ∈ ker(∂_1)：True（自环）")
    print(f"2·loop_a ∈ im(∂_2)：True（Klein 面贡献）")
    print(f"→ [loop_a] 在 H_1 中的阶为 2，即 Z_2 分量")
    print(f"→ 前提：loop_a 不在 im(∂_2) 中（即不存在面使得 ∂_2=loop_a）")

    # 检验 loop_a 是否在 im(∂_2) 中（即是否存在整数线性组合使得 ∂_2·x = e_{la_idx}）
    # 这等价于检验 d2 的列空间是否包含标准基向量 e_{la_idx}
    # 用 Smith 标准型可以严格判断，这里用简单的秩检验
    d2_aug = np.column_stack([d2, np.eye(n1, dtype=int)[:, la_idx:la_idx + 1]])
    rank_d2 = np.linalg.matrix_rank(d2)
    rank_aug = np.linalg.matrix_rank(d2_aug)
    loop_a_in_image = (rank_d2 == rank_aug)
    print(f"loop_a ∈ im(∂_2)（秩检验）：{loop_a_in_image}")
    if not loop_a_in_image:
        print(f"→ 确认：loop_a 不在 im(∂_2) 中，Z_2 扭转有效。")
    else:
        print(f"→ loop_a 在 im(∂_2) 中，Z_2 扭转被抵消，H_1 无扭转项。")

    return h


def face_vertices_to_boundary(face_verts, e_idx, get_rep):
    """
    输入：face_verts = (v0, v1, v2, v3)，四个原始顶点坐标（商空间前）
    输出：dict {edge_idx: coefficient}，即 ∂_2(face) 在各边上的系数

    策略：
    四边形面的四个顶点映射到商空间代表元后，
    找出所有在 all_edges 中存在的有向边，
    按标准四边形定向（顺时针/逆时针）赋予 ±1 系数。

    四边形顶点的自然排序：
    face_verts 的四个顶点按 Hamming 距离构成一个正方形：
    设比特位 i, j 是变化的两个位，则四个顶点是：
        v00（i=0,j=0）, v10（i=1,j=0）, v11（i=1,j=1）, v01（i=0,j=1）
    标准定向：v00→v10→v11→v01→v00
    """
    reps = [get_rep(v) for v in face_verts]

    # 找出变化的两个比特位
    v0 = face_verts[0]
    v1 = face_verts[1]
    v2 = face_verts[2]
    v3 = face_verts[3]

    # 按 Hamming 权重排序，找到正方形的角
    # 或者直接用 apply_A7_faces 返回的顺序
    # 先假设返回顺序是 (v00, v10, v01, v11)（按比特字典序）
    # 标准四边形定向：v00→v10, v10→v11, v11→v01, v01→v00
    # 即：第0→1，第1→3，第3→2，第2→0（按字典序排列）

    # 更安全的方法：找四个顶点中 Hamming 距离=1 的相邻对，
    # 构成四边形的四条边，然后用一致定向

    # 构造所有可能的有向边（Hamming 距离=1 的顶点对）
    n = len(face_verts[0])
    adj = []
    for i in range(4):
        for j in range(4):
            if i != j:
                vi, vj = face_verts[i], face_verts[j]
                dist = sum(a != b for a, b in zip(vi, vj))
                if dist == 1:
                    ri, rj = get_rep(vi), get_rep(vj)
                    if ri != rj:
                        adj.append((ri, rj))

    # adj 现在包含四边形的 8 条有向边（每条无向边两个方向）
    # 需要选出构成一致定向的 4 条

    # 一致定向：找一个欧拉回路（每个顶点入度=出度=1）
    # 对四边形，这等价于选一个哈密顿圈
    # 用简单的贪心方法：从第一个顶点出发，每次选未访问的邻居

    rep_verts = list(set(get_rep(v) for v in face_verts))
    if len(rep_verts) < 3:
        # 顶点被过度合并，无法构成有意义的面
        return {}

    # 构造邻接表（只保留在 all_edges 中存在的方向）
    from_dict = {v: [] for v in rep_verts}
    for ri, rj in adj:
        if (ri, rj) in e_idx:
            from_dict[ri].append(rj)

    # 找哈密顿圈
    def find_cycle(start, path):
        if len(path) == len(rep_verts):
            if path[0] in from_dict.get(path[-1], []):
                return path
            return None
        last = path[-1]
        for nxt in from_dict.get(last, []):
            if nxt not in path:
                result = find_cycle(start, path + [nxt])
                if result is not None:
                    return result
        return None

    cycle = find_cycle(rep_verts[0], [rep_verts[0]])
    if cycle is None:
        return {}

    # 从哈密顿圈提取有向边，赋予系数 +1
    coeff = {}
    for i in range(len(cycle)):
        src = cycle[i]
        tgt = cycle[(i + 1) % len(cycle)]
        if (src, tgt) in e_idx:
            coeff[e_idx[(src, tgt)]] = coeff.get(e_idx[(src, tgt)], 0) + 1
        elif (tgt, src) in e_idx:
            coeff[e_idx[(tgt, src)]] = coeff.get(e_idx[(tgt, src)], 0) - 1

    return coeff


def face_vertices_to_boundary_v2(face_verts, e_idx, get_rep):
    """
    输入：face_verts = (v0, v1, v2, v3)，四个原始顶点（按字典序排列）

    策略：
    不用哈密顿圈。直接从四个顶点找出变化的两个比特位 i, j，
    按标准正方形定向构造边界：

    设四个顶点按 (bit_i, bit_j) 分类：
        v00 = bit_i=0, bit_j=0
        v10 = bit_i=1, bit_j=0
        v01 = bit_i=0, bit_j=1
        v11 = bit_i=1, bit_j=1

    标准定向（逆时针）：v00 → v10 → v11 → v01 → v00
    边界 = (v00→v10) + (v10→v11) + (v11→v01)_反向 + (v01→v00)_反向
         = (v00→v10) + (v10→v11) - (v01→v11) - (v00→v01)

    对每条边，查 e_idx：
        如果正向在 e_idx 里，系数 +1
        如果反向在 e_idx 里，系数 -1
        如果两端点代表元相同（退化边），跳过
    """
    # 找变化的两个比特位
    n = len(face_verts[0])
    changing_bits = []
    for bit in range(n):
        vals = set(v[bit] for v in face_verts)
        if len(vals) == 2:
            changing_bits.append(bit)

    if len(changing_bits) != 2:
        return {}

    bi, bj = changing_bits[0], changing_bits[1]

    # 按 (bit_i, bit_j) 分类四个顶点
    corner = {}
    for v in face_verts:
        key = (v[bi], v[bj])
        corner[key] = v

    if len(corner) != 4:
        return {}

    v00 = corner[(0, 0)]
    v10 = corner[(1, 0)]
    v01 = corner[(0, 1)]
    v11 = corner[(1, 1)]

    # 标准逆时针定向的四条有向边，带系数
    # 边界 = (v00→v10) + (v10→v11) - (v01→v11) - (v00→v01)
    oriented_edges = [
        (get_rep(v00), get_rep(v10), +1),
        (get_rep(v10), get_rep(v11), +1),
        (get_rep(v01), get_rep(v11), -1),
        (get_rep(v00), get_rep(v01), -1),
    ]

    coeff = {}
    for src, tgt, sign in oriented_edges:
        if src == tgt:
            continue  # 退化边（顶点被合并）
        fwd = (src, tgt)
        rev = (tgt, src)
        if fwd in e_idx:
            coeff[e_idx[fwd]] = coeff.get(e_idx[fwd], 0) + sign
        elif rev in e_idx:
            coeff[e_idx[rev]] = coeff.get(e_idx[rev], 0) - sign
        # 两者都不在 e_idx：这条边在商空间里不存在，跳过

    return coeff


def run_experiment_9_fixed():
    """
    实验九（修正版）：正确解析 apply_A7_faces 的顶点格式
    """
    print(f"{'=' * 60}")
    print(f"【实验九修正版】正确面边界算子构造")
    print(f"{'=' * 60}")

    vertices = all_vertices(4)

    parent = {v: v for v in vertices}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(x, y):
        px, py = find(x), find(y)
        if px != py:
            parent[px] = py

    klein_verts = [(0, 0, 0, 0), (1, 0, 0, 0), (0, 1, 0, 0), (1, 1, 0, 0)]
    for i in range(len(klein_verts)):
        for j in range(i + 1, len(klein_verts)):
            union(klein_verts[i], klein_verts[j])

    def get_rep(v):
        return find(v)

    rep_set = sorted(set(get_rep(v) for v in vertices))
    v_rep = get_rep((0, 0, 0, 0))
    v_idx = {v: i for i, v in enumerate(rep_set)}
    n0 = len(rep_set)

    # 外部边
    original_edges = apply_A4(vertices)
    ext_edges_set = set()
    for e in original_edges:
        vl = list(e)
        r0, r1 = get_rep(vl[0]), get_rep(vl[1])
        if r0 != r1:
            ext_edges_set.add(frozenset([r0, r1]))
    ext_directed = apply_A6_dag(list(ext_edges_set), rep_set)

    loop_a = ('loop', v_rep, 'a')
    loop_b = ('loop', v_rep, 'b')
    all_edges = ext_directed + [loop_a, loop_b]
    n1 = len(all_edges)
    e_idx = {e: i for i, e in enumerate(all_edges)}

    # 面
    ext_faces_raw = apply_A7_faces(ext_directed, rep_set)
    klein_face_id = 'klein_face'
    all_faces = list(ext_faces_raw) + [klein_face_id]
    n2 = len(all_faces)
    print(f"C_0={n0}, C_1={n1}, C_2={n2}")

    # ∂_1
    d1 = np.zeros((n0, n1), dtype=int)
    for j, e in enumerate(all_edges):
        if isinstance(e, tuple) and e[0] == 'loop':
            pass
        else:
            src, tgt = e
            d1[v_idx[tgt], j] += 1
            d1[v_idx[src], j] -= 1

    # ── 调试：打印第一个外部面的完整解析过程 ──
    print(f"\n{'─' * 50}")
    print(f"调试：第一个外部面的解析")
    print(f"{'─' * 50}")
    # 验证第一个外部面的解析
    f0 = list(ext_faces_raw)[0]
    coeff0 = face_vertices_to_boundary_v2(f0, e_idx, get_rep)
    print(f"第一个外部面 {f0} 的边界系数：{coeff0}")
    print(f"涉及的边：{[(all_edges[k], c) for k, c in coeff0.items()]}")

    # 找 Hamming 距离=1 的相邻对
    print(f"相邻对（Hamming=1）：")
    for i in range(4):
        for j in range(4):
            if i < j:
                vi, vj = f0[i], f0[j]
                dist = sum(a != b for a, b in zip(vi, vj))
                ri, rj = get_rep(vi), get_rep(vj)
                fwd_in = (ri, rj) in e_idx
                rev_in = (rj, ri) in e_idx
                print(f"  {vi}→{vj} (dist={dist}): "
                      f"rep {ri}→{rj}, "
                      f"fwd_in_e_idx={fwd_in}, rev_in_e_idx={rev_in}")
    print(f"{'─' * 50}")

    # ∂_2（修正版）
    d2 = np.zeros((n1, n2), dtype=int)
    degenerate_faces = 0

    for k, f in enumerate(all_faces):
        if f == klein_face_id:
            d2[e_idx[loop_a], k] = 2
        else:
            # f 是四个原始顶点坐标的元组
            coeff = face_vertices_to_boundary_v2(f, e_idx, get_rep)
            if not coeff:
                degenerate_faces += 1
            for ei, c in coeff.items():
                d2[ei, k] += c

    print(f"退化面数（顶点被合并导致无法构成圈）：{degenerate_faces}")

    # 验证
    check = d1 @ d2
    ok = np.all(check == 0)
    print(f"[验证] ∂_1∘∂_2 = 0: {ok}")
    if not ok:
        bad_cols = [k for k in range(n2) if not np.all((d1 @ d2[:, k:k + 1]) == 0)]
        print(f"  ∂²≠0 的面（前5个）：{[all_faces[k] for k in bad_cols[:5]]}")

    h = compute_homology(d1, d2)
    print(f"同调群结果：")
    for key, val in h.items():
        print(f"  {key} = {val}")

    # 判断
    h1 = h['H_1']
    h2 = h['H_2']
    print(f"Euler 特征数验证：")
    chi_chain = n0 - n1 + n2
    from_homology = lambda s: int(s.split('^')[1]) if '^' in s else (0 if s == '0' else 1)
    print(f"  链复形：χ = {n0} - {n1} + {n2} = {chi_chain}")

    print(f"物理结论：")
    if not ok:
        print(f"  ∂²≠0，面的定向有问题，需进一步调试。")
    elif 'Z_2' in h1:
        print(f"  H_1 含 Z_2 扭转（来自显式编码的 Klein 面）。")
        print(f"  这是人工施加的结果，不是公理自发涌现。")
        print(f"  H_2 = {h2}，商空间含有额外的拓扑结构（超立方体骨架残留）。")
        print(f"  结论：Klein 瓶可以被嵌入框架，但不是公理必然产物。")
    else:
        print(f"  H_1 = {h1}，不含 Z_2 扭转。")
        print(f"  Klein 瓶在当前商空间中不存在，即使显式编码了粘合规则。")
        print(f"  结论：超立方体的几何结构与 Klein 瓶拓扑不相容。")

    return h


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

    # 实验四：弱化 A6（中截面内部双向）
    print("\n【实验四】弱化 A6（跨截面有向，截面内双向）")
    vertices4 = all_vertices(4)
    edges4 = apply_A4(vertices4)
    directed4 = apply_A6_dag_weak(edges4, vertices4)
    faces4 = apply_A7_faces(directed4, vertices4)
    print(f"有向边数：{len(directed4)}，面数：{len(faces4)}")
    d1_4, d2_4, _, _, _ = build_boundary_operators(vertices4, directed4, faces4)
    check4 = d1_4 @ d2_4
    print(f"∂_1∘∂_2=0: {np.all(check4 == 0)}")
    h4 = compute_homology(d1_4, d2_4)
    for k, v in h4.items():
        print(f"  {k} = {v}")

    run_quotient(N=4)

    # 实验七：先验证代码能否识别 Klein 瓶（基准测试）
    print("\n【先做基准测试，确认代码正确性】")
    h7 = run_klein_bottle_2d()

    # 实验六：显式粘合
    h6 = run_klein_bottle_with_loops()

    # h9 = run_experiment_9()
    h9 = run_experiment_9_fixed()
