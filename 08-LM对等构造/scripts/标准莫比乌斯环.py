import numpy as np
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
import json
from datetime import datetime


def mobius_strip(R=1.0, w_max=0.8, n_points=100, m_points=50):
    """
    生成标准莫比乌斯环（扭转1/2圈）的参数坐标

    参数:
    R: 中心圆半径
    w_max: 最大带宽（避免自相交，通常 w_max < R）
    n_points: 沿环方向的采样点数
    m_points: 沿带宽方向的采样点数

    返回:
    X, Y, Z: 莫比乌斯环的三维坐标矩阵
    """
    # 参数范围
    u = np.linspace(0, 2 * np.pi, n_points)  # 沿环的角度
    v = np.linspace(-w_max / 2, w_max / 2, m_points)  # 沿带宽的位置

    # 创建网格
    U, V = np.meshgrid(u, v)

    # 莫比乌斯环参数方程（扭转1/2圈）
    X = (R + V * np.cos(U / 2)) * np.cos(U)
    Y = (R + V * np.cos(U / 2)) * np.sin(U)
    Z = V * np.sin(U / 2)

    return X, Y, Z, U, V


def find_all_self_intersections(R=1.0, w_max=0.8, u_resolution=500, v_resolution=200, tolerance=1e-4):
    """
    精确计算莫比乌斯环的所有自相交点

    使用高效的数值方法搜索所有可能的自相交点

    参数:
    R: 中心圆半径
    w_max: 最大带宽
    u_resolution: u方向的采样分辨率
    v_resolution: v方向的采样分辨率
    tolerance: 判断重合的容差

    返回:
    intersections: 自相交点列表，每个元素包含位置、参数等信息
    """
    print(f"正在搜索自相交点 (u分辨率={u_resolution}, v分辨率={v_resolution})...")

    u = np.linspace(0, 2 * np.pi, u_resolution)
    v = np.linspace(-w_max / 2, w_max / 2, v_resolution)

    # 预计算所有点的坐标
    U_grid, V_grid = np.meshgrid(u, v, indexing='ij')
    X_grid = (R + V_grid * np.cos(U_grid / 2)) * np.cos(U_grid)
    Y_grid = (R + V_grid * np.cos(U_grid / 2)) * np.sin(U_grid)
    Z_grid = V_grid * np.sin(U_grid / 2)

    # 展平为点列表
    points = np.column_stack([X_grid.ravel(), Y_grid.ravel(), Z_grid.ravel()])
    u_indices, v_indices = np.meshgrid(np.arange(u_resolution), np.arange(v_resolution), indexing='ij')
    u_flat = u_indices.ravel()
    v_flat = v_indices.ravel()

    intersections = []
    visited = set()

    # 使用空间哈希加速查找
    # 将空间划分为网格
    grid_size = tolerance
    spatial_hash = {}

    for idx, (x, y, z) in enumerate(points):
        # 计算网格键
        key = (int(x / grid_size), int(y / grid_size), int(z / grid_size))
        if key not in spatial_hash:
            spatial_hash[key] = []
        spatial_hash[key].append(idx)

    # 检查每个网格内的点对
    checked_pairs = set()

    for key, indices in spatial_hash.items():
        if len(indices) < 2:
            continue

        # 检查相邻网格
        neighbor_keys = [
            (key[0] + dx, key[1] + dy, key[2] + dz)
            for dx in [-1, 0, 1]
            for dy in [-1, 0, 1]
            for dz in [-1, 0, 1]
        ]

        all_nearby_indices = []
        for nk in neighbor_keys:
            if nk in spatial_hash:
                all_nearby_indices.extend(spatial_hash[nk])

        # 检查点对
        for i in range(len(indices)):
            for j in all_nearby_indices:
                if i >= j:
                    continue

                idx1, idx2 = indices[i], j
                pair_key = (min(idx1, idx2), max(idx1, idx2))

                if pair_key in checked_pairs:
                    continue
                checked_pairs.add(pair_key)

                # 确保是不同的参数点
                u1_idx, v1_idx = u_flat[idx1], v_flat[idx1]
                u2_idx, v2_idx = u_flat[idx2], v_flat[idx2]

                # 如果参数太接近，跳过
                if abs(u[u1_idx] - u[u2_idx]) < 0.1 and abs(v[v1_idx] - v[v2_idx]) < 0.01:
                    continue

                # 检查坐标是否重合
                dist = np.linalg.norm(points[idx1] - points[idx2])

                if dist < tolerance:
                    x, y, z = points[idx1]

                    # 避免重复记录
                    is_duplicate = False
                    for existing in intersections:
                        if np.linalg.norm(np.array(existing['point']) - np.array([x, y, z])) < tolerance:
                            is_duplicate = True
                            break

                    if not is_duplicate:
                        intersections.append({
                            'point': [float(x), float(y), float(z)],
                            'distance_to_origin': float(np.sqrt(x ** 2 + y ** 2 + z ** 2)),
                            'params1': {
                                'u': float(u[u1_idx]),
                                'v': float(v[v1_idx]),
                                'u_degrees': float(np.degrees(u[u1_idx]))
                            },
                            'params2': {
                                'u': float(u[u2_idx]),
                                'v': float(v[v2_idx]),
                                'u_degrees': float(np.degrees(u[u2_idx]))
                            },
                            'euclidean_distance': float(dist)
                        })

    # 按到原点的距离排序
    intersections.sort(key=lambda x: x['distance_to_origin'])

    print(f"✓ 找到 {len(intersections)} 个自相交点")

    return intersections


