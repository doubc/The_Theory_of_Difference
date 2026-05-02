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


def discrete_morse_matching(vertices, directed_edges, morse_func):
    """
    构造离散 Morse 配对（Morse matching）。

    离散 Morse 理论的核心：
    给定胞腔复形 K 和离散 Morse 函数 f，
    构造一个"梯度配对"——把每个非临界顶点与一条相邻边配对，
    把每条非临界边与一个相邻面配对，以此类推。

    配对规则（Forman）：
    顶点 v 与边 e 配对，当且仅当：
        f(e) <= f(v)（边的函数值不大于顶点的函数值）
        v 是 e 的一个端点
        e 没有与其他胞腔配对

    临界胞腔：没有被配对的胞腔。
    临界胞腔的数量 = 简化复形的胞腔数量。

    参数：
        vertices: 顶点列表
        directed_edges: 有向边列表 (src, tgt)
        morse_func: dict {vertex: float}，顶点的 Morse 函数值

    返回：
        critical_vertices: 临界顶点列表
        critical_edges: 临界边列表
        matching: dict {vertex: edge} 或 {edge: face}，配对关系
    """
    # A8 的 Morse 函数：f(v) = -rho(w(v))
    # 中截面权重最大 → f 值最小（取负）→ 中截面是 Morse 极小值

    # 这里先用贪心算法构造配对
    # 更精确的实现需要用 Morse 理论的标准算法

    matched_vertices = set()
    matched_edges = set()
    matching = {}

    # 按 Morse 函数值从小到大处理顶点
    sorted_verts = sorted(vertices, key=lambda v: morse_func[v])

    for v in sorted_verts:
        if v in matched_vertices:
            continue
        # 找 v 的相邻边中 f(e) <= f(v) 的边
        # 对有向边，f(e) 定义为两端点 f 值的平均
        # 或者用 min(f(src), f(tgt))
        best_edge = None
        best_val = float('inf')
        for e in directed_edges:
            src, tgt = e
            if src == v or tgt == v:
                if e in matched_edges:
                    continue
                f_e = (morse_func[src] + morse_func[tgt]) / 2
                if f_e <= morse_func[v] and f_e < best_val:
                    best_val = f_e
                    best_edge = e

        if best_edge is not None:
            matching[v] = best_edge
            matched_vertices.add(v)
            matched_edges.add(best_edge)

    critical_vertices = [v for v in vertices if v not in matched_vertices]
    critical_edges = [e for e in directed_edges if e not in matched_edges]

    return critical_vertices, critical_edges, matching


