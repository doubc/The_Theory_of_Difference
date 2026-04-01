import itertools

import numpy as np

print("=" * 60)
print("WorldBase化学映射验证")
print("=" * 60)

# 定义量子态映射（简化版）
# 假设N=10，每位对应一个量子态
quantum_states = [
    "1s", "1s'",  # 1s轨道，自旋向上/向下
    "2s", "2s'",  # 2s轨道
    "2p_x", "2p_x'", "2p_y", "2p_y'", "2p_z", "2p_z'"  # 2p轨道
]


def state_to_electron_config(state):
    """将状态映射为电子构型"""
    config = {}
    for i, occupied in enumerate(state):
        if occupied:
            orbital = quantum_states[i].rstrip("'")
            spin = "↑" if "'" not in quantum_states[i] else "↓"
            if orbital not in config:
                config[orbital] = []
            config[orbital].append(spin)
    return config


def config_to_string(config):
    """将电子构型转换为字符串"""
    parts = []
    for orbital, spins in sorted(config.items()):
        parts.append(f"{orbital}^{len(spins)}")
    return " ".join(parts)


# 第二步：模拟电子填充
N = 10
states = list(itertools.product([0, 1], repeat=N))

print("量子态映射：")
for i, qs in enumerate(quantum_states):
    print(f"  位{i}: {qs}")

print("\n模拟电子填充（基于对称性）：")
print(f"{'电子数':<6} {'最优状态':<20} {'电子构型':<30}")
print("-" * 60)

for electron_num in range(0, N + 1):
    # 找出电子数为electron_num的所有状态
    states_with_num = [s for s in states if sum(s) == electron_num]
    if not states_with_num:
        continue


    # 计算每个状态的对称性（简化：电子分布均匀性）
    def symmetry(state):
        """计算状态的对称性"""
        # 将状态分为轨道组
        orbital_groups = {
            "1s": [0, 1],
            "2s": [2, 3],
            "2p": [4, 5, 6, 7, 8, 9]
        }

        # 计算每个轨道的电子数
        orbital_electrons = {}
        for orbital, indices in orbital_groups.items():
            orbital_electrons[orbital] = sum(state[i] for i in indices)

        # 对称性：电子在轨道间分布均匀
        total = sum(orbital_electrons.values())
        if total == 0:
            return 0

        # 理想分布：每个轨道电子数接近 total/轨道数
        ideal_per_orbital = total / len(orbital_groups)
        deviation = sum(abs(orbital_electrons[orb] - ideal_per_orbital)
                        for orb in orbital_groups)

        return 1 - deviation / (total + 1)


    # 找出对称性最高的状态
    symmetries = [symmetry(s) for s in states_with_num]
    best_idx = np.argmax(symmetries)
    best_state = states_with_num[best_idx]

    # 转换为电子构型
    config = state_to_electron_config(best_state)
    config_str = config_to_string(config)

    print(f"{electron_num:<6} {str(best_state):<20} {config_str:<30}")