def save_intersections_to_file(intersections, R, w_max, filename=None):
    """
    将自相交点保存到JSON文件

    参数:
    intersections: 自相交点列表
    R: 中心圆半径
    w_max: 最大带宽
    filename: 输出文件名
    """
    if filename is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"mobius_intersections_R{R}_w{w_max}_{timestamp}.json"

    output_data = {
        'metadata': {
            'description': '莫比乌斯环自相交点数据',
            'generated_at': datetime.now().isoformat(),
            'parameters': {
                'R': R,
                'w_max': w_max,
                'twist': '1/2 turn (180 degrees)',
                'width_to_radius_ratio': w_max / R
            }
        },
        'summary': {
            'total_intersections': len(intersections),
            'min_distance_to_origin': min([p['distance_to_origin'] for p in intersections]) if intersections else None,
            'max_distance_to_origin': max([p['distance_to_origin'] for p in intersections]) if intersections else None,
            'mean_distance_to_origin': np.mean(
                [p['distance_to_origin'] for p in intersections]) if intersections else None
        },
        'intersections': intersections
    }

    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)

    print(f"\n数据已保存到: {filename}")

    # 同时保存一个简化的CSV格式
    csv_filename = filename.replace('.json', '.csv')
    with open(csv_filename, 'w', encoding='utf-8') as f:
        f.write("index,x,y,z,distance_to_origin,u1,v1,u2,v2,distance_between_params\n")
        for i, inter in enumerate(intersections):
            f.write(f"{i + 1},")
            f.write(f"{inter['point'][0]:.6f},{inter['point'][1]:.6f},{inter['point'][2]:.6f},")
            f.write(f"{inter['distance_to_origin']:.6f},")
            f.write(f"{inter['params1']['u']:.6f},{inter['params1']['v']:.6f},")
            f.write(f"{inter['params2']['u']:.6f},{inter['params2']['v']:.6f},")
            f.write(f"{inter['euclidean_distance']:.6e}\n")

    print(f"CSV数据已保存到: {csv_filename}")

    return filename, csv_filename