def morse_func_A8(vertex, N):
    """
    A8 的离散 Morse 函数。
    f(v) = -rho(w(v)) = -C(N, w(v)) / C(N, N/2)
    中截面（w = N/2）是极小值（f 最小）。
    """
    from math import comb
    w = sum(vertex)
    rho = comb(N, w) / comb(N, N // 2)
    return -rho  # 取负使中截面为极小值


def run_clem_morse(N=4):
    """
    CLEM 第一步：用 A8 的离散 Morse 函数简化 {0,1}^N，
    计算简化复形的同调群。

    预期：
    如果简化复形的同调群 = H*(R^3)（即 H_0=Z, H_1=0, H_2=0），
    则 D=3 是拓扑必然，CLEM 方向明确。
    """
    print(f"{'=' * 60}")
    print(f"【CLEM 实验一】A8 离散 Morse 简化，N={N}")
    print(f"{'=' * 60}")

    vertices = all_vertices(N)

    # Morse 函数值
    morse_vals = {v: morse_func_A8(v, N) for v in vertices}
    print(f"Morse 函数值分布（按汉明重量）：")
    from math import comb
    for w in range(N + 1):
        f_val = -comb(N, w) / comb(N, N // 2)
        count = comb(N, w)
        print(f"  w={w}: f={f_val:.4f}, 顶点数={count}")

    # A4 边
    edges = apply_A4(vertices)
    # A6 定向
    directed = apply_A6_dag(list(edges), vertices)
    # A7 面
    faces = apply_A7_faces(directed, vertices)

    print(f" 原始复形：V = {len(vertices)}, E = {len(directed)}, F = {len(faces)}    ")

    # 离散 Morse 配对
    crit_v, crit_e, matching = discrete_morse_matching(
        vertices, directed, morse_vals)

    print(f"    Morse    简化后：")
    print(f"  临界顶点数：{len(crit_v)}")
    print(f"  临界边数：{len(crit_e)}")
    print(f"  配对数：{len(matching)}")
    print(f"    临界顶点（Morse    极值点）：")
    for v in crit_v:
        print(f"    {v}，w={sum(v)}，f={morse_vals[v]:.4f}")

    # 在临界胞腔上构造链复形
    # 临界顶点 = C_0，临界边 = C_1，临界面 = C_2（需要进一步过滤）
    crit_faces = [f for f in faces
                  if all(e in crit_e or (e[1], e[0]) in crit_e
                         for e in [(f[0], f[1]), (f[1], f[2]), (f[2], f[3]), (f[3], f[0])]
                         if isinstance(f, tuple) and len(f) == 4)]

    print(f"  临界面数：{len(crit_faces)}")

    # 构造边界算子并计算同调群
    # （使用已有的 build_boundary_operators 和 compute_homology）
    if len(crit_v) > 0 and len(crit_e) >= 0:
        d1, d2, _, _, _ = build_boundary_operators(
            crit_v, crit_e, crit_faces)
    check = d1 @ d2
    print(f"  ∂_1∘∂_2=0: {np.all(check == 0)}")
    h = compute_homology(d1, d2)
    print(f"    同调群结果：")
    for k, v in h.items():
        print(f"  {k} = {v}")

    # 判断
    print(f"    CLEM    判断：")
    if h['H_0'] == 'Z' and h['H_1'] == '0' and h['H_2'] == '0':
        print(f"  *** H*(X) = H*(R^3) ***")
        print(f"  D=3 是拓扑必然！CLEM 方向：X ≃ R^3")
    elif h['H_0'] == 'Z' and h['H_1'] == '0' and h['H_2'] == 'Z':
        print(f"  H*(X) = H*(S^3)（三维球面）")
        print(f"  CLEM 方向：X ≃ S^3（紧致化的 R^3）")
    else:
        print(f"  H*(X) 非平凡，需要进一步分析。")
        print(f"  可能对应更复杂的流形或框架需要调整。")

    return h


def discrete_morse_matching_v2(vertices, directed_edges, faces_raw, morse_func):
    """
    修正版离散 Morse 配对。

    正确的配对规则（Forman 离散 Morse 理论）：

    0-1 配对（顶点与边）：
        顶点 v 与边 e=(v,u) 配对，当且仅当：
        1. f(e) <= f(v)，其中 f(e) = max(f(v), f(u))
           （等价于：f(u) <= f(v)，即 u 的 Morse 值不大于 v）
        2. v 和 e 都未被配对
        3. 配对后不产生有向环（梯度流无环条件）

    简化版（适用于超立方体 + A8）：
        按 f 值从大到小处理顶点（先消去 f 值最大的，即远离中截面的）
        对每个顶点 v，找一条相邻边 e=(v,u) 使得 f(u) <= f(v)
        （即找一条"下坡"的边）
        配对 v 与 e，把 v 和 e 都标记为非临界

    临界顶点 = 没有找到下坡边的顶点（局部极小值）
    临界边 = 没有被配对的边
    """
    matched_vertices = set()
    matched_edges = set()
    matching_v_to_e = {}  # 顶点 → 边

    # 构造邻接表：顶点 → 相邻有向边列表
    adj = {v: [] for v in vertices}
    for e in directed_edges:
        src, tgt = e
        adj[src].append(e)
        adj[tgt].append(e)  # 无向意义上的邻接

    # 按 f 值从大到小处理顶点（先消去远离中截面的顶点）
    # f 值越大（越负），越靠近中截面，越不应该被消去
    # f 值越小（越接近 0），越远离中截面，越应该被消去
    # 注意：morse_func 里中截面 f = -1（最负），极端态 f = -0.167（最接近 0）
    # 所以"远离中截面"= f 值最大（最接近 0）
    sorted_verts = sorted(vertices, key=lambda v: morse_func[v], reverse=True)
    # reverse=True：从 f 最大（最接近 0，极端态）开始处理

    for v in sorted_verts:
        if v in matched_vertices:
            continue

        # 找一条相邻边 e=(v,u) 或 e=(u,v)，使得 f(u) <= f(v)
        # 即找一条"下坡"或"平坡"的边（u 比 v 更靠近中截面）
        best_edge = None
        best_f_u = float('inf')

        for e in adj[v]:
            if e in matched_edges:
                continue
            src, tgt = e
            u = tgt if src == v else src
            if u in matched_vertices:
                continue
            f_u = morse_func[u]
            f_v = morse_func[v]
            # 找 f(u) <= f(v) 的边（u 比 v 更靠近中截面或同层）
            if f_u <= f_v and f_u < best_f_u:
                best_f_u = f_u
                best_edge = e

        if best_edge is not None:
            src, tgt = best_edge
            u = tgt if src == v else src
            matching_v_to_e[v] = best_edge
            matched_vertices.add(v)
            matched_vertices.add(u)  # u 也被消去（作为边的另一端）
            matched_edges.add(best_edge)

    critical_vertices = [v for v in vertices if v not in matched_vertices]
    critical_edges = [e for e in directed_edges if e not in matched_edges]

    return critical_vertices, critical_edges, matching_v_to_e


def get_critical_faces(faces_raw, critical_edges_set, get_changing_bits=None):
    """
    从原始面列表中筛选临界面。

    临界面的条件：面的四条边（在 Hamming 距离意义下）
    全部都是临界边（无论正向还是反向）。

    faces_raw: apply_A7_faces 返回的面列表，每个面是四个顶点的元组
    critical_edges_set: 临界有向边的集合（frozenset 或 set of tuples）
    """
    # 把临界边转成无向集合，方便查找
    crit_undirected = set()
    for e in critical_edges_set:
        src, tgt = e
        crit_undirected.add(frozenset([src, tgt]))

    critical_faces = []
    for face in faces_raw:
        v0, v1, v2, v3 = face

        # 找四条 Hamming=1 的边
        face_edges = []
        verts = [v0, v1, v2, v3]
        for i in range(4):
            for j in range(i + 1, 4):
                vi, vj = verts[i], verts[j]
                if sum(a != b for a, b in zip(vi, vj)) == 1:
                    face_edges.append(frozenset([vi, vj]))

        # 四边形应该有 4 条边
        if len(face_edges) != 4:
            continue

        # 检查所有边是否都是临界边
        if all(e in crit_undirected for e in face_edges):
            critical_faces.append(face)

    return critical_faces


def run_clem_morse_v2(N=4):
    """
    CLEM 实验一（修正版）：A8 离散 Morse 简化
    """
    print(f"{'=' * 60}")
    print(f"【CLEM 实验一修正版】A8 离散 Morse 简化，N={N}")
    print(f"{'=' * 60}")

    from math import comb
    vertices = all_vertices(N)

    # A8 的 Morse 函数
    def f_morse(v):
        w = sum(v)
        return -comb(N, w) / comb(N, N // 2)

    morse_vals = {v: f_morse(v) for v in vertices}

    print(f"Morse 函数值（按汉明重量）：")
    for w in range(N + 1):
        fv = -comb(N, w) / comb(N, N // 2)
        print(f"  w={w}: f={fv:.4f}, 顶点数={comb(N, w)}")

    # 构造原始复形
    edges = apply_A4(vertices)
    directed = apply_A6_dag(list(edges), vertices)
    faces_raw = apply_A7_faces(directed, vertices)
    print(f"    原始复形：V = {len(vertices)}, E = {len(directed)}, F = {len(faces_raw)}    ")

    # 离散 Morse 配对（修正版）
    crit_v, crit_e, matching = discrete_morse_matching_v2(
        vertices, directed, faces_raw, morse_vals)

    print(f"    Morse    简化后：")
    print(f"  临界顶点数：{len(crit_v)}")
    print(f"  临界边数：{len(crit_e)}")
    print(f"  配对（顶点消去）数：{len(matching)}")

    print(f"    临界顶点（w = {N // 2}    的中截面）：")
    for v in sorted(crit_v, key=lambda x: x):
        print(f"    {v}，w={sum(v)}，f={morse_vals[v]:.4f}")

    # 验证：临界边的端点是否都在临界顶点里
    crit_v_set = set(crit_v)
    bad_edges = [(s, t) for s, t in crit_e
                 if s not in crit_v_set or t not in crit_v_set]
    print(f"    端点不在临界顶点集里的边数：{len(bad_edges)}    ")
    if bad_edges:
        print(f"  （前3个）：{bad_edges[:3]}")
        print(f"  → 需要进一步过滤临界边")
        # 只保留两端点都在临界顶点集里的边
        crit_e_filtered = [(s, t) for s, t in crit_e
                           if s in crit_v_set and t in crit_v_set]
        print(f"  过滤后临界边数：{len(crit_e_filtered)}")
    else:
        crit_e_filtered = crit_e

    # 临界面
    crit_f = get_critical_faces(faces_raw, crit_e_filtered)
    print(f"  临界面数：{len(crit_f)}")

    # 构造链复形
    print(f"    链复形：C_0 = {len(crit_v)}, C_1 = {len(crit_e_filtered)}, C_2 = {len(crit_f)}    ")
    chi = len(crit_v) - len(crit_e_filtered) + len(crit_f)
    print(f"Euler 特征数：χ = {chi}")

    if len(crit_e_filtered) == 0 and len(crit_f) == 0:
        print(f"    只有顶点，无边无面。")
        print(f"H_0 = Z^{len(crit_v)}，H_1 = 0，H_2 = 0")
        print(f"    CLEM    判断：")
        if len(crit_v) == 1:
            print(f"  单点空间，可收缩，≃ R^3（平凡）")
        else:
            print(f"  {len(crit_v)} 个孤立点，H_0 = Z^{len(crit_v)}")
            print(f"  → 中截面的 6 个顶点是孤立的？需要检查边。")
        return

    d1, d2, _, _, _ = build_boundary_operators(
        crit_v, crit_e_filtered, crit_f)

    check = d1 @ d2
    ok = np.all(check == 0)
    print(f"∂_1∘∂_2 = 0: {ok}")

    h = compute_homology(d1, d2)
    print(f"    同调群结果：")
    for k, val in h.items():
        print(f"  {k} = {val}")

    # 关键判断
    print(f"    CLEM    判断：")
    h0, h1, h2 = h['H_0'], h['H_1'], h['H_2']

    if h0 == 'Z' and h1 == '0' and h2 == '0':
        print(f"  *** H*(X) = H*(R^3) ***")
        print(f"  A8 Morse 简化后的空间与 R^3 同调等价。")
        print(f"  D=3 是 A8 约束下的拓扑必然。")
        print(f"  CLEM 下一步：证明同伦等价（不只是同调等价）。")
    elif h0 == 'Z' and h1 == '0' and h2 == 'Z':
        print(f"  H*(X) = H*(S^3)（三维球面）")
        print(f"  空间是紧致的，对应紧致化的 R^3。")
    elif h0 == f'Z^{len(crit_v)}' or (len(crit_e_filtered) == 0):
        print(f"  中截面的 {len(crit_v)} 个顶点彼此孤立（无连接边）。")
        print(f"  这说明 A4 的边在 Morse 简化后被全部消去了。")
        print(f"  → A8 单独不足以产生连通的临界复形。")
        print(f"  → 需要检查 A7（循环闭合）是否能恢复连通性。")
    else:
        print(f"  H_0={h0}, H_1={h1}, H_2={h2}")
        print(f"  需要进一步分析。")

    # 中截面的图结构分析
    print(f"          - -- 中截面图结构分析 - --")
    print(f"中截面 6 个顶点之间的 Hamming=1 边：")
    mid_edges = []
    for i, v in enumerate(crit_v):
        for j, u in enumerate(crit_v):
            if i < j:
                if sum(a != b for a, b in zip(v, u)) == 1:
                    mid_edges.append((v, u))
    print(f"  边数：{len(mid_edges)}")
    for e in mid_edges:
        print(f"  {e[0]} — {e[1]}")

    if len(mid_edges) == 0:
        print(f"    中截面内没有    Hamming = 1    的边！")
        print(f"  （中截面顶点间最小 Hamming 距离为 2）")
        print(f"  → A4（单步翻转）无法在中截面内移动。")
        print(f"  → 这与之前实验二的结论一致。")
        print(f"  → 中截面是 A4 意义下的孤立点集。")

    return h


def discrete_morse_matching_v3(vertices, directed_edges, morse_func):
    """
    正确的 Forman 离散 Morse 配对。

    规则：
    顶点 v 与边 e=(v,u) 配对时：
        - v 被标记为非临界（消去）
        - e 被标记为非临界（消去）
        - u 不受影响，由后续处理决定是否临界

    临界顶点 = 没有被配对的顶点（Morse 极小值）
    临界边 = 没有被配对的边

    配对方向：从高 f 值顶点向低 f 值顶点配对
    （消去远离中截面的顶点，保留中截面附近的顶点）
    """
    matched_vertices = set()  # 被消去的顶点
    matched_edges = set()  # 被消去的边

    # 构造邻接表
    adj = {v: [] for v in vertices}
    for e in directed_edges:
        src, tgt = e
        adj[src].append(e)
        adj[tgt].append(e)

    # 按 f 值从大到小处理（先消去远离中截面的顶点）
    # f 最大（最接近 0）= 极端态（w=0 或 w=N），最先被消去
    sorted_verts = sorted(vertices,
                          key=lambda v: morse_func[v],
                          reverse=True)

    for v in sorted_verts:
        if v in matched_vertices:
            continue  # v 已经被消去，跳过

        # 找一条相邻边 e，使得边的另一端 u 满足 f(u) < f(v)
        # 即找一条严格下坡的边（不包括平坡）
        # 这样可以保证配对不产生环
        best_edge = None
        best_f_u = float('inf')

        for e in adj[v]:
            if e in matched_edges:
                continue
            src, tgt = e
            u = tgt if src == v else src
            if u in matched_vertices:
                continue
            f_u = morse_func[u]
            f_v = morse_func[v]
            # 严格下坡：f(u) < f(v)
            if f_u < f_v and f_u < best_f_u:
                best_f_u = f_u
                best_edge = e

        if best_edge is not None:
            # 只消去 v 和 e，不消去 u
            matched_vertices.add(v)
            matched_edges.add(best_edge)
            # u 保持未配对状态，等待后续处理
        # 如果找不到下坡边，v 是临界顶点（局部极小值），保留

    critical_vertices = [v for v in vertices if v not in matched_vertices]
    critical_edges = [e for e in directed_edges if e not in matched_edges]

    return critical_vertices, critical_edges


def run_clem_morse_v3(N=4):
    """
    CLEM 实验一（v3）：修正 Forman 配对规则
    """
    print(f"{'=' * 60}")
    print(f"【CLEM 实验一 v3】正确 Forman 配对，N={N}")
    print(f"{'=' * 60}")

    from math import comb
    vertices = all_vertices(N)

    def f_morse(v):
        w = sum(v)
        return -comb(N, w) / comb(N, N // 2)

    morse_vals = {v: f_morse(v) for v in vertices}

    edges = apply_A4(vertices)
    directed = apply_A6_dag(list(edges), vertices)
    faces_raw = apply_A7_faces(directed, vertices)
    print(f"原始复形：V={len(vertices)}, E={len(directed)}, F={len(faces_raw)}")

    crit_v, crit_e = discrete_morse_matching_v3(
        vertices, directed, morse_vals)

    print(f"\nMorse 简化后：")
    print(f"  临界顶点数：{len(crit_v)}")
    print(f"  临界边数：{len(crit_e)}")
    print(f"  消去顶点数：{len(vertices) - len(crit_v)}")
    print(f"  消去边数：{len(directed) - len(crit_e)}")

    print(f"\n  临界顶点（按汉明重量）：")
    from collections import Counter
    w_count = Counter(sum(v) for v in crit_v)
    for w in sorted(w_count):
        print(f"    w={w}: {w_count[w]} 个顶点")
    for v in sorted(crit_v):
        print(f"      {v}, f={morse_vals[v]:.4f}")

    # 检查临界边的端点是否都在临界顶点里
    crit_v_set = set(crit_v)
    bad = [(s, t) for s, t in crit_e
           if s not in crit_v_set or t not in crit_v_set]
    print(f"\n  临界边端点不在临界顶点集的边数：{len(bad)}")

    # 过滤临界边（只保留两端都在临界顶点集里的边）
    crit_e_clean = [(s, t) for s, t in crit_e
                    if s in crit_v_set and t in crit_v_set]
    print(f"  过滤后临界边数：{len(crit_e_clean)}")

    # 临界面
    crit_f = get_critical_faces(faces_raw, crit_e_clean)
    print(f"  临界面数：{len(crit_f)}")

    n0, n1, n2 = len(crit_v), len(crit_e_clean), len(crit_f)
    chi = n0 - n1 + n2
    print(f"\n链复形：C_0={n0}, C_1={n1}, C_2={n2}")
    print(f"Euler 特征数：χ = {chi}")

    if n0 == 0:
        print("临界顶点为空，配对逻辑仍有问题。")
        return

    if n1 == 0:
        print(f"\n无临界边。H_0=Z^{n0}, H_1=0, H_2=0")
        print(f"\n--- 中截面连通性分析 ---")
        print(f"临界顶点间的 Hamming 距离分布：")
        vl = sorted(crit_v)
        dists = Counter()
        for i in range(len(vl)):
            for j in range(i + 1, len(vl)):
                d = sum(a != b for a, b in zip(vl[i], vl[j]))
                dists[d] += 1
        for d in sorted(dists):
            print(f"  d={d}: {dists[d]} 对")
        print(f"\nA4 要求 d=1，中截面内最小距离为 "
              f"{min(dists.keys())} → 无 A4 边")
        print(f"CLEM 结论：A8 Morse 简化产生孤立点集，")
        print(f"需要 A7（循环闭合）恢复连通性。")
        return

    d1, d2, _, _, _ = build_boundary_operators(
        crit_v, crit_e_clean, crit_f)
    check = d1 @ d2
    ok = np.all(check == 0)
    print(f"∂_1∘∂_2=0: {ok}")

    h = compute_homology(d1, d2)
    print(f"\n同调群结果：")
    for k, val in h.items():
        print(f"  {k} = {val}")

    print(f"\nCLEM 判断：")
    h0, h1, h2 = h['H_0'], h['H_1'], h['H_2']
    if h0 == 'Z' and h1 == '0' and h2 == '0':
        print(f"  *** H*(X) ≅ H*(R³) — D=3 是拓扑必然 ***")
    elif h0 == 'Z' and h1 == '0' and h2 == 'Z':
        print(f"  H*(X) ≅ H*(S³) — 紧致化的 R³")
    else:
        print(f"  H_0={h0}, H_1={h1}, H_2={h2}，需进一步分析")

    return h


def apply_A1_prime_edges(vertices, N):
    """
    A1' 的横向边：Hamming 距离为 2，且两个不同比特位
    恰好是一个从 0→1、另一个从 1→0（横向交换）。

    在中截面（w=N/2）内，这对应于比特对的横向翻转：
    (x_i=1, x_j=0) → (x_i=0, x_j=1)，保持汉明重量不变。

    更一般地，A1' 边连接所有满足以下条件的顶点对：
    d_H(v, u) = 2，且 w(v) = w(u)（汉明重量相同）
    即：同层内的横向跃迁。
    """
    edges = set()
    for i, v in enumerate(vertices):
        for j, u in enumerate(vertices):
            if i >= j:
                continue
            if sum(v) != sum(u):
                continue  # 不同层，不是横向边
            dist = sum(a != b for a, b in zip(v, u))
            if dist == 2:
                edges.add(frozenset([v, u]))
    return list(edges)


def run_clem_morse_A1prime(N=4):
    """
    CLEM 实验二：A8 Morse 简化 + A1' 横向边

    在临界顶点（中截面）上，加入 A1' 允许的横向边，
    计算扩充后的临界复形的同调群。
    """
    print(f"{'=' * 60}")
    print(f"【CLEM 实验二】A8 Morse + A1' 横向边，N={N}")
    print(f"{'=' * 60}")

    from math import comb
    vertices = all_vertices(N)

    def f_morse(v):
        w = sum(v)
        return -comb(N, w) / comb(N, N // 2)

    morse_vals = {v: f_morse(v) for v in vertices}

    # A4 边 + A6 定向
    edges_A4 = apply_A4(vertices)
    directed_A4 = apply_A6_dag(list(edges_A4), vertices)
    faces_raw = apply_A7_faces(directed_A4, vertices)

    # Morse 简化（已知结果：临界顶点 = 中截面 6 个顶点）
    crit_v, _ = discrete_morse_matching_v3(
        vertices, directed_A4, morse_vals)
    crit_v_set = set(crit_v)
    print(f"临界顶点（中截面）：{len(crit_v)} 个")

    # A1' 横向边（在中截面内）
    a1p_edges_all = apply_A1_prime_edges(vertices, N)
    # 只保留两端都在临界顶点集里的横向边
    a1p_edges_crit = [e for e in a1p_edges_all
                      if all(v in crit_v_set for v in e)]
    print(f"A1' 横向边（全空间）：{len(a1p_edges_all)} 条")
    print(f"A1' 横向边（中截面内）：{len(a1p_edges_crit)} 条")

    # 对中截面的 A1' 边用 A6 定向
    a1p_directed = apply_A6_dag(a1p_edges_crit, crit_v)
    print(f"A1' 有向边（中截面内）：{len(a1p_directed)} 条")

    # 在中截面上构造 A7 面（由 A1' 边围成的三角形或四边形）
    faces_a1p = apply_A7_faces(a1p_directed, crit_v)
    print(f"A1' 面（中截面内）：{len(faces_a1p)} 个")

    n0 = len(crit_v)
    n1 = len(a1p_directed)
    n2 = len(faces_a1p)
    chi = n0 - n1 + n2
    print(f"    链复形：C_0 = {n0}, C_1 = {n1}, C_2 = {n2}    ")
    print(f"Euler 特征数：χ = {chi}")

    if n1 == 0:
        print("无边，无法计算同调。")
        return

    d1, d2, _, _, _ = build_boundary_operators(
        crit_v, a1p_directed, faces_a1p)
    check = d1 @ d2
    ok = np.all(check == 0)
    print(f"∂_1∘∂_2=0: {ok}")

    h = compute_homology(d1, d2)
    print(f"    同调群结果：")
    for k, val in h.items():
        print(f"  {k} = {val}")

    print(f"    CLEM    判断：")
    h0, h1, h2 = h['H_0'], h['H_1'], h['H_2']
    if h0 == 'Z' and h1 == '0' and h2 == 'Z':
        print(f"  *** H*(X) ≅ H*(S²) ***")
        print(f"  中截面 = 八面体 ≃ S²（二维球面）")
        print(f"  物理含义：横向自由度形成二维球面，")
        print(f"  对应 A1' 的 SO(3) 或 SU(2) 对称性。")
        print(f"  注意：这是 S²，不是 R³。")
        print(f"  CLEM 下一步：加入层级方向（A1）恢复 R³。")
    elif h0 == 'Z' and h1 == '0' and h2 == '0':
        print(f"  H*(X) ≅ H*(R³) — 单连通，无高阶同调")
    elif h0 == 'Z' and h1 == 'Z^2' and h2 == 'Z':
        print(f"  H*(X) ≅ H*(T²)（环面）")
    else:
        print(f"  H_0={h0}, H_1={h1}, H_2={h2}")
        # 与八面体的理论值对比
        print(f"    理论预期（八面体 ≃ S²）：")
        print(f"    H_0=Z, H_1=0, H_2=Z")
        print(f"  实际结果与预期{'一致' if h0 == 'Z' and h1 == '0' and h2 == 'Z' else '不一致'}。")

    # 八面体结构验证
    print(f"          - -- 八面体结构验证 - --")
    print(f"理论：正八面体有 6 顶点、12 边、8 三角面")
    print(f"实际：{n0} 顶点、{n1} 边、{n2} 面")
    print(f"注意：apply_A7_faces 寻找四边形面，")
    print(f"八面体的面是三角形，可能未被识别。")
    print(f"如果 n2=0，需要单独实现三角面识别。")

    return h


def apply_triangular_faces(directed_edges, vertices):
    """
    识别三角形面：三个顶点两两之间都有边（有向或反向）。

    返回三角形面列表，每个面是三个顶点的元组，
    按标准定向（逆时针）排列。
    """
    # 构造无向邻接集合
    undirected = set()
    for e in directed_edges:
        src, tgt = e
        undirected.add(frozenset([src, tgt]))

    e_idx = {e: i for i, e in enumerate(directed_edges)}

    triangles = []
    vl = list(vertices)
    n = len(vl)

    for i in range(n):
        for j in range(i + 1, n):
            for k in range(j + 1, n):
                vi, vj, vk = vl[i], vl[j], vl[k]
                # 检查三条边是否都存在
                if (frozenset([vi, vj]) in undirected and
                        frozenset([vj, vk]) in undirected and
                        frozenset([vi, vk]) in undirected):
                    triangles.append((vi, vj, vk))

    return triangles


def triangle_boundary(tri, e_idx):
    """
    计算三角形面的边界算子列。

    三角形 (v0, v1, v2) 的标准定向边界：
    ∂_2(F) = (v0→v1) - (v0→v2) + (v1→v2)

    对每条边，查 e_idx：
        正向在 e_idx 里：系数 +sign
        反向在 e_idx 里：系数 -sign
    """
    v0, v1, v2 = tri
    # 三条有向边，带符号
    oriented = [
        (v0, v1, +1),
        (v0, v2, -1),
        (v1, v2, +1),
    ]
    coeff = {}
    for src, tgt, sign in oriented:
        fwd = (src, tgt)
        rev = (tgt, src)
        if fwd in e_idx:
            coeff[e_idx[fwd]] = coeff.get(e_idx[fwd], 0) + sign
        elif rev in e_idx:
            coeff[e_idx[rev]] = coeff.get(e_idx[rev], 0) - sign
    return coeff


def run_clem_octahedron(N=4):
    """
    CLEM 实验三：八面体同调验证

    在中截面 + A1' 边的基础上，加入三角面，
    验证同调群是否等于 S²（H_0=Z, H_1=0, H_2=Z）。
    """
    print(f"{'=' * 60}")
    print(f"【CLEM 实验三】八面体同调（加入三角面），N={N}")
    print(f"{'=' * 60}")

    from math import comb
    vertices = all_vertices(N)

    def f_morse(v):
        w = sum(v)
        return -comb(N, w) / comb(N, N // 2)

    morse_vals = {v: f_morse(v) for v in vertices}

    # Morse 简化得到中截面 6 个顶点
    edges_A4 = apply_A4(vertices)
    directed_A4 = apply_A6_dag(list(edges_A4), vertices)
    crit_v, _ = discrete_morse_matching_v3(
        vertices, directed_A4, morse_vals)
    crit_v_set = set(crit_v)
    crit_v_sorted = sorted(crit_v)
    print(f"中截面顶点：{len(crit_v)} 个")

    # A1' 横向边（中截面内，d=2）
    a1p_edges = [e for e in apply_A1_prime_edges(vertices, N)
                 if all(v in crit_v_set for v in e)]
    a1p_directed = apply_A6_dag(a1p_edges, crit_v)
    print(f"A1' 有向边：{len(a1p_directed)} 条")

    e_idx = {e: i for i, e in enumerate(a1p_directed)}
    n1 = len(a1p_directed)

    # 三角面
    triangles = apply_triangular_faces(a1p_directed, crit_v_sorted)
    print(f"三角面：{len(triangles)} 个（理论：8 个）")

    n0 = len(crit_v)
    n2 = len(triangles)
    chi = n0 - n1 + n2
    print(f"链复形：C_0={n0}, C_1={n1}, C_2={n2}")
    print(f"Euler 特征数：χ = {chi}（八面体理论值 = 2）")

    # ∂_1
    v_idx = {v: i for i, v in enumerate(crit_v_sorted)}
    d1 = np.zeros((n0, n1), dtype=int)
    for j, e in enumerate(a1p_directed):
        src, tgt = e
        d1[v_idx[tgt], j] += 1
        d1[v_idx[src], j] -= 1

    # ∂_2（三角面）
    d2 = np.zeros((n1, n2), dtype=int)
    for k, tri in enumerate(triangles):
        coeff = triangle_boundary(tri, e_idx)
        for ei, c in coeff.items():
            d2[ei, k] += c

    check = d1 @ d2
    ok = np.all(check == 0)
    print(f"∂_1∘∂_2=0: {ok}")
    if not ok:
        print(f"  警告：边界算子不满足 ∂²=0，三角面定向有问题。")

    h = compute_homology(d1, d2)
    print(f"同调群结果：")
    for k, val in h.items():
        print(f"  {k} = {val}")

    print(f"CLEM 判断：")
    h0, h1, h2 = h['H_0'], h['H_1'], h['H_2']
    if h0 == 'Z' and h1 == '0' and h2 == 'Z':
        print(f"  *** H*(X) ≅ H*(S²) ***")
        print(f"  A8 Morse 简化 + A1' 横向边 → 中截面 ≃ S²")
        print(f"  物理含义：")
        print(f"    横向自由度（A1'）形成二维球面 S²")
        print(f"    对应 SO(3)/U(1) ≅ S² 的靶空间结构")
        print(f"    这是 A1' → SU(2)/U(1) → S² 推导链的拓扑验证")
        print(f"  CLEM 下一步：")
        print(f"    加入 A1（层级方向）构造完整空间")
        print(f"    完整空间应为 S² × R 或其纤维丛结构")
        print(f"    D=3 来自 dim(S²) + dim(R) = 2 + 1 = 3")
    elif h0 == 'Z' and h1 == '0' and h2 == '0':
        print(f"  H*(X) ≅ H*(R³)，单连通无高阶同调")
        print(f"  三角面填满了所有圈，空间可收缩")
    else:
        print(f"  H_0={h0}, H_1={h1}, H_2={h2}")
        print(f"  与 S² 预期不符，需检查三角面定向。")

    # 补充：打印前几个三角面供检查
    print(f"前 4 个三角面：")
    for tri in triangles[:4]:
        print(f"  {tri}")

    return h


def run_clem_full_space(N=4):
    """
    CLEM 实验四：完整空间 = A1 层级方向 + A1' 横向结构

    构造策略：
    - 顶点：全部 2^N 个顶点（所有汉明重量层）
    - 边：A4 边（层间，d_H=1）+ A1' 边（层内，d_H=2，w相同）
    - 面：A4 四边形面 + A1' 三角面
    - A6 定向：A4 边按汉明重量方向定向，A1' 边按 A6 DAG 定向
    - A8 权重：作为 Morse 函数，不筛选顶点

    预期：
    完整空间的同调群应该介于 S² 和 R³ 之间，
    取决于层间连接如何改变中截面的拓扑。
    """
    print(f"{'=' * 60}")
    print(f"【CLEM 实验四】完整空间（A1+A1' 联合），N={N}")
    print(f"{'=' * 60}")

    vertices = all_vertices(N)
    v_idx = {v: i for i, v in enumerate(sorted(vertices))}
    vertices_sorted = sorted(vertices)
    n0 = len(vertices_sorted)

    # A4 边（层间，d_H=1）
    edges_A4 = apply_A4(vertices)
    directed_A4 = apply_A6_dag(list(edges_A4), vertices)

    # A1' 边（层内，d_H=2，w 相同）
    a1p_edges = apply_A1_prime_edges(vertices, N)
    a1p_directed = apply_A6_dag(a1p_edges, vertices)

    # 合并所有边
    all_directed = directed_A4 + a1p_directed
    # 去重
    all_directed = list(set(all_directed))
    n1 = len(all_directed)
    e_idx = {e: i for i, e in enumerate(all_directed)}

    print(f"顶点数：{n0}")
    print(f"A4 有向边：{len(directed_A4)} 条")
    print(f"A1' 有向边：{len(a1p_directed)} 条")
    print(f"合并后总边数：{n1} 条")

    # 面：A4 四边形面 + A1' 三角面（全空间）
    faces_A4 = apply_A7_faces(directed_A4, vertices)
    faces_A1p = apply_triangular_faces(all_directed, vertices_sorted)
    # 只保留 A1' 三角面（三条边都是 A1' 边）
    a1p_edge_set = set(a1p_directed)
    a1p_undirected = set(frozenset(e) for e in a1p_directed)
    faces_A1p_pure = []
    for tri in faces_A1p:
        v0, v1, v2 = tri
        edges_of_tri = [
            frozenset([v0, v1]),
            frozenset([v1, v2]),
            frozenset([v0, v2])
        ]
        if all(e in a1p_undirected for e in edges_of_tri):
            faces_A1p_pure.append(tri)

    all_faces = list(faces_A4) + faces_A1p_pure
    n2 = len(all_faces)
    print(f"A4 四边形面：{len(faces_A4)} 个")
    print(f"A1' 纯三角面：{len(faces_A1p_pure)} 个")
    print(f"合并后总面数：{n2} 个")

    chi = n0 - n1 + n2
    print(f"链复形：C_0={n0}, C_1={n1}, C_2={n2}")
    print(f"Euler 特征数：χ = {chi}")

    # ∂_1
    d1 = np.zeros((n0, n1), dtype=int)
    for j, e in enumerate(all_directed):
        src, tgt = e
        d1[v_idx[tgt], j] += 1
        d1[v_idx[src], j] -= 1

    # ∂_2
    d2 = np.zeros((n1, n2), dtype=int)
    for k, f in enumerate(all_faces):
        if isinstance(f, tuple) and len(f) == 4:
            # A4 四边形面
            coeff = face_vertices_to_boundary_v2(f, e_idx, lambda v: v)
            for ei, c in coeff.items():
                d2[ei, k] += c
        elif isinstance(f, tuple) and len(f) == 3:
            # A1' 三角面
            coeff = triangle_boundary(f, e_idx)
            for ei, c in coeff.items():
                d2[ei, k] += c

    check = d1 @ d2
    ok = np.all(check == 0)
    print(f"∂_1∘∂_2=0: {ok}")
    if not ok:
        bad = np.argwhere(check != 0)
        print(f"  非零位置数：{len(bad)}，前3个面：")
        seen = set()
        for _, j in bad[:3]:
            if j not in seen:
                print(f"    面[{j}] = {all_faces[j]}")
                seen.add(j)
    # ── 诊断统计：检查 d2 的零列和边界分布 ──────────────
    zero_cols = sum(1 for k in range(n2) if np.all(d2[:, k] == 0))
    col_nnz = [np.count_nonzero(d2[:, k]) for k in range(n2)]
    from collections import Counter
    nnz_dist = Counter(col_nnz)

    print(f"\n[诊断] ∂_2 矩阵分析：")
    print(f"  零列数（边界为空的面）：{zero_cols}")
    print(f"  列非零元素分布：{dict(sorted(nnz_dist.items()))}")
    # 预期：40个面中，四边形应为4个非零，三角形应为3个非零

    # 打印前几个零边界面示例
    zero_examples = [all_faces[k] for k in range(n2) if np.all(d2[:, k] == 0)][:3]
    if zero_examples:
        print(f"  零边界面示例：{zero_examples}")
    # ───────────────────────────────────────────────────

    h = compute_homology(d1, d2)
    print(f"同调群结果：")
    for k, val in h.items():
        print(f"  {k} = {val}")

    print(f"CLEM 判断：")
    h0, h1, h2 = h['H_0'], h['H_1'], h['H_2']
    if h0 == 'Z' and h1 == '0' and h2 == '0':
        print(f"  *** H*(X) ≅ H*(R³) ***")
        print(f"  完整空间单连通，无高阶同调。")
        print(f"  A1 层级方向把 S² 的 H_2=Z 杀死了。")
        print(f"  D=3 来自 A1（1维）+ A1'（2维 S²）的纤维丛结构。")
        print(f"  CLEM 核心命题数值验证通过。")
    elif h0 == 'Z' and h1 == '0' and h2 == 'Z':
        print(f"  H*(X) ≅ H*(S²×R)，层级方向未能杀死 H_2。")
        print(f"  可能原因：A4 的层间连接不足以填充 S² 的空腔。")
        print(f"  需要检查 A7 是否要求更多的 2-胞腔。")
    elif h0 == 'Z' and h1 == '0' and h2 == 'Z^2':
        print(f"  H_2=Z²，存在两个独立的球面结构。")
        print(f"  可能对应 N=4 的两个独立 S² 纤维。")
    else:
        print(f"  H_0={h0}, H_1={h1}, H_2={h2}")
        print(f"  需要进一步分析。")

    return h


def apply_mixed_triangular_faces(all_directed, vertices):
    """
    识别所有三角形面：三个顶点两两之间都有边
    （无论是 A4 边还是 A1' 边）。

    这包括：
    - 纯 A4 三角形（不存在，超立方体无三角形）
    - 纯 A1' 三角形（已在实验三中处理）
    - 混合三角形（A4+A1' 混合边）← 新增
    """
    undirected = set()
    for e in all_directed:
        src, tgt = e
        undirected.add(frozenset([src, tgt]))

    triangles = []
    vl = sorted(vertices)
    n = len(vl)
    for i in range(n):
        for j in range(i + 1, n):
            for k in range(j + 1, n):
                vi, vj, vk = vl[i], vl[j], vl[k]
                if (frozenset([vi, vj]) in undirected and
                        frozenset([vj, vk]) in undirected and
                        frozenset([vi, vk]) in undirected):
                    triangles.append((vi, vj, vk))
    return triangles


def run_clem_full_v2(N=4):
    """
    CLEM 实验五：完整空间，包含所有混合面

    面的类型：
    1. A4 四边形面（纯 A4 边围成）
    2. A1' 纯三角面（纯 A1' 边围成）
    3. 混合三角面（A4+A1' 混合边围成）← 新增

    预期：混合面填充层间-层内的混合圈，
    同调群向 H*(R³) 靠近。
    """
    print(f"{'=' * 60}")
    print(f"【CLEM 实验五】完整空间含混合面，N={N}")
    print(f"{'=' * 60}")

    vertices = all_vertices(N)
    vertices_sorted = sorted(vertices)
    v_idx = {v: i for i, v in enumerate(vertices_sorted)}
    n0 = len(vertices_sorted)

    # 所有边
    edges_A4 = apply_A4(vertices)
    directed_A4 = apply_A6_dag(list(edges_A4), vertices)
    a1p_edges = apply_A1_prime_edges(vertices, N)
    a1p_directed = apply_A6_dag(a1p_edges, vertices)
    all_directed = list(set(directed_A4 + a1p_directed))
    n1 = len(all_directed)
    e_idx = {e: i for i, e in enumerate(all_directed)}

    print(f"A4 边：{len(directed_A4)}, A1' 边：{len(a1p_directed)}, 合计：{n1}")

    # 所有面（包含混合面）
    faces_A4 = list(apply_A7_faces(directed_A4, vertices))

    # 所有三角面（纯 A1' + 混合）
    all_triangles = apply_mixed_triangular_faces(all_directed, vertices)

    # 分类统计
    a1p_undi = set(frozenset(e) for e in a1p_directed)
    a4_undi = set(frozenset(e) for e in directed_A4)

    pure_a1p_tri = []
    mixed_tri = []
    for tri in all_triangles:
        edges = [frozenset([tri[i], tri[j]])
                 for i, j in [(0, 1), (1, 2), (0, 2)]]
        if all(e in a1p_undi for e in edges):
            pure_a1p_tri.append(tri)
        else:
            mixed_tri.append(tri)

    all_faces = faces_A4 + pure_a1p_tri + mixed_tri
    n2 = len(all_faces)

    print(f"A4 四边形面：{len(faces_A4)}")
    print(f"A1' 纯三角面：{len(pure_a1p_tri)}")
    print(f"混合三角面：{len(mixed_tri)}")
    print(f"合计面数：{n2}")

    chi = n0 - n1 + n2
    print(f"链复形：C_0={n0}, C_1={n1}, C_2={n2}")
    print(f"Euler 特征数：χ = {chi}")

    # ∂_1
    d1 = np.zeros((n0, n1), dtype=int)
    for j, e in enumerate(all_directed):
        src, tgt = e
        d1[v_idx[tgt], j] += 1
        d1[v_idx[src], j] -= 1

    # ∂_2
    d2 = np.zeros((n1, n2), dtype=int)
    zero_cols = 0
    for k, f in enumerate(all_faces):
        if len(f) == 4:
            coeff = face_vertices_to_boundary_v2(f, e_idx, lambda v: v)
        else:
            coeff = triangle_boundary(f, e_idx)
        if not coeff:
            zero_cols += 1
        for ei, c in coeff.items():
            d2[ei, k] += c

    print(f"∂_2 零列数：{zero_cols}")
    check = d1 @ d2
    ok = np.all(check == 0)
    print(f"∂_1∘∂_2=0: {ok}")
    if not ok:
        bad_cols = [k for k in range(n2)
                    if not np.all((d1 @ d2[:, k:k + 1]) == 0)]
        print(f"  ∂²≠0 的面数：{len(bad_cols)}，前3个：")
        for k in bad_cols[:3]:
            print(f"    面[{k}]={all_faces[k]}")

    h = compute_homology(d1, d2)
    print(f"同调群结果：")
    for k, val in h.items():
        print(f"  {k} = {val}")

    print(f"CLEM 判断：")
    h0, h1, h2 = h['H_0'], h['H_1'], h['H_2']
    if h0 == 'Z' and h1 == '0' and h2 == '0':
        print(f"  *** H*(X) ≅ H*(R³) — CLEM 核心命题验证通过 ***")
        print(f"  A1（层级）+ A1'（横向）+ A8（中截面偏好）")
        print(f"  联合约束下，{2 ** N} 个状态的空间与 R³ 同调等价。")
        print(f"  D=3 是公理体系的拓扑必然结果。")
    elif h0 == 'Z' and h1 == '0' and h2 == 'Z':
        print(f"  H*(X) ≅ H*(S²)，仍有球面结构残留。")
        print(f"  需要更多混合面或 3-胞腔来填充。")
    elif h0 == 'Z' and h1 == '0':
        print(f"  H_1=0（单连通），H_2={h2}。")
        print(f"  层间连接消除了所有 1-圈，")
        print(f"  但仍有高阶球面结构。")
    else:
        print(f"  H_0={h0}, H_1={h1}, H_2={h2}")
        if h1 != '0':
            print(f"  H_1≠0，仍有未填充的 1-圈。")
            print(f"  可能还有更多类型的混合面未被识别。")

    # 诊断：各类面的贡献
    print(f"诊断（分类面的秩贡献）：")
    for label, cnt in [("A4四边形", len(faces_A4)),
                       ("A1'三角", len(pure_a1p_tri)),
                       ("混合三角", len(mixed_tri))]:
        print(f"  {label}：{cnt} 个")

    return h


def apply_3cells(all_directed, vertices):
    """
    识别所有 3-胞腔（四面体和立方体）。

    策略：找出四个顶点，使得任意两个顶点之间都有边
    （完全图 K_4），构成四面体（最小 3-胞腔）。

    同时找出八个顶点构成的三维子立方体
    （纯 A4 边，Hamming 距离 1 的三维超立方体）。
    """
    undirected = set()
    for e in all_directed:
        undirected.add(frozenset(e))

    vl = sorted(vertices)
    n = len(vl)

    # 四面体（K_4：4个顶点两两相连）
    tetrahedra = []
    for i in range(n):
        for j in range(i + 1, n):
            for k in range(j + 1, n):
                for l in range(k + 1, n):
                    vi, vj, vk, vl_ = vl[i], vl[j], vl[k], vl[l]
                    pairs = [(vi, vj), (vi, vk), (vi, vl_),
                             (vj, vk), (vj, vl_), (vk, vl_)]
                    if all(frozenset(p) in undirected for p in pairs):
                        tetrahedra.append((vi, vj, vk, vl_))

    return tetrahedra


def tetrahedron_boundary(tet, e_idx, all_faces_idx):
    """
    四面体的边界算子：∂_3(T) = 四个三角面的带符号和。

    四面体 T = (v0,v1,v2,v3) 的标准定向边界：
    ∂_3(T) = [v1,v2,v3] - [v0,v2,v3] + [v0,v1,v3] - [v0,v1,v2]

    all_faces_idx: dict {face_tuple: column_index}
    """
    v0, v1, v2, v3 = tet
    # 四个三角面，带符号
    faces_signed = [
        ((v1, v2, v3), +1),
        ((v0, v2, v3), -1),
        ((v0, v1, v3), +1),
        ((v0, v1, v2), -1),
    ]
    coeff = {}
    for face_verts, sign in faces_signed:
        # 查找面（可能以不同顶点顺序存储）
        # 尝试所有排列
        from itertools import permutations
        found = False
        for perm in permutations(face_verts):
            if perm in all_faces_idx:
                fi = all_faces_idx[perm]
                coeff[fi] = coeff.get(fi, 0) + sign
                found = True
                break
        if not found:
            # 面不在 all_faces 里，说明缺少这个面
            pass
    return coeff


def run_clem_full_v3(N=4):
    """
    CLEM 实验六：加入 3-胞腔（四面体）

    目标：用 3-胞腔杀死 H_2，
    验证完整空间是否与 R³ 同调等价。
    """
    print(f"{'=' * 60}")
    print(f"【CLEM 实验六】加入 3-胞腔，N={N}")
    print(f"{'=' * 60}")

    vertices = all_vertices(N)
    vertices_sorted = sorted(vertices)
    v_idx = {v: i for i, v in enumerate(vertices_sorted)}
    n0 = len(vertices_sorted)

    # 所有边
    edges_A4 = apply_A4(vertices)
    directed_A4 = apply_A6_dag(list(edges_A4), vertices)
    a1p_edges = apply_A1_prime_edges(vertices, N)
    a1p_directed = apply_A6_dag(a1p_edges, vertices)
    all_directed = list(set(directed_A4 + a1p_directed))
    n1 = len(all_directed)
    e_idx = {e: i for i, e in enumerate(all_directed)}

    # 所有面（同实验五）
    faces_A4 = list(apply_A7_faces(directed_A4, vertices))
    a1p_undi = set(frozenset(e) for e in a1p_directed)
    all_tris = apply_mixed_triangular_faces(all_directed, vertices)
    pure_a1p = [t for t in all_tris
                if all(frozenset([t[i], t[j]]) in a1p_undi
                       for i, j in [(0, 1), (1, 2), (0, 2)])]
    mixed = [t for t in all_tris if t not in set(pure_a1p)]
    all_faces = faces_A4 + pure_a1p + mixed
    n2 = len(all_faces)
    f_idx = {f: i for i, f in enumerate(all_faces)}

    print(f"C_1={n1}, C_2={n2}")

    # 3-胞腔（四面体）
    tetrahedra = apply_3cells(all_directed, vertices)
    n3 = len(tetrahedra)
    print(f"四面体数：{n3}")
    print(f"链复形：C_0={n0},C_1={n1},C_2={n2},C_3={n3}")
    chi = n0 - n1 + n2 - n3
    print(f"Euler 特征数：χ = {chi}")

    # ∂_1
    d1 = np.zeros((n0, n1), dtype=int)
    for j, e in enumerate(all_directed):
        src, tgt = e
        d1[v_idx[tgt], j] += 1
        d1[v_idx[src], j] -= 1

    # ∂_2
    d2 = np.zeros((n1, n2), dtype=int)
    for k, f in enumerate(all_faces):
        if len(f) == 4:
            coeff = face_vertices_to_boundary_v2(f, e_idx, lambda v: v)
        else:
            coeff = triangle_boundary(f, e_idx)
        for ei, c in coeff.items():
            d2[ei, k] += c

    print(f"∂_1∘∂_2=0: {np.all(d1 @ d2 == 0)}")

    # ∂_3
    d3 = np.zeros((n2, n3), dtype=int)
    missing_faces = 0
    for l, tet in enumerate(tetrahedra):
        coeff = tetrahedron_boundary(tet, e_idx, f_idx)
        if len(coeff) < 4:
            missing_faces += len(coeff)
        for fi, c in coeff.items():
            d3[fi, l] += c

    print(f"∂_2∘∂_3=0: {np.all(d2 @ d3 == 0)}")
    print(f"四面体边界中缺失的面数：{missing_faces}")

    # H_2 = ker(∂_2) / im(∂_3)
    # H_3 = ker(∂_3) / im(∂_4)，∂_4=0
    # 用 Smith 标准型计算

    def homology_with_d3(d2, d3):
        """计算 H_2 = ker(d2) / im(d3)"""
        # ker(d2)
        # im(d3)
        # 用 Smith 标准型
        # 这里复用 compute_homology 的逻辑
        # H_2: 把 d2 作为 ∂_2，d3 作为 ∂_3
        return compute_homology(d2, d3)

    # 完整同调
    print(f"计算 H_0, H_1...")
    h01 = compute_homology(d1, d2)
    print(f"计算 H_2, H_3...")
    h23 = homology_with_d3(d2, d3)

    print(f"同调群结果：")
    print(f"  H_0 = {h01['H_0']}")
    print(f"  H_1 = {h01['H_1']}")
    print(f"  H_2 = {h23['H_0']}")  # ker(d2)/im(d3) 对应 H_2
    print(f"  H_3 = {h23['H_1']}")  # ker(d3)/im(0) 对应 H_3

    h2_val = h23['H_0']
    h3_val = h23['H_1']

    print(f"CLEM 判断：")
    h0 = h01['H_0']
    h1 = h01['H_1']
    if h0 == 'Z' and h1 == '0' and h2_val == 'Z' and h3_val == '0':
        print(f"  H*(X) ≅ H*(S³)（三维球面）")
        print(f"  紧致化的 R³，对应有限 N 的边界效应。")
        print(f"  N→∞ 极限下趋向 H*(R³)。")
    elif h0 == 'Z' and h1 == '0' and h2_val == '0' and h3_val == '0':
        print(f"  *** H*(X) ≅ H*(R³) — CLEM 核心命题验证通过 ***")
        print(f"  D=3 是公理体系的拓扑必然结果。")
    elif h0 == 'Z' and h1 == '0':
        print(f"  单连通，H_2={h2_val}, H_3={h3_val}")
        if h2_val != '0':
            print(f"  仍有 H_2≠0，需要更多 3-胞腔或检查四面体边界。")
    else:
        print(f"  H_0={h0},H_1={h1},H_2={h2_val},H_3={h3_val}")

    return h01, h23


def compute_homology_chain(boundary_ops):
    """
    计算完整链复形的同调群。

    boundary_ops: [d1, d2, d3, ...] 的列表
    d_k: C_k  C_{k-1} 的边界算子矩阵（行数=C_{k-1}维数，列数=C_k维数）

    验证：d_k  d_{k+1} = 0 对所有 k
    计算：H_k = ker(d_k) / im(d_{k+1})
    """
    n = len(boundary_ops)

    # 验证 ² = 0
    for i in range(n - 1):
        check = boundary_ops[i] @ boundary_ops[i + 1]
        if not np.all(check == 0):
            print(f"警告：_{i + 1}  _{i + 2}  0！")

    results = {}

    for k in range(n + 1):
        # H_k = ker(d_k) / im(d_{k+1})
        # d_k: C_k  C_{k-1}，k从1开始
        # d_0 不存在（或为零映射）

        if k < n:
            dk = boundary_ops[k]  # _{k+1}: C_{k+1}  C_k
        else:
            dk = None

        if k > 0:
            dk_prev = boundary_ops[k - 1]  # _k: C_k  C_{k-1}
        else:
            dk_prev = None

        # ker(_{k+1}): 在 C_{k+1} 中
        # 但 H_k 需要 ker(_k) 和 im(_{k+1})
        # _k: C_k  C_{k-1}

        # 重新理清：
        # boundary_ops[i] = _{i+1}: C_{i+1}  C_i
        # H_k = ker(_k: C_kC_{k-1}) / im(_{k+1}: C_{k+1}C_k)

        if k == 0:
            # H_0 = C_0 / im(_1)
            # _1 = boundary_ops[0]
            d_in = boundary_ops[0]  # _1: C_1  C_0
            d_out = None
        elif k < n:
            d_in = boundary_ops[k]  # _{k+1}: C_{k+1}  C_k（用于 ker）
            d_out = boundary_ops[k - 1]  # _k: C_k  C_{k-1}（用于 im）
            # H_k = ker(d_out 的转置？)
            # 注意方向：_k 的 ker 在 C_k 中
            # d_out = _k: C_k  C_{k-1}，ker 在列空间的零化子
            pass
        else:
            # H_n = ker(_n) / 0 = ker(_n)
            d_out = boundary_ops[k - 1]
            d_in = None

        # 使用 Smith 标准型计算
        # ker(_k: C_k  C_{k-1}) 的秩 = dim(C_k) - rank(_k)
        # im(_{k+1}: C_{k+1}  C_k) 的秩 = rank(_{k+1})

        if k == 0:
            # H_0
            d1_mat = boundary_ops[0]
            rank_d1 = smith_rank(d1_mat)
            dim_C0 = d1_mat.shape[0]
            # H_0 的自由秩 = dim(C_0) - rank(_1)
            free_rank = dim_C0 - rank_d1
            results[f'H_{k}'] = format_homology_group(free_rank, [])
        elif k <= n:
            d_boundary = boundary_ops[k - 1]  # _k: C_k  C_{k-1}
            dim_Ck = d_boundary.shape[1]
            rank_dk = smith_rank(d_boundary)
            ker_rank = dim_Ck - rank_dk

            if k < n:
                d_next = boundary_ops[k]  # _{k+1}: C_{k+1}  C_k
                rank_dk1 = smith_rank(d_next)
            else:
                rank_dk1 = 0

            free_rank = ker_rank - rank_dk1

            # 扭转项：用 Smith 标准型提取
            torsion = smith_torsion(d_boundary,
                                    boundary_ops[k] if k < n else None)
            results[f'H_{k}'] = format_homology_group(free_rank, torsion)

    return results


def smith_rank(mat):
    """整数矩阵的秩（用 Smith 标准型）"""
    if mat.size == 0:
        return 0
    # 复用已有的 Smith 标准型实现
    # 这里用 numpy 的秩作为近似（对整数矩阵足够）
    return int(np.linalg.matrix_rank(mat))


def smith_torsion(d_in, d_out):
    """提取扭转项（简化版，只检测 Z_2）"""
    return []  # 暂时返回空，专注自由秩


def format_homology_group(free_rank, torsion):
    if free_rank == 0 and not torsion:
        return '0'
    parts = []
    if free_rank == 1:
        parts.append('Z')
    elif free_rank > 1:
        parts.append(f'Z^{free_rank}')
    for t in torsion:
        parts.append(f'Z_{t}')
    return '  '.join(parts)


def run_clem_final(N=4):
    """
    CLEM 最终实验：完整四维链复形的正确同调计算
    """
    print(f"{'=' * 60}")
    print(f"【CLEM 最终实验】完整链复形同调，N={N}")
    print(f"{'=' * 60}")

    vertices = all_vertices(N)
    vertices_sorted = sorted(vertices)
    v_idx = {v: i for i, v in enumerate(vertices_sorted)}
    n0 = len(vertices_sorted)

    edges_A4 = apply_A4(vertices)
    directed_A4 = apply_A6_dag(list(edges_A4), vertices)
    a1p_edges = apply_A1_prime_edges(vertices, N)
    a1p_directed = apply_A6_dag(a1p_edges, vertices)
    all_directed = list(set(directed_A4 + a1p_directed))
    n1 = len(all_directed)
    e_idx = {e: i for i, e in enumerate(all_directed)}

    faces_A4 = list(apply_A7_faces(directed_A4, vertices))
    a1p_undi = set(frozenset(e) for e in a1p_directed)
    all_tris = apply_mixed_triangular_faces(all_directed, vertices)
    pure_a1p = [t for t in all_tris
                if all(frozenset([t[i], t[j]]) in a1p_undi
                       for i, j in [(0, 1), (1, 2), (0, 2)])]
    mixed = [t for t in all_tris if t not in set(pure_a1p)]
    all_faces = faces_A4 + pure_a1p + mixed
    n2 = len(all_faces)
    f_idx = {f: i for i, f in enumerate(all_faces)}

    tetrahedra = apply_3cells(all_directed, vertices)
    n3 = len(tetrahedra)

    print(f"C_0={n0}, C_1={n1}, C_2={n2}, C_3={n3}")
    chi = n0 - n1 + n2 - n3
    print(f"Euler 特征数：χ = {chi}")

    # _1
    d1 = np.zeros((n0, n1), dtype=int)
    for j, e in enumerate(all_directed):
        src, tgt = e
        d1[v_idx[tgt], j] += 1
        d1[v_idx[src], j] -= 1

    # _2
    d2 = np.zeros((n1, n2), dtype=int)
    for k, f in enumerate(all_faces):
        coeff = (face_vertices_to_boundary_v2(f, e_idx, lambda v: v)
                 if len(f) == 4 else triangle_boundary(f, e_idx))
        for ei, c in coeff.items():
            d2[ei, k] += c

    # _3
    d3 = np.zeros((n2, n3), dtype=int)
    for l, tet in enumerate(tetrahedra):
        coeff = tetrahedron_boundary(tet, e_idx, f_idx)
        for fi, c in coeff.items():
            d3[fi, l] += c

    print(f"_1_2=0: {np.all(d1 @ d2 == 0)}")
    print(f"_2_3=0: {np.all(d2 @ d3 == 0)}")

    # 正确计算各阶同调群
    def rank(mat):
        if mat.size == 0: return 0
        return int(np.linalg.matrix_rank(mat))

    r1 = rank(d1)
    r2 = rank(d2)
    r3 = rank(d3)

    h0_rank = n0 - r1
    h1_rank = (n1 - r1) - r2
    h2_rank = (n2 - r2) - r3
    h3_rank = n3 - r3

    print(f"秩：rank(_1)={r1}, rank(_2)={r2}, rank(_3)={r3}")
    print(f"同调群（自由秩）：")
    print(f"  H_0 = {'Z' if h0_rank == 1 else f'Z^{h0_rank}'}")
    print(f"  H_1 = {'0' if h1_rank == 0 else f'Z^{h1_rank}'}")
    print(f"  H_2 = {'0' if h2_rank == 0 else f'Z^{h2_rank}'}")
    print(f"  H_3 = {'0' if h3_rank == 0 else f'Z^{h3_rank}'}")

    chi_check = h0_rank - h1_rank + h2_rank - h3_rank
    print(f"Euler 验证：{chi_check} == {chi}: {chi_check == chi}")

    print(f"CLEM 判断：")
    if h0_rank == 1 and h1_rank == 0 and h2_rank == 0 and h3_rank == 0:
        print(f"  *** H*(X)  H*(R³) — CLEM 核心命题验证通过 ***")
        print(f"  D=3 是公理体系的拓扑必然结果。")
    elif h0_rank == 1 and h1_rank == 0 and h2_rank == 0 and h3_rank == 1:
        print(f"  H*(X)  H*(S³)（三维球面）")
        print(f"  有限 N 的紧致化效应，N 趋向 H*(R³)。")
    elif h0_rank == 1 and h1_rank == 0:
        print(f"  单连通，H_2={h2_rank}, H_3={h3_rank}")
        print(f"  需要更多高维胞腔，或检查 N 是否足够大。")
    else:
        print(f"  H_0={h0_rank}, H_1={h1_rank}, "
              f"H_2={h2_rank}, H_3={h3_rank}")


def run_johnson_graph_homology(N_list=[4, 6, 8]):
    """
    计算不同 N 下，中截面 Johnson 图 J(N,N/2) 的同调群。

    只用顶点和边（不加面），看 H_0 和 H_1 的变化。
    然后加入 A1' 三角面，看 H_2 的变化。

    目标：找到 J(N,N/2) 同调群随 N 的变化规律。
    """
    import numpy as np

    for N in N_list:
        if N % 2 != 0:
            continue

        print(f"\n{'=' * 50}")
        print(f"N={N}, 中截面 J({N},{N // 2})")
        print(f"{'=' * 50}")

        vertices = all_vertices(N)

        # 中截面顶点
        mid_verts = [v for v in vertices if sum(v) == N // 2]
        mid_verts_sorted = sorted(mid_verts)
        v_idx = {v: i for i, v in enumerate(mid_verts_sorted)}
        n0 = len(mid_verts_sorted)

        # A1' 边（d_H=2，同层）
        a1p_edges = []
        for i in range(n0):
            for j in range(i + 1, n0):
                vi, vj = mid_verts_sorted[i], mid_verts_sorted[j]
                if sum(a != b for a, b in zip(vi, vj)) == 2:
                    a1p_edges.append(frozenset([vi, vj]))
        a1p_directed = apply_A6_dag(a1p_edges, mid_verts_sorted)
        n1 = len(a1p_directed)
        e_idx = {e: i for i, e in enumerate(a1p_directed)}

        print(f"顶点数：{n0}，边数：{n1}")
        print(f"理论边数：{n0 * (N // 2) ** 2 // 2}")

        # ∂_1（只有边，无面）
        d1 = np.zeros((n0, n1), dtype=int)
        for j, e in enumerate(a1p_directed):
            src, tgt = e
            d1[v_idx[tgt], j] += 1
            d1[v_idx[src], j] -= 1

        # 无面时的同调
        d2_empty = np.zeros((n1, 0), dtype=int)
        h_no_face = compute_homology(d1, d2_empty)
        print(f"无面同调：{h_no_face}")

        # 加入三角面
        all_tris = apply_triangular_faces(a1p_directed, mid_verts_sorted)
        n2 = len(all_tris)
        print(f"三角面数：{n2}")

        d2 = np.zeros((n1, n2), dtype=int)
        for k, tri in enumerate(all_tris):
            coeff = triangle_boundary(tri, e_idx)
            for ei, c in coeff.items():
                d2[ei, k] += c

        ok = np.all(d1 @ d2 == 0)
        print(f"∂²=0: {ok}")

        h = compute_homology(d1, d2)
        chi = n0 - n1 + n2
        print(f"加入三角面后：C_0={n0},C_1={n1},C_2={n2},χ={chi}")
        print(f"同调群：{h}")

        # Euler 特征数的理论值
        # J(N,N/2) 的 χ 没有简单公式，但可以从同调群读出
        r = int(np.linalg.matrix_rank(d1))
        h1_rank = n1 - r - int(np.linalg.matrix_rank(d2))
        print(f"H_1 自由秩（秩公式）：{h1_rank}")


def find_long_cycles(directed_edges, vertices, min_length):
    """
    找出所有长度 >= min_length 的有向循环，
    返回参与这些循环的顶点集合和边集合。

    用 DFS 找有向图中的所有简单环。
    对大图（N=6，20顶点）可能很慢，需要剪枝。
    """
    from collections import defaultdict

    adj = defaultdict(list)
    for src, tgt in directed_edges:
        adj[src].append(tgt)

    participating_vertices = set()
    participating_edges = set()

    def dfs(start, current, path, path_set):
        for nxt in adj[current]:
            if nxt == start and len(path) >= min_length:
                # 找到一个有效循环
                for v in path:
                    participating_vertices.add(v)
                for i in range(len(path)):
                    participating_edges.add(
                        (path[i], path[(i + 1) % len(path)]))
                return
            if nxt not in path_set and len(path) < min_length * 2:
                path.append(nxt)
                path_set.add(nxt)
                dfs(start, nxt, path, path_set)
                path.pop()
                path_set.remove(nxt)

    for v in vertices:
        dfs(v, v, [v], {v})

    return participating_vertices, participating_edges


def run_A7_filtered_homology(N=6):
    """
    在中截面上，用 A7 筛选后的顶点和边计算同调群。
    """
    print(f"{'=' * 50}")
    print(f"【A7 筛选实验】N={N}，循环长度 >= {N}")
    print(f"{'=' * 50}")

    vertices = all_vertices(N)
    mid_verts = sorted([v for v in vertices if sum(v) == N // 2])

    # A1' 边
    a1p_edges = [frozenset([mid_verts[i], mid_verts[j]])
                 for i in range(len(mid_verts))
                 for j in range(i + 1, len(mid_verts))
                 if sum(a != b for a, b in zip(mid_verts[i], mid_verts[j])) == 2]
    a1p_directed = apply_A6_dag(a1p_edges, mid_verts)

    print(f"原始：{len(mid_verts)} 顶点，{len(a1p_directed)} 边")

    # A7 筛选
    part_v, part_e = find_long_cycles(a1p_directed, mid_verts, N)
    print(f"A7 筛选后：{len(part_v)} 顶点，{len(part_e)} 边")

    if not part_v:
        print("无满足 A7 的循环。")
        return

    part_v_sorted = sorted(part_v)
    part_e_list = [(s, t) for s, t in part_e
                   if s in part_v and t in part_v]

    v_idx = {v: i for i, v in enumerate(part_v_sorted)}
    e_idx = {e: i for i, e in enumerate(part_e_list)}
    n0, n1 = len(part_v_sorted), len(part_e_list)

    # 三角面（只在筛选后的顶点和边上）
    tris = apply_triangular_faces(part_e_list, part_v_sorted)
    n2 = len(tris)
    print(f"三角面：{n2}")

    chi = n0 - n1 + n2
    print(f"C_0={n0}, C_1={n1}, C_2={n2}, χ={chi}")

    d1 = np.zeros((n0, n1), dtype=int)
    for j, (src, tgt) in enumerate(part_e_list):
        d1[v_idx[tgt], j] += 1
        d1[v_idx[src], j] -= 1

    d2 = np.zeros((n1, n2), dtype=int)
    for k, tri in enumerate(tris):
        coeff = triangle_boundary(tri, e_idx)
        for ei, c in coeff.items():
            d2[ei, k] += c

    ok = np.all(d1 @ d2 == 0)
    print(f"∂²=0: {ok}")

    h = compute_homology(d1, d2)
    print(f"同调群：{h}")

    if h['H_0'] == 'Z' and h['H_1'] == '0' and h['H_2'] == 'Z':
        print(f"*** A7 筛选后 H*(X) ≅ H*(S²) ***")
        print(f"A7 是产生 S² 结构的关键约束。")
    elif h['H_1'] == '0':
        print(f"H_1=0，单连通，但 H_2={h['H_2']}")
    else:
        print(f"H_1={h['H_1']}，仍有非平凡 1-圈。")


def find_sphere_triangulation(directed_edges, vertices):
    """
    在图的三角面中，找一个满足流形条件的子集：
    每条无向边恰好属于 2 个三角面。

    这等价于找图的一个球面三角剖分（如果存在）。

    策略：
    1. 找出所有三角面
    2. 用贪心算法选取三角面子集，
       使得每条边最多被 2 个面使用
    3. 检验结果的同调群
    """
    all_tris = apply_triangular_faces(directed_edges, sorted(vertices))

    # 统计每条无向边被多少个三角面包含
    from collections import defaultdict
    edge_to_tris = defaultdict(list)
    for k, tri in enumerate(all_tris):
        v0, v1, v2 = tri
        for ei, ej in [(v0, v1), (v1, v2), (v0, v2)]:
            edge_to_tris[frozenset([ei, ej])].append(k)

    # 贪心选取：每条边最多被 2 个面选中
    selected = set()
    edge_count = defaultdict(int)

    # 按"边的竞争度"排序：竞争越少的三角面优先选
    def face_score(k):
        tri = all_tris[k]
        v0, v1, v2 = tri
        total = 0
        for ei, ej in [(v0, v1), (v1, v2), (v0, v2)]:
            total += len(edge_to_tris[frozenset([ei, ej])])
        return total

    sorted_tris = sorted(range(len(all_tris)), key=face_score)

    for k in sorted_tris:
        tri = all_tris[k]
        v0, v1, v2 = tri
        # 检查这个面的三条边是否都还有空位
        ok = True
        for ei, ej in [(v0, v1), (v1, v2), (v0, v2)]:
            if edge_count[frozenset([ei, ej])] >= 2:
                ok = False
                break
        if ok:
            selected.add(k)
            for ei, ej in [(v0, v1), (v1, v2), (v0, v2)]:
                edge_count[frozenset([ei, ej])] += 1

    selected_tris = [all_tris[k] for k in sorted(selected)]

    # 检验流形条件
    edge_counts = list(edge_count.values())
    from collections import Counter
    count_dist = Counter(edge_counts)

    return selected_tris, count_dist


def run_sphere_triangulation(N=6):
    print(f"{'=' * 50}")
    print(f"【球面三角剖分实验】N={N}")
    print(f"{'=' * 50}")

    vertices = all_vertices(N)
    mid_verts = sorted([v for v in vertices if sum(v) == N // 2])
    v_idx = {v: i for i, v in enumerate(mid_verts)}
    n0 = len(mid_verts)

    a1p_edges = [frozenset([mid_verts[i], mid_verts[j]])
                 for i in range(n0)
                 for j in range(i + 1, n0)
                 if sum(a != b for a, b in zip(mid_verts[i], mid_verts[j])) == 2]
    a1p_directed = apply_A6_dag(a1p_edges, mid_verts)
    e_idx = {e: i for i, e in enumerate(a1p_directed)}
    n1 = len(a1p_directed)

    # 球面三角剖分
    sel_tris, count_dist = find_sphere_triangulation(
        a1p_directed, mid_verts)
    n2 = len(sel_tris)

    print(f"顶点：{n0}，边：{n1}，选取三角面：{n2}")
    print(f"边的面数分布：{dict(count_dist)}")
    print(f"（理想：全部为 2）")

    chi = n0 - n1 + n2
    print(f"χ = {chi}")

    d1 = np.zeros((n0, n1), dtype=int)
    for j, (src, tgt) in enumerate(a1p_directed):
        d1[v_idx[tgt], j] += 1
        d1[v_idx[src], j] -= 1

    d2 = np.zeros((n1, n2), dtype=int)
    for k, tri in enumerate(sel_tris):
        coeff = triangle_boundary(tri, e_idx)
        for ei, c in coeff.items():
            d2[ei, k] += c

    ok = np.all(d1 @ d2 == 0)
    print(f"∂²=0: {ok}")

    h = compute_homology(d1, d2)
    print(f"同调群：{h}")

    if h['H_0'] == 'Z' and h['H_1'] == '0' and h['H_2'] == 'Z':
        print(f"*** H*(X) ≅ H*(S²) — 球面三角剖分成功 ***")
        print(f"流形条件（每边恰好 2 个面）产生 S²。")
        print(f"这说明 A1' 的几何含义（球面对称性）")
        print(f"在 N={N} 下仍然成立，但需要流形约束来实现。")
    else:
        print(f"H={h}，需进一步调整选取策略。")


def find_global_cycles_undirected(vertices, N, min_length):
    """
    在无向超立方体图上，找长度 >= min_length 的简单环。

    A6 的 DAG 定向是局部的（单步有向），但 A7 的循环是全局的。
    在全局尺度上，循环通过 A1' 的横向跃迁来"回头"，
    不受 A6 单步方向的约束。

    策略：
    - 用 A4 边（无向）构造图
    - 找所有经过中截面顶点的长度 >= min_length 的简单环
    - 返回参与这些环的中截面顶点和边
    """
    from collections import defaultdict

    # 无向 A4 边
    adj = defaultdict(set)
    for v in vertices:
        for i in range(N):
            u = list(v)
            u[i] = 1 - u[i]
            u = tuple(u)
            adj[v].add(u)

    mid_verts = set(v for v in vertices if sum(v) == N // 2)
    participating = set()

    # 从每个中截面顶点出发，DFS 找长环
    # 限制搜索深度为 min_length * 1.5 防止爆炸
    max_depth = min(min_length + 4, 2 * N)

    def dfs(start, current, depth, visited):
        if depth >= min_length:
            if start in adj[current]:
                participating.add(start)
                return True
        if depth >= max_depth:
            return False
        found = False
        for nxt in adj[current]:
            if nxt not in visited:
                visited.add(nxt)
                if dfs(start, nxt, depth + 1, visited):
                    participating.add(current)
                    found = True
                visited.remove(nxt)
        return found

    for v in sorted(mid_verts)[:10]:  # 先测前10个，避免超时
        dfs(v, v, 0, {v})

    return participating


def run_A7_global_experiment(N=6):
    """
    A7-global 实验：用无向全局循环筛选中截面顶点，
    然后在筛选后的子图上计算同调群。
    """
    print(f"{'=' * 50}")
    print(f"【A7-global 实验】N={N}，无向循环长度 >= {N}")
    print(f"{'=' * 50}")

    vertices = all_vertices(N)
    mid_verts = sorted([v for v in vertices if sum(v) == N // 2])

    # 找参与全局循环的中截面顶点
    part_v = find_global_cycles_undirected(vertices, N, N)
    print(f"参与全局循环的中截面顶点：{len(part_v)}/{len(mid_verts)}")

    if not part_v:
        print("无参与全局循环的中截面顶点。")
        return

    # 在参与顶点上构造 A1' 子图
    part_v_sorted = sorted(part_v)
    v_idx = {v: i for i, v in enumerate(part_v_sorted)}
    n0 = len(part_v_sorted)

    a1p_edges = [frozenset([part_v_sorted[i], part_v_sorted[j]])
                 for i in range(n0)
                 for j in range(i + 1, n0)
                 if sum(a != b for a, b in zip(
            part_v_sorted[i], part_v_sorted[j])) == 2]
    a1p_directed = apply_A6_dag(a1p_edges, part_v_sorted)
    e_idx = {e: i for i, e in enumerate(a1p_directed)}
    n1 = len(a1p_directed)

    # 三角面
    tris = apply_triangular_faces(a1p_directed, part_v_sorted)
    n2 = len(tris)

    chi = n0 - n1 + n2
    print(f"C_0={n0}, C_1={n1}, C_2={n2}, χ={chi}")

    if n1 == 0:
        print("无边，无法计算同调。")
        return

    d1 = np.zeros((n0, n1), dtype=int)
    for j, (src, tgt) in enumerate(a1p_directed):
        d1[v_idx[tgt], j] += 1
        d1[v_idx[src], j] -= 1

    d2 = np.zeros((n1, n2), dtype=int)
    for k, tri in enumerate(tris):
        coeff = triangle_boundary(tri, e_idx)
        for ei, c in coeff.items():
            d2[ei, k] += c

    ok = np.all(d1 @ d2 == 0)
    print(f"∂²=0: {ok}")

    h = compute_homology(d1, d2)
    print(f"同调群：{h}")

    if h['H_0'] == 'Z' and h['H_1'] == '0' and h['H_2'] == 'Z':
        print(f"*** H*(X) ≅ H*(S²) ***")
        print(f"A7-global 筛选恢复了 S² 结构！")
        print(f"A7 是 CLEM 中 S² 涌现的关键约束。")
    elif h.get('H_1', '') == '0':
        print(f"H_1=0（单连通），H_2={h.get('H_2', '?')}")
    else:
        print(f"结果：{h}")
        print(f"提示：max_depth 可能不够，或需要完整搜索所有顶点。")


def find_global_cycles_undirected_v2(vertices, N, min_length):
    """
    修复版：只收集中截面顶点中，
    确实参与长度 >= min_length 的简单环的那些顶点。

    关键修复：
    1. DFS 找到有效循环后，只把循环路径上的
       【中截面顶点】加入 participating
    2. 不把路径上的非中截面顶点加入
    3. 对所有中截面顶点（不只是前10个）做搜索
    """
    from collections import defaultdict

    # 无向 A4 边
    adj = defaultdict(set)
    for v in vertices:
        for i in range(N):
            u = list(v)
            u[i] = 1 - u[i]
            u = tuple(u)
            adj[v].add(u)

    mid_verts = set(v for v in vertices if sum(v) == N // 2)
    participating = set()
    max_depth = min(min_length + 4, 2 * N)

    def dfs(start, current, path, visited):
        """
        返回 True 表示找到了从 start 出发的有效循环。
        path 是当前路径（包含 start）。
        """
        if len(path) >= min_length:
            if start in adj[current]:
                # 找到有效循环，只收集路径上的中截面顶点
                for v in path:
                    if v in mid_verts:
                        participating.add(v)
                return True
        if len(path) >= max_depth:
            return False

        found = False
        for nxt in sorted(adj[current]):  # 排序保证确定性
            if nxt not in visited:
                visited.add(nxt)
                path.append(nxt)
                if dfs(start, nxt, path, visited):
                    found = True
                    # 不提前退出，继续找更多循环
                path.pop()
                visited.remove(nxt)
        return found

    # 对所有中截面顶点做搜索
    for v in sorted(mid_verts):
        dfs(v, v, [v], {v})

    return participating


def run_A7_global_v2(N=6):
    """
    A7-global 实验修复版
    """
    print(f"{'=' * 50}")
    print(f"【A7-global 修复版】N={N}，循环长度 >= {N}")
    print(f"{'=' * 50}")

    vertices = all_vertices(N)
    mid_verts_all = sorted([v for v in vertices if sum(v) == N // 2])
    print(f"中截面总顶点数：{len(mid_verts_all)}")

    # A7-global 筛选
    part_v = find_global_cycles_undirected_v2(vertices, N, N)
    print(f"参与全局循环的中截面顶点：{len(part_v)}/{len(mid_verts_all)}")

    if not part_v:
        print("无参与全局循环的中截面顶点。")
        return

    # 打印参与和未参与的顶点
    not_part = set(mid_verts_all) - part_v
    print(f"未参与的顶点数：{len(not_part)}")
    if not_part:
        print(f"未参与顶点（前5个）：{sorted(not_part)[:5]}")

    part_v_sorted = sorted(part_v)
    v_idx = {v: i for i, v in enumerate(part_v_sorted)}
    n0 = len(part_v_sorted)

    # A1' 边（只在参与顶点之间）
    a1p_edges = [frozenset([part_v_sorted[i], part_v_sorted[j]])
                 for i in range(n0)
                 for j in range(i + 1, n0)
                 if sum(a != b for a, b in zip(
            part_v_sorted[i], part_v_sorted[j])) == 2]
    a1p_directed = apply_A6_dag(a1p_edges, part_v_sorted)
    e_idx = {e: i for i, e in enumerate(a1p_directed)}
    n1 = len(a1p_directed)

    # 三角面
    tris = apply_triangular_faces(a1p_directed, part_v_sorted)
    n2 = len(tris)

    chi = n0 - n1 + n2
    print(f"C_0={n0}, C_1={n1}, C_2={n2}, χ={chi}")

    if n1 == 0:
        print("无边，无法计算同调。")
        return

    d1 = np.zeros((n0, n1), dtype=int)
    for j, (src, tgt) in enumerate(a1p_directed):
        d1[v_idx[tgt], j] += 1
        d1[v_idx[src], j] -= 1

    d2 = np.zeros((n1, n2), dtype=int)
    for k, tri in enumerate(tris):
        coeff = triangle_boundary(tri, e_idx)
        for ei, c in coeff.items():
            d2[ei, k] += c

    ok = np.all(d1 @ d2 == 0)
    print(f"∂²=0: {ok}")

    h = compute_homology(d1, d2)
    print(f"同调群：{h}")

    # 判断
    h0, h1, h2 = h['H_0'], h['H_1'], h['H_2']
    print(f"CLEM 判断：")
    if h0 == 'Z' and h1 == '0' and h2 == 'Z':
        print(f"  *** H*(X) ≅ H*(S²) ***")
        print(f"  A7-global 筛选恢复了 S² 结构。")
        print(f"  A7 是 S² 涌现的关键约束——")
        print(f"  只有参与全局循环的顶点才构成物理空间。")
    elif h0 == 'Z' and h1 == '0':
        print(f"  单连通，H_2={h2}。")
        print(f"  三角面仍然过多，需要进一步筛选。")
        print(f"  下一步：在参与顶点上做球面三角剖分。")
    elif len(part_v) == len(mid_verts_all):
        print(f"  所有中截面顶点都参与全局循环——")
        print(f"  A7-global 筛选无效（超立方体高度对称）。")
        print(f"  需要更强的筛选条件：")
        print(f"  最短循环长度 = N，或相位约束（复系数同调）。")
    else:
        print(f"  H_0={h0}, H_1={h1}, H_2={h2}")

    return h


def build_axiom_space_sequential(N):
    """
    按公理顺序逐步构造允许的状态空间。

    A1：只保留 w 单调不减的有向边（层间向上）
    A1'：添加同层横向边（d_H=2，w相同）
    A4：每步 d_H=1（已在 A1 中隐含）
    A6：DAG（已在 A1 中隐含）
    A7：在已有有向图上，只保留参与长度>=N循环的顶点
    A8：Morse 权重（偏好中截面）
    """
    vertices = all_vertices(N)

    # A1 + A4 + A6：层间有向边，w 严格递增
    edges_A1 = []
    for v in vertices:
        for i in range(N):
            if v[i] == 0:  # 只允许 0→1，即 w 增加
                u = list(v)
                u[i] = 1
                u = tuple(u)
                edges_A1.append((v, u))

    print(f"A1+A4+A6 有向边：{len(edges_A1)}")

    # A1'：同层横向边（d_H=2，w相同）
    edges_A1p = []
    for i, v in enumerate(vertices):
        for j, u in enumerate(vertices):
            if i < j and sum(v) == sum(u):
                if sum(a != b for a, b in zip(v, u)) == 2:
                    # A1' 边无方向偏好，用 A6 定向
                    edges_A1p.append(frozenset([v, u]))
    edges_A1p_directed = apply_A6_dag(edges_A1p, vertices)
    print(f"A1' 有向边：{len(edges_A1p_directed)}")

    # 合并 A1 和 A1' 边
    all_directed = list(set(edges_A1 + edges_A1p_directed))

    # A7：在合并图上，找参与长度>=N循环的顶点
    # 注意：A1 边是单向的（只能向上），A1' 边可以横向
    # 循环必须通过 A1' 横向边来"绕回"
    from collections import defaultdict
    adj = defaultdict(list)
    for src, tgt in all_directed:
        adj[src].append(tgt)

    participating = set()
    max_depth = N * 3  # 允许更长的搜索

    def dfs_directed(start, current, depth, visited):
        if depth >= N:
            if start in adj[current]:
                return True
        if depth >= max_depth:
            return False
        for nxt in adj[current]:
            if nxt not in visited or (nxt == start and depth >= N):
                if nxt == start and depth >= N:
                    return True
                if nxt not in visited:
                    visited.add(nxt)
                    if dfs_directed(start, nxt, depth + 1, visited):
                        visited.remove(nxt)
                        return True
                    visited.remove(nxt)
        return False

    mid_verts = [v for v in vertices if sum(v) == N // 2]
    for v in sorted(mid_verts):
        if dfs_directed(v, v, 0, {v}):
            participating.add(v)

    print(f"A7 筛选后中截面顶点：{len(participating)}/{len(mid_verts)}")

    return all_directed, participating, mid_verts


def build_sequential_with_quotient(N):
    """
    按公理顺序逐步构造，正确处理 A6 vs A7 张力。

    关键修正：
    A7 的循环在商空间中实现。
    A1' 定义等价关系：同层内通过横向对称性相关的顶点等价。
    在商空间中，A1' 横向跃迁变成"自环"（从等价类到自身），
    这允许 A7 的循环条件被满足。

    具体实现：
    1. A1+A4+A6 建立层间有向边（同之前）
    2. A1' 定义同层等价关系（把 d_H=2 的同层顶点对识别）
    3. 在商空间中，A7 循环 = 从某个等价类出发，
       经过层间跃迁，回到同一等价类
    4. A8 Morse 简化选出中截面等价类
    """
    vertices = all_vertices(N)
    mid_verts = sorted([v for v in vertices if sum(v) == N // 2])

    # A1 层间有向边（w 严格递增）
    edges_up = []
    for v in vertices:
        for i in range(N):
            if v[i] == 0:
                u = list(v);
                u[i] = 1;
                u = tuple(u)
                edges_up.append((v, u))

    # A1' 等价关系：同层内 d_H=2 的顶点对
    # 用 Union-Find 构造等价类
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

    # 只合并同层的 d_H=2 顶点对（A1' 横向等价）
    for i, v in enumerate(vertices):
        for j, u in enumerate(vertices):
            if i < j and sum(v) == sum(u):
                if sum(a != b for a, b in zip(v, u)) == 2:
                    union(v, u)

    # 商空间等价类
    classes = {}
    for v in vertices:
        rep = find(v)
        if rep not in classes:
            classes[rep] = []
        classes[rep].append(v)

    print(f"商空间等价类数：{len(classes)}")
    print(f"各层等价类分布：")
    from collections import Counter
    layer_classes = Counter()
    for rep, members in classes.items():
        w = sum(members[0])
        layer_classes[w] += 1
    for w in sorted(layer_classes):
        print(f"  w={w}: {layer_classes[w]} 个等价类")

    # 在商空间上构造有向边
    def get_rep(v):
        return find(v)

    # 层间边（A1）在商空间上的像
    quotient_edges = set()
    for src, tgt in edges_up:
        r_src = get_rep(src)
        r_tgt = get_rep(tgt)
        if r_src != r_tgt:
            quotient_edges.add((r_src, r_tgt))
        else:
            # src 和 tgt 在同一等价类——这是 A7 循环的来源！
            # 层间跃迁落在同一等价类 = 循环闭合
            pass

    # 检查：有多少层间边在商空间中变成"自环"（循环）
    self_loops = [(src, tgt) for src, tgt in edges_up
                  if get_rep(src) == get_rep(tgt)]
    print(f"    商空间中的自环（A7    循环候选）：{len(self_loops)}    ")
    if self_loops:
        print(f"  示例：{self_loops[:3]}")
    # 这些自环对应的等价类就是 A7 允许的稳定态
    stable_classes = set(get_rep(src) for src, tgt in self_loops)
    print(f"  对应的等价类数：{len(stable_classes)}")
    # 其中有多少是中截面等价类？
    mid_stable = [c for c in stable_classes
                  if sum(list(classes[c])[0]) == N // 2]
    print(f"  中截面稳定等价类：{len(mid_stable)}")

    # A8 Morse 简化：中截面等价类
    mid_classes = [rep for rep, members in classes.items()
                   if sum(members[0]) == N // 2]
    print(f"    中截面等价类总数：{len(mid_classes)}    ")

    return classes, quotient_edges, self_loops


def build_directed_A1prime(N):
    """
    给 A1' 边赋予方向：
    v → u 当且仅当存在 i < j 使得 v[i]=1, v[j]=0, u[i]=0, u[j]=1
    （把高位的1换到低位——这是一个具体的规范选择，可以讨论）

    然后枚举有向三角形（A7 循环的最小实现），
    用有向三角形作为面，计算同调群。
    """
    from itertools import combinations, product

    verts = [v for v in product([0, 1], repeat=N) if sum(v) == N // 2]
    idx = {v: i for i, v in enumerate(verts)}
    n = len(verts)

    # 有向 A1' 边
    directed_edges = set()
    for v in verts:
        for i in range(N):
            for j in range(N):
                if i != j and v[i] == 1 and v[j] == 0:
                    u = list(v)
                    u[i] = 0;
                    u[j] = 1
                    u = tuple(u)
                    # 规范方向：i < j 时 v→u，i > j 时 u→v
                    if i < j:
                        directed_edges.add((idx[v], idx[u]))

    # 枚举有向三角形
    triangles = []
    for a, b, c in combinations(range(n), 3):
        # 检查六种有向三角形，找循环方向
        if (a, b) in directed_edges and (b, c) in directed_edges and (c, a) in directed_edges:
            triangles.append((a, b, c))
        elif (a, c) in directed_edges and (c, b) in directed_edges and (b, a) in directed_edges:
            triangles.append((a, c, b))

    print(f"N={N}: {n} 顶点, {len(directed_edges)} 有向边, {len(triangles)} 有向三角形")
    return verts, directed_edges, triangles


def build_circular_directed_A1prime(N):
    """
    把 N 个坐标位置排成一个圆（0,1,...,N-1,0,...）
    σ_ij 的方向：在圆上从 i 到 j 是顺时针则 v→u，逆时针则 u→v
    顺时针定义：(j - i) mod N <= N//2
    """
    from itertools import combinations, product

    verts = [v for v in product([0, 1], repeat=N) if sum(v) == N // 2]
    idx = {v: i for i, v in enumerate(verts)}
    n = len(verts)

    directed_edges = set()
    for v in verts:
        for i in range(N):
            for j in range(N):
                if i != j and v[i] == 1 and v[j] == 0:
                    u = list(v)
                    u[i] = 0;
                    u[j] = 1
                    u = tuple(u)
                    # 循环方向：(j-i) mod N <= N//2 为顺时针（正向）
                    if (j - i) % N <= N // 2:
                        directed_edges.add((idx[v], idx[u]))
                    # 反向由对称性自动处理（不重复添加）

    # 枚举有向三角形
    triangles = []
    for a, b, c in combinations(range(n), 3):
        if ((a, b) in directed_edges and (b, c) in directed_edges
                and (c, a) in directed_edges):
            triangles.append((a, b, c))
        elif ((a, c) in directed_edges and (c, b) in directed_edges
              and (b, a) in directed_edges):
            triangles.append((a, c, b))

    print(f"N={N}: {n} 顶点, {len(directed_edges)} 有向边, {len(triangles)} 有向三角形")

    # 验证：有向三角形是否覆盖所有顶点
    covered = set()
    for t in triangles:
        covered.update(t)
    print(f"  被三角形覆盖的顶点数：{len(covered)}/{n}")

    return verts, directed_edges, triangles


def compute_homology_from_directed(N, verts, directed_edges, triangles):
    import numpy as np

    def rank_m(M):
        if M.size == 0: return 0
        s = np.linalg.svd(M.astype(float), compute_uv=False)
        return int(np.sum(s > 1e-6))

    n = len(verts)

    # 无向边
    undirected_edges = set()
    for (a, b) in directed_edges:
        undirected_edges.add((min(a, b), max(a, b)))
    edges_list = sorted(undirected_edges)
    edge_idx = {e: i for i, e in enumerate(edges_list)}

    # 无向三角面
    faces_set = set()
    for (a, b, c) in triangles:
        faces_set.add(tuple(sorted([a, b, c])))
    faces_list = sorted(faces_set)

    V = n
    E = len(edges_list)
    F = len(faces_list)
    chi = V - E + F
    print(f"\nN={N}: V={V}, E={E}, F={F}, χ={chi}")

    # ∂1: E → V
    d1 = np.zeros((V, E), dtype=int)
    for j, (a, b) in enumerate(edges_list):
        d1[a][j] = -1
        d1[b][j] = 1

    # ∂2: F → E，标准单纯同调符号
    d2 = np.zeros((E, F), dtype=int)
    for k, (a, b, c) in enumerate(faces_list):
        # a < b < c 已保证（sorted）
        # ∂[a,b,c] = [b,c] - [a,c] + [a,b]
        e_ab = edge_idx[(a, b)]
        e_bc = edge_idx[(b, c)]
        e_ac = edge_idx[(a, c)]
        d2[e_ab][k] = 1
        d2[e_bc][k] = 1
        d2[e_ac][k] = -1

    # 验证链复形条件
    check = d1 @ d2
    print(f"  ∂1∂2 = 0: {np.all(check == 0)}")
    if not np.all(check == 0):
        print(f"  ∂1∂2 非零项数: {np.count_nonzero(check)}")

    r1 = rank_m(d1)
    r2 = rank_m(d2)

    b0 = V - r1
    b1 = E - r1 - r2
    b2 = F - r2

    print(f"  β0={b0}, β1={b1}, β2={b2}")
    print(f"  χ check: {b0 - b1 + b2} (should be {chi})")

    if b0 == 1 and b1 == 0 and b2 == 1:
        print(f"  → H_*(S²) ✓")
    else:
        print(f"  → 非 S²")

    return b0, b1, b2


def analyze_edge_degrees(N, verts, directed_edges, triangles):
    # 无向边和无向面（复用之前的逻辑）
    undirected_edges = set()
    for (a, b) in directed_edges:
        undirected_edges.add((min(a, b), max(a, b)))
    edges_list = sorted(undirected_edges)
    edge_idx = {e: i for i, e in enumerate(edges_list)}

    faces_set = set()
    for (a, b, c) in triangles:
        faces_set.add(tuple(sorted([a, b, c])))
    faces_list = sorted(faces_set)

    # 每条边被多少个面共享
    edge_face_count = {e: 0 for e in edges_list}
    for (a, b, c) in faces_list:
        for (u, v) in [(a, b), (b, c), (a, c)]:
            edge_face_count[(min(u, v), max(u, v))] += 1

    from collections import Counter
    degree_dist = Counter(edge_face_count.values())
    print(f"N={N} 边-面度数分布：")
    for deg, cnt in sorted(degree_dist.items()):
        print(f"  度数={deg} 的边：{cnt} 条")

    # 每个顶点被多少个面共享
    vert_face_count = [0] * len(verts)
    for (a, b, c) in faces_list:
        vert_face_count[a] += 1
        vert_face_count[b] += 1
        vert_face_count[c] += 1
    vc_dist = Counter(vert_face_count)
    print(f"N={N} 顶点-面度数分布：")
    for deg, cnt in sorted(vc_dist.items()):
        print(f"  度数={deg} 的顶点：{cnt} 个")

    # 边度数=1 的边（边界边）
    boundary_edges = [e for e, c in edge_face_count.items() if c == 1]
    print(f"  边界边数量（度数=1）：{len(boundary_edges)}")
    # 边度数>2 的边（非流形边）
    nonmanifold_edges = [e for e, c in edge_face_count.items() if c > 2]
    print(f"  非流形边数量（度数>2）：{len(nonmanifold_edges)}")


def extract_manifold_subcomplex(N, verts, directed_edges, triangles):
    import numpy as np

    def rank_m(M):
        if M.size == 0: return 0
        s = np.linalg.svd(M.astype(float), compute_uv=False)
        return int(np.sum(s > 1e-6))

    # 无向边和无向面
    undirected_edges = set()
    for (a, b) in directed_edges:
        undirected_edges.add((min(a, b), max(a, b)))
    edges_list = sorted(undirected_edges)

    faces_set = set()
    for (a, b, c) in triangles:
        faces_set.add(tuple(sorted([a, b, c])))
    faces_list = sorted(faces_set)

    # 计算每条边的面度数
    edge_face_count = {e: 0 for e in edges_list}
    for (a, b, c) in faces_list:
        for (u, v) in [(a, b), (b, c), (a, c)]:
            edge_face_count[(min(u, v), max(u, v))] += 1

    # 流形边：度数恰好=2
    manifold_edges = {e for e, c in edge_face_count.items() if c == 2}

    # 流形面：三条边全部是流形边
    manifold_faces = []
    for (a, b, c) in faces_list:
        edges_of_face = {
            (min(a, b), max(a, b)),
            (min(b, c), max(b, c)),
            (min(a, c), max(a, c))
        }
        if edges_of_face.issubset(manifold_edges):
            manifold_faces.append((a, b, c))

    # 流形顶点：出现在流形面中的顶点
    manifold_verts = sorted(set(v for f in manifold_faces for v in f))
    vert_remap = {v: i for i, v in enumerate(manifold_verts)}

    manifold_edges_list = sorted(manifold_edges)
    edge_idx = {e: i for i, e in enumerate(manifold_edges_list)}

    V = len(manifold_verts)
    E = len(manifold_edges_list)
    F = len(manifold_faces)
    chi = V - E + F
    print(f"\nN={N} 流形子复形: V={V}, E={E}, F={F}, χ={chi}")

    if V == 0 or E == 0 or F == 0:
        print("  流形子复形为空")
        return

    # ∂1
    d1 = np.zeros((V, E), dtype=int)
    for j, (a, b) in enumerate(manifold_edges_list):
        d1[vert_remap[a]][j] = -1
        d1[vert_remap[b]][j] = 1

    # ∂2
    d2 = np.zeros((E, F), dtype=int)
    for k, (a, b, c) in enumerate(manifold_faces):
        e_ab = edge_idx[(min(a, b), max(a, b))]
        e_bc = edge_idx[(min(b, c), max(b, c))]
        e_ac = edge_idx[(min(a, c), max(a, c))]
        d2[e_ab][k] = 1
        d2[e_bc][k] = 1
        d2[e_ac][k] = -1

    check = d1 @ d2
    print(f"  ∂1∂2 = 0: {np.all(check == 0)}")

    r1 = rank_m(d1)
    r2 = rank_m(d2)
    b0 = V - r1
    b1 = E - r1 - r2
    b2 = F - r2

    print(f"  β0={b0}, β1={b1}, β2={b2}")
    print(f"  χ check: {b0 - b1 + b2} (should be {chi})")

    if b0 == 1 and b1 == 0 and b2 == 1:
        print(f"  → H_*(S²) ✓")
    elif b1 == 0 and b2 == 1:
        print(f"  → 多连通分量，各分量同调为 S²")
    else:
        g = (2 - chi) // 2
        print(f"  → 若为封闭定向曲面，亏格 g={g}")


def analyze_face_edge_degrees(N, verts, directed_edges, triangles):
    from collections import Counter

    undirected_edges = set()
    for (a, b) in directed_edges:
        undirected_edges.add((min(a, b), max(a, b)))
    edges_list = sorted(undirected_edges)

    faces_set = set()
    for (a, b, c) in triangles:
        faces_set.add(tuple(sorted([a, b, c])))
    faces_list = sorted(faces_set)

    edge_face_count = {e: 0 for e in edges_list}
    for (a, b, c) in faces_list:
        for (u, v) in [(a, b), (b, c), (a, c)]:
            edge_face_count[(min(u, v), max(u, v))] += 1

    # 每个面的边度数组合（排序后）
    face_degree_patterns = []
    for (a, b, c) in faces_list:
        degs = tuple(sorted([
            edge_face_count[(min(a, b), max(a, b))],
            edge_face_count[(min(b, c), max(b, c))],
            edge_face_count[(min(a, c), max(a, c))]
        ]))
        face_degree_patterns.append(degs)

    pattern_dist = Counter(face_degree_patterns)
    print(f"N={N} 面的边度数组合分布：")
    for pattern, cnt in sorted(pattern_dist.items()):
        print(f"  边度数={pattern} 的面：{cnt} 个")


def barycentric_subdivision_octahedron():
    """
    对 N=4 正八面体做重心细分，
    验证细分后仍然是 S²，且给出更高分辨率的三角剖分。
    """
    import numpy as np
    from itertools import combinations

    # 原始正八面体（N=4 中截面 + 循环方向三角面）
    from itertools import product
    N = 4
    verts = [v for v in product([0, 1], repeat=N) if sum(v) == 2]
    idx = {v: i for i, v in enumerate(verts)}

    directed = set()
    for v in verts:
        for i in range(N):
            for j in range(N):
                if i != j and v[i] == 1 and v[j] == 0:
                    u = list(v);
                    u[i] = 0;
                    u[j] = 1;
                    u = tuple(u)
                    if (j - i) % N <= N // 2:
                        directed.add((idx[v], idx[u]))

    undirected = set()
    for (a, b) in directed:
        undirected.add((min(a, b), max(a, b)))
    edges = sorted(undirected)

    tris_dir = []
    n = len(verts)
    for a, b, c in combinations(range(n), 3):
        if (a, b) in directed and (b, c) in directed and (c, a) in directed:
            tris_dir.append((a, b, c))
        elif (a, c) in directed and (c, b) in directed and (b, a) in directed:
            tris_dir.append((a, c, b))
    faces = sorted(set(tuple(sorted(t)) for t in tris_dir))

    # 重心细分
    # 新顶点：每条边的中点
    new_verts = list(range(len(verts)))  # 原始顶点保留
    edge_midpoint = {}
    for e in edges:
        mid_id = len(new_verts)
        edge_midpoint[e] = mid_id
        new_verts.append(e)  # 用边的端点对表示中点

    # 新三角面：每个原始三角面 (a,b,c) 分成 4 个小三角形
    # 中点：m_ab, m_bc, m_ac
    new_faces = []
    for (a, b, c) in faces:
        m_ab = edge_midpoint[(min(a, b), max(a, b))]
        m_bc = edge_midpoint[(min(b, c), max(b, c))]
        m_ac = edge_midpoint[(min(a, c), max(a, c))]
        new_faces.append(tuple(sorted([a, m_ab, m_ac])))
        new_faces.append(tuple(sorted([b, m_ab, m_bc])))
        new_faces.append(tuple(sorted([c, m_bc, m_ac])))
        new_faces.append(tuple(sorted([m_ab, m_bc, m_ac])))

    # 新边：从新三角面提取
    new_edges_set = set()
    for (a, b, c) in new_faces:
        new_edges_set.add((a, b));
        new_edges_set.add((b, c));
        new_edges_set.add((a, c))
    new_edges = sorted(new_edges_set)
    edge_idx2 = {e: i for i, e in enumerate(new_edges)}

    V = len(new_verts)
    E = len(new_edges)
    F = len(new_faces)
    chi = V - E + F
    print(f"重心细分后: V={V}, E={E}, F={F}, χ={chi}")

    # 同调群
    def rank_m(M):
        if M.size == 0: return 0
        s = np.linalg.svd(M.astype(float), compute_uv=False)
        return int(np.sum(s > 1e-6))

    d1 = np.zeros((V, E), dtype=int)
    for j, (a, b) in enumerate(new_edges):
        d1[a][j] = -1;
        d1[b][j] = 1

    d2 = np.zeros((E, F), dtype=int)
    for k, (a, b, c) in enumerate(new_faces):
        d2[edge_idx2[(a, b)]][k] = 1
        d2[edge_idx2[(b, c)]][k] = 1
        d2[edge_idx2[(a, c)]][k] = -1

    print(f"  ∂1∂2 = 0: {np.all(d1 @ d2 == 0)}")
    r1, r2 = rank_m(d1), rank_m(d2)
    b0, b1, b2 = V - r1, E - r1 - r2, F - r2
    print(f"  β0={b0}, β1={b1}, β2={b2}, χ={b0 - b1 + b2}")
    if b0 == 1 and b1 == 0 and b2 == 1:
        print("  → H_*(S²) ✓ 重心细分保持拓扑")


def iterated_subdivision(n_iterations):
    """
    对 N=4 正八面体做 n 次重心细分，
    每次验证：∂²=0, H_*(S²), 流形条件（每边恰好2个面）
    """
    import numpy as np
    from itertools import product, combinations

    def rank_m(M):
        if M.size == 0: return 0
        s = np.linalg.svd(M.astype(float), compute_uv=False)
        return int(np.sum(s > 1e-6))

    # 初始正八面体
    N = 4
    base_verts = [v for v in product([0, 1], repeat=N) if sum(v) == 2]
    n_v = len(base_verts)

    directed = set()
    for v in base_verts:
        for i in range(N):
            for j in range(N):
                if i != j and v[i] == 1 and v[j] == 0:
                    u = list(v);
                    u[i] = 0;
                    u[j] = 1;
                    u = tuple(u)
                    if (j - i) % N <= N // 2:
                        vi = base_verts.index(v)
                        ui = base_verts.index(u)
                        directed.add((vi, ui))

    undirected = set((min(a, b), max(a, b)) for (a, b) in directed)
    edges = sorted(undirected)

    tris_dir = []
    for a, b, c in combinations(range(n_v), 3):
        if (a, b) in directed and (b, c) in directed and (c, a) in directed:
            tris_dir.append((a, b, c))
        elif (a, c) in directed and (c, b) in directed and (b, a) in directed:
            tris_dir.append((a, c, b))
    faces = sorted(set(tuple(sorted(t)) for t in tris_dir))

    # 用整数 ID 表示顶点（不依赖原始坐标）
    # 顶点 0..n_v-1 是原始顶点，后续新增中点
    next_id = [n_v]
    edge_to_mid = {}

    def get_mid(a, b):
        e = (min(a, b), max(a, b))
        if e not in edge_to_mid:
            edge_to_mid[e] = next_id[0]
            next_id[0] += 1
        return edge_to_mid[e]

    current_faces = faces
    current_edges = edges

    for iteration in range(n_iterations):
        new_faces = []
        new_edges_set = set()

        for (a, b, c) in current_faces:
            m_ab = get_mid(a, b)
            m_bc = get_mid(b, c)
            m_ac = get_mid(a, c)
            for tri in [
                tuple(sorted([a, m_ab, m_ac])),
                tuple(sorted([b, m_ab, m_bc])),
                tuple(sorted([c, m_bc, m_ac])),
                tuple(sorted([m_ab, m_bc, m_ac]))
            ]:
                new_faces.append(tri)
                for u, v in [(tri[0], tri[1]), (tri[1], tri[2]), (tri[0], tri[2])]:
                    new_edges_set.add((min(u, v), max(u, v)))

        current_faces = sorted(set(new_faces))
        current_edges = sorted(new_edges_set)

    V = next_id[0]
    E = len(current_edges)
    F = len(current_faces)
    chi = V - E + F

    # 流形条件
    from collections import Counter
    edge_face_count = Counter()
    for (a, b, c) in current_faces:
        for u, v in [(a, b), (b, c), (a, c)]:
            edge_face_count[(min(u, v), max(u, v))] += 1
    manifold = all(c == 2 for c in edge_face_count.values())

    # 同调群
    edge_idx = {e: i for i, e in enumerate(current_edges)}
    d1 = np.zeros((V, E), dtype=int)
    for j, (a, b) in enumerate(current_edges):
        d1[a][j] = -1;
        d1[b][j] = 1
    d2 = np.zeros((E, F), dtype=int)
    for k, (a, b, c) in enumerate(current_faces):
        d2[edge_idx[(a, b)]][k] = 1
        d2[edge_idx[(b, c)]][k] = 1
        d2[edge_idx[(a, c)]][k] = -1

    r1, r2 = rank_m(d1), rank_m(d2)
    b0, b1, b2 = V - r1, E - r1 - r2, F - r2

    print(f"细分{n_iterations}次: V={V}, E={E}, F={F}, χ={chi}, "
          f"流形={manifold}, β=({b0},{b1},{b2}), "
          f"{'H_*(S²) ✓' if b0 == 1 and b1 == 0 and b2 == 1 else '非S²'}")


if __name__ == "__main__":
    # # 实验一：完整 {0,1}^4，全部公理
    # print("\n【实验一】完整 {0,1}^4（A4 + A6 + A7）")
    # h_full = run(N=4, midplane_only=False)
    #
    # # 实验二：只取中截面（A8 约束）
    # print("\n【实验二】中截面子空间（A4 + A6 + A7 + A8）")
    # h_mid = run(N=4, midplane_only=True)
    #
    # # 实验三：N=3 对照组
    # print("\n【实验三】{0,1}^3 对照（A4 + A6 + A7）")
    # h_3 = run(N=3, midplane_only=False)
    #
    # # 实验四：弱化 A6（中截面内部双向）
    # print("\n【实验四】弱化 A6（跨截面有向，截面内双向）")
    # vertices4 = all_vertices(4)
    # edges4 = apply_A4(vertices4)
    # directed4 = apply_A6_dag_weak(edges4, vertices4)
    # faces4 = apply_A7_faces(directed4, vertices4)
    # print(f"有向边数：{len(directed4)}，面数：{len(faces4)}")
    # d1_4, d2_4, _, _, _ = build_boundary_operators(vertices4, directed4, faces4)
    # check4 = d1_4 @ d2_4
    # print(f"∂_1∘∂_2=0: {np.all(check4 == 0)}")
    # h4 = compute_homology(d1_4, d2_4)
    # for k, v in h4.items():
    #     print(f"  {k} = {v}")
    #
    # run_quotient(N=4)
    #
    # # 实验七：先验证代码能否识别 Klein 瓶（基准测试）
    # print("\n【先做基准测试，确认代码正确性】")
    # h7 = run_klein_bottle_2d()
    #
    # # 实验六：显式粘合
    # h6 = run_klein_bottle_with_loops()
    #
    # # h9 = run_experiment_9()
    # h9 = run_experiment_9_fixed()
    # h_clem = run_clem_morse_v3(N=4)

    # h_clem = run_clem_octahedron(N=4)

    # h_clem = run_clem_full_space(N=4)

    # h_clem = run_clem_full_v2(N=4)
    # h_clem = run_clem_full_v3(N=4)
    # h_clem = run_clem_final(N=4)
    # run_johnson_graph_homology(N_list=[4, 6, 8])
    # run_A7_filtered_homology(N=6)
    # run_sphere_triangulation(N=6)
    # run_sphere_triangulation(N=4)
    # run_A7_global_experiment(N=6)
    # run_A7_global_v2(N=6)
    # run_A7_global_v2(N=4)
    # build_axiom_space_sequential(N=6)
    # build_sequential_with_quotient(N=4)
    # build_sequential_with_quotient(N=6)
    # build_directed_A1prime(N=4)
    # build_directed_A1prime(N=6)
    # build_circular_directed_A1prime(N=4)
    # build_circular_directed_A1prime(N=6)
    #
    # for N in [4, 6]:
    #     verts, dedges, tris = build_circular_directed_A1prime(N)
    #     compute_homology_from_directed(N, verts, dedges, tris)
    # for N in [4, 6]:
    #     verts, dedges, tris = build_circular_directed_A1prime(N)
    #     analyze_edge_degrees(N, verts, dedges, tris)

    # for N in [4, 6]:
    #     verts, dedges, tris = build_circular_directed_A1prime(N)
    #     analyze_face_edge_degrees(N, verts, dedges, tris)
    # barycentric_subdivision_octahedron()
    for n in range(4):
        iterated_subdivision(n)
