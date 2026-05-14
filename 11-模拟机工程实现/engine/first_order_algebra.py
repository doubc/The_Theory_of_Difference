"""
first_order_algebra.py — 一阶变易代数验证器

验证 WorldBase §5.4 的核心对易关系：
- CR-1: [E_ij, E_jk] = E_ik
- CR-2: [E_ij, E_ji] = x_i - x_j
- CR-3: [E_ij, x_i] = -E_ij, [E_ij, x_j] = E_ij

以及生成元计数：6非对角 + 2对角 = 8 → su(3)
"""

import torch
from typing import List, Optional, Dict, Tuple
from itertools import combinations


class FirstOrderAlgebra:
    """一阶变易代数验证器

    在三活跃位 {a, b, c} 上验证 E_ij 算符的代数结构。
    """

    def __init__(self, N: int = 6, device: str = "cpu"):
        self.N = N
        self.device = device

    def apply_E(self, state: torch.Tensor, i: int, j: int) -> Optional[torch.Tensor]:
        """E_ij|x> = |x'> if x_i=1, x_j=0"""
        if state[i] > 0.5 and state[j] < 0.5:
            new = state.clone()
            new[i] = 0.0
            new[j] = 1.0
            return new
        return None

    def verify_CR1(self, state: torch.Tensor, i: int, j: int, k: int) -> Dict:
        """验证 CR-1: [E_ij, E_jk] = E_ij E_jk - E_jk E_ij = E_ik"""
        results = {}

        # E_jk |state>
        E_jk_s = self.apply_E(state, j, k)
        # E_ij E_jk |state>
        if E_jk_s is not None:
            E_ij_E_jk_s = self.apply_E(E_jk_s, i, j)
        else:
            E_ij_E_jk_s = None

        # E_ij |state>
        E_ij_s = self.apply_E(state, i, j)
        # E_jk E_ij |state>
        if E_ij_s is not None:
            E_jk_E_ij_s = self.apply_E(E_ij_s, j, k)
        else:
            E_jk_E_ij_s = None

        # E_ik |state>
        E_ik_s = self.apply_E(state, i, k)

        # 对易子
        if E_ij_E_jk_s is not None and E_jk_E_ij_s is not None:
            commutator = E_ij_E_jk_s - E_jk_E_ij_s
            if E_ik_s is not None:
                holds = (commutator == E_ik_s).all().item()
            else:
                holds = False
            results['commutator'] = commutator.tolist()
        else:
            holds = 'N/A'
            results['commutator'] = None

        results['E_ij_E_jk'] = E_ij_E_jk_s.tolist() if E_ij_E_jk_s is not None else None
        results['E_jk_E_ij'] = E_jk_E_ij_s.tolist() if E_jk_E_ij_s is not None else None
        results['E_ik'] = E_ik_s.tolist() if E_ik_s is not None else None
        results['CR1_holds'] = holds

        return results

    def verify_CR2(self, state: torch.Tensor, i: int, j: int) -> Dict:
        """验证 CR-2: [E_ij, E_ji] = x_i - x_j"""
        results = {}

        # E_ij |state>
        E_ij_s = self.apply_E(state, i, j)
        # E_ji E_ij |state>
        if E_ij_s is not None:
            E_ji_E_ij_s = self.apply_E(E_ij_s, j, i)
        else:
            E_ji_E_ij_s = None

        # E_ji |state>
        E_ji_s = self.apply_E(state, j, i)
        # E_ij E_ji |state>
        if E_ji_s is not None:
            E_ij_E_ji_s = self.apply_E(E_ij_s, i, j)
        else:
            E_ij_E_ji_s = None

        # x_i - x_j (对角算符)
        xi_xj = state[i].item() - state[j].item()

        # 对易子 [E_ij, E_ji] = E_ij E_ji - E_ji E_ij
        if E_ij_E_ji_s is not None and E_ji_E_ij_s is not None:
            commutator = E_ij_E_ji_s - E_ji_E_ij_s
            # 对角算符作用：结果应该在 i 和 j 位置上有差值
            expected = torch.zeros_like(state)
            expected[i] = xi_xj
            expected[j] = -xi_xj
            holds = (commutator == expected).all().item()
            results['commutator'] = commutator.tolist()
        else:
            holds = 'N/A'
            results['commutator'] = None

        results['xi_minus_xj'] = xi_xj
        results['CR2_holds'] = holds

        return results

    def verify_CR3(self, state: torch.Tensor, i: int, j: int) -> Dict:
        """验证 CR-3: [E_ij, x_i] = -E_ij, [E_ij, x_j] = E_ij"""
        results = {}

        E_ij_s = self.apply_E(state, i, j)
        if E_ij_s is None:
            results['CR3_holds'] = 'N/A (E_ij invalid)'
            return results

        # [E_ij, x_i] = E_ij x_i - x_i E_ij
        # x_i |state> = state[i] |state> (位置算符本征值)
        # E_ij x_i |state> = state[i] E_ij |state>
        # x_i E_ij |state>: 在 E_ij|state> 中位置 i 的值
        xi_val = state[i].item()
        xj_val = state[j].item()

        # [E_ij, x_i]|state> = E_ij(x_i|state>) - x_i(E_ij|state>)
        # = xi_val * E_ij|state> - (E_ij|state>)[i] * E_ij|state>
        # 但 (E_ij|state>)[i] = 0（E_ij 把 i 位置从 1 翻成 0）
        # 所以 = xi_val * E_ij|state> - 0 = xi_val * E_ij|state>
        # 而 -E_ij|state> = -1 * E_ij|state>
        # 所以 [E_ij, x_i] = -E_ij 当 xi_val = 1 时成立

        # 简化：直接验证 E_ij 作用后的状态
        results['E_ij_state'] = E_ij_s.tolist()
        results['original_state'] = state.tolist()
        results['xi_value'] = xi_val
        results['xj_value'] = xj_val
        results['CR3_note'] = 'CR3 requires operator-level verification'
        results['CR3_holds'] = 'partial (state-level check)'

        return results

    def count_generators(self, active_bits: List[int]) -> Dict:
        """计算生成元数量

        k 个活跃位上：
        - 非对角：k*(k-1) 个 E_ij (i≠j)
        - 对角：k-1 个独立 (x_i - x_j)（受总权重守恒约束）
        - 总计：k*(k-1) + (k-1) = (k-1)(k+1) = k^2 - 1

        k=3: 8 个生成元 → su(3)
        k=2: 3 个生成元 → su(2)
        """
        k = len(active_bits)
        n_off_diag = k * (k - 1)
        n_diag = k - 1
        total = n_off_diag + n_diag

        algebra = None
        if k == 2:
            algebra = 'su(2)'
        elif k == 3:
            algebra = 'su(3)'
        elif k == 4:
            algebra = 'su(4) (excluded by A9)'

        return {
            'k': k,
            'n_off_diagonal': n_off_diag,
            'n_diagonal': n_diag,
            'total_generators': total,
            'algebra': algebra,
            'k_squared_minus_1': k**2 - 1,
        }

    def verify_all_CR(self, n_samples: int = 50) -> Dict:
        """在所有中截面状态上验证对易关系"""
        from engine.hamming_engine import HammingMeasurement

        N = self.N
        mid_w = N // 2

        cr1_pass = 0
        cr1_fail = 0
        cr1_na = 0
        cr2_pass = 0
        cr2_fail = 0
        cr2_na = 0

        for _ in range(n_samples):
            # 随机中截面状态
            state = torch.zeros(N, device=self.device)
            indices = torch.randperm(N, device=self.device)[:mid_w]
            state[indices] = 1.0

            ones = indices.tolist()
            if len(ones) < 3:
                continue

            # 取前 3 个活跃位
            a, b, c = ones[0], ones[1], ones[2]

            # CR-1
            r1 = self.verify_CR1(state, a, b, c)
            if r1['CR1_holds'] == True:
                cr1_pass += 1
            elif r1['CR1_holds'] == False:
                cr1_fail += 1
            else:
                cr1_na += 1

            # CR-2
            r2 = self.verify_CR2(state, a, b)
            if r2['CR2_holds'] == True:
                cr2_pass += 1
            elif r2['CR2_holds'] == False:
                cr2_fail += 1
            else:
                cr2_na += 1

        return {
            'CR1_pass': cr1_pass,
            'CR1_fail': cr1_fail,
            'CR1_N/A': cr1_na,
            'CR2_pass': cr2_pass,
            'CR2_fail': cr2_fail,
            'CR2_N/A': cr2_na,
        }