def analyze_zero_attractor(R=1.0, w_max=0.6):
    """
    分析莫比乌斯环上的"零吸引子"特性

    假设：
    - 自相交点对应代数结构中的零元
    - 加法操作：沿带宽方向 v 的移动
    - 乘法操作：沿环方向 u 的移动
    - 在交点处，两种操作等价
    """
    print("=" * 70)
    print("莫比乌斯环：加法与乘法等价性分析")
    print("=" * 70)

    # 理论计算自相交点
    # 对于标准莫比乌斯环，当 w_max 足够大时
    # 自相交发生在 x 轴负半轴

    # 关键观察：在 u=π 处
    u_critical = np.pi
    v_range = np.linspace(-w_max / 2, w_max / 2, 100)

    x_at_pi = (R + v_range * np.cos(u_critical / 2)) * np.cos(u_critical)
    y_at_pi = (R + v_range * np.cos(u_critical / 2)) * np.sin(u_critical)
    z_at_pi = v_range * np.sin(u_critical / 2)

    print(f"\n临界位置分析 (u = π):")
    print(f"  x 坐标范围: [{x_at_pi.min():.4f}, {x_at_pi.max():.4f}]")
    print(f"  y 坐标: {y_at_pi[0]:.6f} (理论上为 0)")
    print(f"  z 坐标范围: [{z_at_pi.min():.4f}, {z_at_pi.max():.4f}]")

    # 寻找可能的零点
    # 当 x=0 时：(R + v*cos(π/2))*cos(π) = 0
    # 即：-(R + v*0) = 0 => R = 0 (不可能)
    #
    # 但自相交点可能是：两个不同的 (u,v) 映射到同一点

    print(f"\n自相交条件分析:")
    print(f"  带宽/半径比 w/R = {w_max / R:.4f}")

    if w_max >= R:
        print(f"  ⚠ 带宽过大，必然存在自相交")
        # 自相交点的近似位置
        x_intersect = -(R - w_max / 2)
        print(f"  预期自相交位置: x ≈ {x_intersect:.4f}, y = 0, z ∈ [-{w_max / 2:.4f}, {w_max / 2:.4f}]")
    else:
        print(f"  ✓ 带宽安全，理论上无自相交")
        print(f"  但当视角旋转时，可能出现视觉重叠")

    # 计算曲面上的特殊点
    print(f"\n曲面上的关键点:")

    # 中心线 (v=0)
    center_line_x = R * np.cos(np.linspace(0, 2 * np.pi, 100))
    center_line_y = R * np.sin(np.linspace(0, 2 * np.pi, 100))
    center_line_z = np.zeros(100)
    print(f"  中心线: 半径 R={R}, 位于 z=0 平面")

    # 边界曲线
    v_edge = w_max / 2
    boundary_x = (R + v_edge * np.cos(np.linspace(0, 2 * np.pi, 100) / 2)) * np.cos(np.linspace(0, 2 * np.pi, 100))
    print(f"  边界曲线: 距离中心线 ±{v_edge:.4f}")

    # "零点"假设：自相交或对称中心
    print(f"\n零吸引子假设:")
    print(f"  候选位置 1: 原点 (0, 0, 0) - 几何中心")
    print(f"  候选位置 2: 自相交点 - 若存在")
    print(f"  候选位置 3: 对称轴上的特殊点")

    distance_to_origin = np.sqrt(center_line_x ** 2 + center_line_y ** 2 + center_line_z ** 2)
    print(f"  中心线到原点距离: {distance_to_origin[0]:.4f} (恒定 = R)")

    return {
        'center_radius': R,
        'half_width': w_max / 2,
        'width_ratio': w_max / R
    }


def plot_with_intersection_highlight(R=1.0, w_max=0.6, intersections=None):
    """
    绘制莫比乌斯环并高亮显示潜在的自相交点/零点
    """
    fig = plt.figure(figsize=(16, 6))

    # 生成莫比乌斯环
    X, Y, Z, U, V = mobius_strip(R=R, w_max=w_max, n_points=200, m_points=100)

    # 图1: 标准视图
    ax1 = fig.add_subplot(131, projection='3d')
    surf1 = ax1.plot_surface(X, Y, Z, cmap='viridis', alpha=0.8, edgecolor='none')

    # 高亮中心线
    u_center = np.linspace(0, 2 * np.pi, 100)
    x_center = R * np.cos(u_center)
    y_center = R * np.sin(u_center)
    z_center = np.zeros_like(u_center)
    ax1.plot(x_center, y_center, z_center, 'r-', linewidth=3, label='Center line (v=0)')

    # 标记原点
    ax1.scatter([0], [0], [0], color='black', s=200, marker='*', label='Origin (0,0,0)')

    # 标记自相交点
    if intersections:
        xs = [p['point'][0] for p in intersections[:10]]  # 只显示前10个
        ys = [p['point'][1] for p in intersections[:10]]
        zs = [p['point'][2] for p in intersections[:10]]
        ax1.scatter(xs, ys, zs, color='red', s=100, marker='o',
                    label=f'Self-intersections ({len(intersections)} total)')

    ax1.set_title('Standard View\n(Center line & Origin)', fontsize=11, fontweight='bold')
    ax1.legend(loc='upper right', fontsize=8)
    ax1.view_init(elev=30, azim=45)

    # 图2: 侧视图 - 观察自相交
    ax2 = fig.add_subplot(132, projection='3d')
    surf2 = ax2.plot_surface(X, Y, Z, cmap='plasma', alpha=0.8, edgecolor='none')

    # 从侧面观察，更容易看到自相交
    if intersections:
        xs = [p['point'][0] for p in intersections[:10]]
        ys = [p['point'][1] for p in intersections[:10]]
        zs = [p['point'][2] for p in intersections[:10]]
        ax2.scatter(xs, ys, zs, color='red', s=100, marker='o')

    ax2.set_title('Side View\n(Looking for intersection)', fontsize=11, fontweight='bold')
    ax2.view_init(elev=0, azim=90)

    # 图3: 顶视图 - 观察对称性
    ax3 = fig.add_subplot(133, projection='3d')
    surf3 = ax3.plot_surface(X, Y, Z, cmap='coolwarm', alpha=0.8, edgecolor='none')

    # 标记关键位置
    ax3.scatter([0], [0], [0], color='black', s=200, marker='*')

    if intersections:
        xs = [p['point'][0] for p in intersections[:10]]
        ys = [p['point'][1] for p in intersections[:10]]
        zs = [p['point'][2] for p in intersections[:10]]
        ax3.scatter(xs, ys, zs, color='red', s=100, marker='o')

    ax3.set_title('Top View\n(Symmetry analysis)', fontsize=11, fontweight='bold')
    ax3.view_init(elev=90, azim=0)

    plt.suptitle(f'Möbius Strip: Zero Attractor Analysis (R={R}, w={w_max})',
                 fontsize=14, fontweight='bold', y=1.02)
    plt.tight_layout()
    plt.savefig('mobius_zero_analysis.png', dpi=300, bbox_inches='tight')
    plt.show()

    return fig


def algebraic_interpretation(R=1.0, w_max=0.6):
    """
    代数解释：加法与乘法的等价性

    在莫比乌斯环上定义：
    - 加法 ⊕: 沿带宽方向 v 的平移
    - 乘法 ⊗: 沿环方向 u 的旋转

    在自相交点（零点），两种操作应该等价或坍缩
    """
    print("\n" + "=" * 70)
    print("代数结构解释")
    print("=" * 70)

    print("\n操作定义:")
    print("  加法 ⊕: (u, v₁) ⊕ (u, v₂) → (u, v₁ + v₂)")
    print("         沿带宽方向的线性叠加")
    print()
    print("  乘法 ⊗: (u₁, v) ⊗ (u₂, v) → (u₁ + u₂ mod 2π, v')")
    print("         沿环方向的旋转组合（带扭转）")
    print()

    print("零点特性假设:")
    print("  在自相交点 P₀:")
    print("    • P₀ ⊕ any = P₀  (加法吸收)")
    print("    • P₀ ⊗ any = P₀  (乘法吸收)")
    print("    • 加法 ≡ 乘法  (在 P₀ 附近等价)")
    print()

    print("拓扑解释:")
    print("  莫比乌斯环的单侧性意味着:")
    print("    • 绕行一周后，'上'变成'下'")
    print("    • 加法逆元与自身重合")
    print("    • 这暗示了某种自对偶性")
    print()

    # 数值验证
    print("数值验证:")
    u_test = np.pi
    v_test_values = [-w_max / 2, 0, w_max / 2]

    print(f"  在 u = π 处:")
    for v in v_test_values:
        x = (R + v * np.cos(u_test / 2)) * np.cos(u_test)
        y = (R + v * np.cos(u_test / 2)) * np.sin(u_test)
        z = v * np.sin(u_test / 2)
        r = np.sqrt(x ** 2 + y ** 2 + z ** 2)
        print(f"    v={v:6.3f}: (x,y,z)=({x:7.3f},{y:7.3f},{z:7.3f}), r={r:.4f}")


# ==================== 主程序 ====================
if __name__ == "__main__":
    print("=" * 70)
    print("莫比乌斯环：加法与乘法等价性验证")
    print("=" * 70)

    # 设置参数
    R = 1.0
    w_max = 0.8  # 增大带宽以产生明显的自相交

    print(f"\n参数设置:")
    print(f"  中心圆半径 R = {R}")
    print(f"  最大带宽 w_max = {w_max}")
    print(f"  扭转次数 = 1/2 圈（180°）")
    print(f"  带宽/半径比 = {w_max / R:.4f}")
    print()

    # 分析零点吸引子
    params = analyze_zero_attractor(R, w_max)

    # 代数解释
    algebraic_interpretation(R, w_max)

    # 查找所有自相交点
    print("\n" + "=" * 70)
    intersections = find_all_self_intersections(
        R=R,
        w_max=w_max,
        u_resolution=500,
        v_resolution=200,
        tolerance=1e-4
    )

    # 保存自相交点到文件
    if intersections:
        print("\n" + "=" * 70)
        print("保存自相交点数据...")
        print("=" * 70)

        json_file, csv_file = save_intersections_to_file(intersections, R, w_max)

        print(f"\n自相交点统计:")
        print(f"  总数: {len(intersections)}")
        if intersections:
            distances = [p['distance_to_origin'] for p in intersections]
            print(f"  到原点最小距离: {min(distances):.6f}")
            print(f"  到原点最大距离: {max(distances):.6f}")
            print(f"  到原点平均距离: {np.mean(distances):.6f}")

            # 显示前5个最近的点
            print(f"\n  最近的5个自相交点:")
            for i, inter in enumerate(intersections[:5]):
                pt = inter['point']
                print(f"    [{i + 1}] ({pt[0]:.6f}, {pt[1]:.6f}, {pt[2]:.6f}), "
                      f"r={inter['distance_to_origin']:.6f}")
    else:
        print("\n未找到自相交点")

    # 生成可视化图形
    print("\n生成可视化图形...")
    plot_with_intersection_highlight(R, w_max, intersections)

    print("\n完成！")
    print("\n关键观察:")
    print("  • 黑色交点可能是代数结构中的零元")
    print("  • 在该点，加法与乘法操作可能等价")
    print("  • 这与莫比乌斯环的非定向性相关")
    print(f"\n输出文件:")
    if intersections:
        print(f"  JSON: {json_file}")
        print(f"  CSV:  {csv_file}")
    print("  PNG:  mobius_zero_analysis.png")
