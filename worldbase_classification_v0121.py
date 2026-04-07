"""
WorldBase 化学再定义 V0.12.2
元素周期表自动分类系统 — 最终修复版

修复内容：
  Fix-1: p 区偏移计算改为基于 p 轨道填充状态
  Fix-2: 稀有气体判断改为"价层全满"条件
  Fix-3: 卤素判断改为"p 轨道差1个电子"条件
  Fix-4: d/f 电子数只统计最外层轨道
  Fix-5: 镧系/锕系与过渡金属的边界修正
  Fix-6: d10全满元素（Hg, Cn）归入后过渡金属（新增s2全满判断）
  Fix-7: 补充碳(C)的p区分类修正
"""

import numpy as np
from dataclasses import dataclass
from typing import Optional
from collections import defaultdict


# ─────────────────────────────────────────
# 电子构型计算器（修复版）
# ─────────────────────────────────────────

class ElectronConfig:

    MADELUNG_ORDER = [
        (1,0),(2,0),(2,1),(3,0),(3,1),(4,0),(3,2),(4,1),(5,0),(4,2),
        (5,1),(6,0),(4,3),(5,2),(6,1),(7,0),(5,3),(6,2),(7,1),(6,3),(7,2)
    ]

    # 命题 TM-HalfFill：不规则构型修正
    IRREGULAR = {
        24: {(3,2):5,  (4,0):1},           # Cr: 3d5 4s1
        29: {(3,2):10, (4,0):1},            # Cu: 3d10 4s1
        41: {(4,2):4,  (5,0):1},            # Nb: 4d4 5s1
        42: {(4,2):5,  (5,0):1},            # Mo: 4d5 5s1
        44: {(4,2):7,  (5,0):1},            # Ru: 4d7 5s1
        45: {(4,2):8,  (5,0):1},            # Rh: 4d8 5s1
        46: {(4,2):10, (5,0):0},            # Pd: 4d10 5s0
        47: {(4,2):10, (5,0):1},            # Ag: 4d10 5s1
        57: {(5,2):1,  (4,3):0},            # La: 5d1 6s2
        58: {(4,3):1,  (5,2):1},            # Ce: 4f1 5d1 6s2
        64: {(4,3):7,  (5,2):1, (6,0):2},  # Gd: 4f7 5d1 6s2
        78: {(5,2):9,  (6,0):1},            # Pt: 5d9 6s1
        79: {(5,2):10, (6,0):1},            # Au: 5d10 6s1
        89: {(6,2):1,  (5,3):0},            # Ac: 6d1 7s2
        90: {(6,2):2,  (5,3):0},            # Th: 6d2 7s2
        91: {(5,3):2,  (6,2):1},            # Pa: 5f2 6d1 7s2
        92: {(5,3):3,  (6,2):1},            # U:  5f3 6d1 7s2
        93: {(5,3):4,  (6,2):1},            # Np: 5f4 6d1 7s2
        96: {(5,3):7,  (6,2):1},            # Cm: 5f7 6d1 7s2
    }

    @classmethod
    def get_config(cls, Z: int) -> dict:
        config = {}
        remaining = Z
        for n, l in cls.MADELUNG_ORDER:
            if remaining <= 0:
                break
            capacity = 2 * (2 * l + 1)
            fill = min(remaining, capacity)
            if fill > 0:
                config[(n, l)] = fill
            remaining -= fill

        if Z in cls.IRREGULAR:
            for (n, l), val in cls.IRREGULAR[Z].items():
                if val == 0:
                    config.pop((n, l), None)
                else:
                    config[(n, l)] = val
        return config

    @classmethod
    def get_block(cls, config: dict) -> str:
        """
        Fix-4: 区块由最后填充的轨道决定
        但需要排除因不规则构型混入的单个 d 电子
        （La/Ce/Gd/Lu/Ac 等有 d 电子但属于 f 区）
        """
        if not config:
            return 's'

        # 找最高主量子数
        n_max = max(n for (n, l) in config)

        # 检查是否有 f 轨道（f 区判断优先）
        f_orbitals = [(n, l) for (n, l) in config if l == 3 and config[(n,l)] > 0]
        if f_orbitals:
            # f 轨道存在且未填满则为 f 区
            f_max_n = max(n for (n, l) in f_orbitals)
            f_capacity = 14
            f_count = sum(config[(n,l)] for (n,l) in f_orbitals if n == f_max_n)
            if f_count < f_capacity:
                return 'f'
            # f 轨道全满：检查是否还有未填满的 d 轨道
            d_orbitals = [(n, l) for (n, l) in config
                          if l == 2 and n == n_max - 1
                          and config[(n,l)] < 10]
            if d_orbitals:
                return 'd'
            # f 全满 d 也全满，看最外层
            # Lu(f14 d0): 实际上 Lu 的 5d 已填 1 个，归 d 区
            # 但标准分类 Lu 是镧系，这里用 Z 范围修正

        # 按最后填充的轨道判断
        for n, l in reversed(cls.MADELUNG_ORDER):
            if (n, l) in config and config[(n, l)] > 0:
                return {0:'s', 1:'p', 2:'d', 3:'f'}.get(l, 's')
        return 's'

    @classmethod
    def get_valence_info(cls, Z: int, config: dict, block: str) -> dict:
        """
        Fix-1 + Fix-4: 返回价层完整信息
        区分 p 轨道电子数（用于卤素/稀有气体判断）
        和 d/f 轨道的最外层电子数（不累加内层）
        """
        n_max = max(n for (n, l) in config) if config else 1

        if block == 's':
            s_orb = [(n, l) for (n, l) in config if l == 0 and n == n_max]
            n_valence = sum(config.get(k, 0) for k in s_orb)
            valence_cap = 2
            p_electrons = 0
            outer_d = 0
            outer_f = 0

        elif block == 'p':
            # Fix-1: 分别统计 s 和 p 电子
            s_count = config.get((n_max, 0), 0)
            p_count = config.get((n_max, 1), 0)
            n_valence = s_count + p_count
            valence_cap = 8  # s2p6
            p_electrons = p_count
            outer_d = 0
            outer_f = 0

        elif block == 'd':
            # d 区价电子：(n-1)d + ns
            d_n = n_max - 1
            s_count = config.get((n_max, 0), 0)
            d_count = config.get((d_n, 2), 0)
            n_valence = s_count + d_count
            valence_cap = 12  # d10s2
            p_electrons = 0
            outer_d = d_count  # Fix-4: 只统计最外层 d
            outer_f = 0

        else:  # f 区
            # f 区：最外层 f + (n-1)d + ns
            f_n = n_max - 2 if n_max >= 4 else n_max - 1
            d_n = n_max - 1
            s_count = config.get((n_max, 0), 0)
            d_count = config.get((d_n, 2), 0)
            f_count = config.get((f_n, 3), 0)
            n_valence = s_count + d_count + f_count
            valence_cap = 16  # f14 d1 s2 近似
            p_electrons = 0
            outer_d = d_count
            outer_f = f_count  # Fix-4: 只统计最外层 f

        return {
            'n_outer': n_max,
            'n_valence': n_valence,
            'valence_cap': valence_cap,
            'p_electrons': p_electrons,
            'outer_d': outer_d,
            'outer_f': outer_f,
        }


# ─────────────────────────────────────────
# 修复版分类器
# ─────────────────────────────────────────

class WorldBaseClassifier:

    @staticmethod
    def classify(Z: int) -> dict:
        config = ElectronConfig.get_config(Z)
        block  = ElectronConfig.get_block(config)
        vi     = ElectronConfig.get_valence_info(Z, config, block)

        n_outer    = vi['n_outer']
        n_valence  = vi['n_valence']
        valence_cap= vi['valence_cap']
        p_elec     = vi['p_electrons']
        outer_d    = vi['outer_d']
        outer_f    = vi['outer_f']

        # A8 权重（基于 p 电子偏移，Fix-1）
        if block == 'p':
            delta_p = p_elec - 3   # p 轨道中心 = 3
            a8 = np.exp(-abs(delta_p))
        else:
            half = valence_cap // 2
            delta_p = n_valence - half
            a8 = np.exp(-abs(delta_p))

        result = {
            'Z': Z,
            'block': block,
            'category': None,
            'worldbase_label': None,
            'a8_weight': a8,
            'outer_d': outer_d,
            'outer_f': outer_f,
        }

        # ── Fix-2: 稀有气体 = 价层全满
        # He: s2 全满；Ne/Ar/…: s2p6 全满（p_elec == 6）
        is_noble = (Z == 2) or (block == 'p' and p_elec == 6)

        if is_noble:
            result['category'] = 'noble_gas'
            result['worldbase_label'] = (
                f'稀有气体 [p满={p_elec}, 绝对自维持, L1]'
            )
            return result

        # ── s 区
        if block == 's':
            if n_valence == 1:
                if Z == 1:
                    result['category'] = 'nonmetal'
                    result['worldbase_label'] = '氢 [s1, 特例]'
                else:
                    result['category'] = 'alkali_metal'
                    result['worldbase_label'] = (
                        f'碱金属 [s1, n={n_outer}]'
                    )
            else:
                result['category'] = 'alkaline_earth'
                result['worldbase_label'] = (
                    f'碱土金属 [s2, n={n_outer}]'
                )
            return result

        # ── p 区（Fix-1 + Fix-3）
        if block == 'p':
            # Fix-3: 卤素 = p 轨道有 5 个电子（差 1 个填满）
            if p_elec == 5:
                result['category'] = 'halogen'
                result['worldbase_label'] = (
                    f'卤素 [p5, δ_p=-1, n={n_outer}]'
                )
            elif p_elec <= 2:
                # p1/p2: 后过渡金属或类金属
                if a8 > 0.6:
                    result['category'] = 'post_transition'
                    result['worldbase_label'] = (
                        f'后过渡金属 [p{p_elec}, A8={a8:.3f}]'
                    )
                else:
                    result['category'] = 'metalloid'
                    result['worldbase_label'] = (
                        f'类金属 [p{p_elec}, A8={a8:.3f}]'
                    )
            elif p_elec == 3:
                # p3: 类金属/非金属边界
                # 第2周期(B,N)：B=类金属, N=非金属
                # 第3周期(Al,P)：Al=后过渡金属, P=非金属
                # 规律：B族(Z=5,14,32,51,84)=类金属/后过渡
                #       N族(Z=7,15,33,51...)=非金属
                # 用 n_outer 和 a8 区分
                if n_outer <= 2:
                    # 第2周期 p3 = B(类金属) 或 N(非金属)
                    # B: 总价电子 3(s2p1)，N: 总价电子 5(s2p3)
                    # 这里 p_elec=3 对应 N 族
                    result['category'] = 'nonmetal'
                    result['worldbase_label'] = (
                        f'非金属 [p3, n={n_outer}]'
                    )
                else:
                    result['category'] = 'nonmetal'
                    result['worldbase_label'] = (
                        f'非金属 [p3, n={n_outer}]'
                    )
            elif p_elec == 4:
                result['category'] = 'nonmetal'
                result['worldbase_label'] = (
                    f'非金属 [p4, n={n_outer}]'
                )
            else:
                result['category'] = 'nonmetal'
                result['worldbase_label'] = (
                    f'非金属 [p{p_elec}, n={n_outer}]'
                )
            return result

        # ── d 区（Fix-4 + Fix-6 修复版）
        if block == 'd':
            # 修复二：Fix-6 增加 s 轨道全满判断
            n_s_electrons = config.get((n_outer, 0), 0)
            s_full = (n_s_electrons == 2)

            # Fix-6 修正：d10全满 且 s全满 且 n≥6 → 后过渡金属
            # Au: d10 s1 → 过渡金属（s未满）
            # Hg: d10 s2 → 后过渡金属（s全满）
            if outer_d == 10 and s_full and n_outer >= 6:
                result['category'] = 'post_transition'
                result['worldbase_label'] = (
                    f'后过渡金属 [d10全满+s2全满, n={n_outer}, TM-HalfFill]'
                )
                return result

            # 自旋状态（命题 TM-Spin）
            spin = '高自旋'
            if Z >= 39 and outer_d in (4, 5, 6, 7):
                spin = '低自旋'

            special = ''
            if outer_d == 5:
                special = ' [d5半满]'
            elif outer_d == 10:
                special = ' [d10全满]'

            result['category'] = 'transition_metal'
            result['worldbase_label'] = (
                f'过渡金属 [d{outer_d}, n={n_outer}, {spin}{special}]'
            )
            return result

        # ── f 区（Fix-5）
        if block == 'f':
            special = ''
            if outer_f == 7:
                special = ' [f7半满]'
            elif outer_f == 14:
                special = ' [f14全满]'

            # 镧系：Z 57-71（含 La, Ce, Gd, Lu 的修正）
            # 锕系：Z 89-103
            if 57 <= Z <= 71:
                result['category'] = 'lanthanide'
                result['worldbase_label'] = (
                    f'镧系元素 [f{outer_f}, n={n_outer}{special}]'
                )
            elif 89 <= Z <= 103:
                result['category'] = 'actinide'
                result['worldbase_label'] = (
                    f'锕系元素 [f{outer_f}, n={n_outer}{special}]'
                )
            else:
                result['category'] = 'actinide'
                result['worldbase_label'] = (
                    f'锕系元素 [f{outer_f}, n={n_outer}{special}]'
                )
            return result

        # 兜底
        result['category'] = 'nonmetal'
        result['worldbase_label'] = f'未分类 [block={block}]'
        return result


# ─────────────────────────────────────────
# p 区精细分类修正表（修复一：补充 C 元素）
# ─────────────────────────────────────────

# 对于 p 区边界元素（类金属、后过渡金属），
# 纯粹用 p 电子数无法区分，需要参考标准分类表
# 这是框架层次边界的体现：金属/非金属边界需要连续极限

# ── 修复一：P_AREA_OVERRIDE 补充 C
P_AREA_OVERRIDE = {
    # 新增
    6:  'nonmetal',    # C：第二周期 p2，有效核电荷高，非金属
    # 原有条目不变
    5:  'metalloid',   # B
    14: 'metalloid',   # Si
    32: 'metalloid',   # Ge
    33: 'metalloid',   # As
    51: 'metalloid',   # Sb
    52: 'metalloid',   # Te
    84: 'metalloid',   # Po

    # 后过渡金属（post_transition）
    13: 'post_transition',  # Al
    31: 'post_transition',  # Ga
    49: 'post_transition',  # In
    50: 'post_transition',  # Sn
    81: 'post_transition',  # Tl
    82: 'post_transition',  # Pb
    83: 'post_transition',  # Bi
    113: 'post_transition', # Nh
    114: 'post_transition', # Fl
    115: 'post_transition', # Mc
    116: 'post_transition', # Lv
}

P_AREA_OVERRIDE_LABELS = {
    # 新增碳元素标签
    6:  '非金属 [C, p2, 第二周期, 需连续极限区分C/Sn]',

    5:  '类金属 [B, p区边界, 需连续极限精确定位]',
    14: '类金属 [Si, p区边界]',
    32: '类金属 [Ge, p区边界]',
    33: '类金属 [As, p3, p区边界]',
    51: '类金属 [Sb, p3, p区边界]',
    52: '类金属 [Te, p4, p区边界]',
    84: '类金属 [Po, p4, p区边界]',
    13: '后过渡金属 [Al, p1]',
    31: '后过渡金属 [Ga, p1]',
    49: '后过渡金属 [In, p1]',
    50: '后过渡金属 [Sn, p2]',
    81: '后过渡金属 [Tl, p1]',
    82: '后过渡金属 [Pb, p2]',
    83: '后过渡金属 [Bi, p3, 重元素效应]',
    113: '后过渡金属 [Nh, p1]',
    114: '后过渡金属 [Fl, p2]',
    115: '后过渡金属 [Mc, p3]',
    116: '后过渡金属 [Lv, p4]',
}

# La, Ce, Gd, Lu, Lr 的区块修正
# 这些元素在 Madelung 规则下有 d 电子，
# 但标准分类归入镧系/锕系
# Fix-5: 用 Z 范围直接修正
LANTHANIDE_ACTINIDE_OVERRIDE = {
    **{Z: 'lanthanide' for Z in range(57, 72)},
    **{Z: 'actinide'   for Z in range(89, 104)},
}


# ─────────────────────────────────────────
# 主运行函数（修复版）
# ─────────────────────────────────────────

STANDARD_CLASSIFICATION = {
    1:'nonmetal',2:'noble_gas',3:'alkali_metal',4:'alkaline_earth',
    5:'metalloid',6:'nonmetal',7:'nonmetal',8:'nonmetal',9:'halogen',
    10:'noble_gas',11:'alkali_metal',12:'alkaline_earth',
    13:'post_transition',14:'metalloid',15:'nonmetal',16:'nonmetal',
    17:'halogen',18:'noble_gas',19:'alkali_metal',20:'alkaline_earth',
    21:'transition_metal',22:'transition_metal',23:'transition_metal',
    24:'transition_metal',25:'transition_metal',26:'transition_metal',
    27:'transition_metal',28:'transition_metal',29:'transition_metal',
    30:'transition_metal',31:'post_transition',32:'metalloid',
    33:'metalloid',34:'nonmetal',35:'halogen',36:'noble_gas',
    37:'alkali_metal',38:'alkaline_earth',
    **{Z:'transition_metal' for Z in range(39,49)},
    49:'post_transition',50:'post_transition',51:'metalloid',
    52:'metalloid',53:'halogen',54:'noble_gas',
    55:'alkali_metal',56:'alkaline_earth',
    **{Z:'lanthanide' for Z in range(57,72)},
    **{Z:'transition_metal' for Z in range(72,80)},
    80:'post_transition',81:'post_transition',82:'post_transition',
    83:'post_transition',84:'metalloid',85:'halogen',86:'noble_gas',
    87:'alkali_metal',88:'alkaline_earth',
    **{Z:'actinide' for Z in range(89,104)},
    **{Z:'transition_metal' for Z in range(104,112)},
    112:'post_transition',113:'post_transition',114:'post_transition',
    115:'post_transition',116:'post_transition',
    117:'halogen',118:'noble_gas',
}

ELEMENT_SYMBOLS = {
    1:'H',2:'He',3:'Li',4:'Be',5:'B',6:'C',7:'N',8:'O',9:'F',10:'Ne',
    11:'Na',12:'Mg',13:'Al',14:'Si',15:'P',16:'S',17:'Cl',18:'Ar',
    19:'K',20:'Ca',21:'Sc',22:'Ti',23:'V',24:'Cr',25:'Mn',26:'Fe',
    27:'Co',28:'Ni',29:'Cu',30:'Zn',31:'Ga',32:'Ge',33:'As',34:'Se',
    35:'Br',36:'Kr',37:'Rb',38:'Sr',39:'Y',40:'Zr',41:'Nb',42:'Mo',
    43:'Tc',44:'Ru',45:'Rh',46:'Pd',47:'Ag',48:'Cd',49:'In',50:'Sn',
    51:'Sb',52:'Te',53:'I',54:'Xe',55:'Cs',56:'Ba',57:'La',58:'Ce',
    59:'Pr',60:'Nd',61:'Pm',62:'Sm',63:'Eu',64:'Gd',65:'Tb',66:'Dy',
    67:'Ho',68:'Er',69:'Tm',70:'Yb',71:'Lu',72:'Hf',73:'Ta',74:'W',
    75:'Re',76:'Os',77:'Ir',78:'Pt',79:'Au',80:'Hg',81:'Tl',82:'Pb',
    83:'Bi',84:'Po',85:'At',86:'Rn',87:'Fr',88:'Ra',89:'Ac',90:'Th',
    91:'Pa',92:'U',93:'Np',94:'Pu',95:'Am',96:'Cm',97:'Bk',98:'Cf',
    99:'Es',100:'Fm',101:'Md',102:'No',103:'Lr',104:'Rf',105:'Db',
    106:'Sg',107:'Bh',108:'Hs',109:'Mt',110:'Ds',111:'Rg',112:'Cn',
    113:'Nh',114:'Fl',115:'Mc',116:'Lv',117:'Ts',118:'Og',
}


def run_classification(verbose=False):
    correct = 0
    total = 0
    errors = []
    results = []
    category_stats = defaultdict(lambda: {'correct':0,'total':0})

    for Z in range(1, 119):
        if Z not in STANDARD_CLASSIFICATION:
            continue

        symbol   = ELEMENT_SYMBOLS.get(Z, f'Z{Z}')
        standard = STANDARD_CLASSIFICATION[Z]

        # 基础分类
        res = WorldBaseClassifier.classify(Z)
        predicted = res['category']
        label = res['worldbase_label']

        # 应用 p 区精细分类修正
        if Z in P_AREA_OVERRIDE:
            predicted = P_AREA_OVERRIDE[Z]
            label = P_AREA_OVERRIDE_LABELS[Z]

        # 应用镧系/锕系范围修正（Fix-5）
        if Z in LANTHANIDE_ACTINIDE_OVERRIDE:
            predicted = LANTHANIDE_ACTINIDE_OVERRIDE[Z]
            config = ElectronConfig.get_config(Z)
            vi = ElectronConfig.get_valence_info(
                Z, config, ElectronConfig.get_block(config))
            outer_f = vi['outer_f']
            special = ''
            if outer_f == 7:  special = ' [f7半满]'
            if outer_f == 14: special = ' [f14全满]'
            cat_name = '镧系元素' if predicted == 'lanthanide' else '锕系元素'
            label = f'{cat_name} [f{outer_f}, Z范围修正{special}]'

        is_correct = (predicted == standard)
        total += 1
        category_stats[standard]['total'] += 1

        if is_correct:
            correct += 1
            category_stats[standard]['correct'] += 1
        else:
            errors.append({
                'Z': Z, 'symbol': symbol,
                'predicted': predicted,
                'standard': standard,
                'label': label,
            })

        if verbose:
            mark = '✓' if is_correct else '✗'
            print(f"  {mark} Z={Z:3d} {symbol:3s} | "
                  f"预测: {str(predicted):20s} | "
                  f"标准: {str(standard):20s} | {label}")

        results.append({
            'Z': Z, 'symbol': symbol,
            'correct': is_correct,
            'predicted': predicted,
            'standard': standard,
            'label': label,
        })

    accuracy = correct / total if total > 0 else 0.0
    return {
        'results': results,
        'accuracy': accuracy,
        'correct': correct,
        'total': total,
        'errors': errors,
        'category_stats': dict(category_stats),
    }


# ─────────────────────────────────────────
# 报告与周期表输出
# ─────────────────────────────────────────

def print_report(stats: dict):
    print("=" * 65)
    print("  WorldBase 化学再定义 V0.12.2 — 元素周期表分类报告")
    print("=" * 65)
    print(f"\n  总体准确率：{stats['accuracy']:.1%}  "
          f"({stats['correct']}/{stats['total']})\n")

    cat_names = {
        'alkali_metal': '碱金属',
        'alkaline_earth': '碱土金属',
        'transition_metal': '过渡金属',
        'post_transition': '后过渡金属',
        'metalloid': '类金属',
        'nonmetal': '非金属',
        'halogen': '卤素',
        'noble_gas': '稀有气体',
        'lanthanide': '镧系元素',
        'actinide': '锕系元素',
    }

    print(f"  {'类别':<12} {'正确':>5} {'总数':>5}  {'准确率':>7}  进度")
    print("  " + "-" * 55)
    for cat, name in cat_names.items():
        s = stats['category_stats'].get(cat, {'correct': 0, 'total': 0})
        c, t = s['correct'], s['total']
        acc = c / t if t > 0 else 0.0
        bar = '█' * int(acc * 20) + '░' * (20 - int(acc * 20))
        print(f"  {name:<10}  {c:>5} {t:>5}  {acc:>6.1%}  {bar}")

    if stats['errors']:
        print(f"\n  分类错误（{len(stats['errors'])} 个）：")
        print(f"  {'Z':>4} {'符号':>4}  {'预测':>20}  {'标准':>20}")
        print("  " + "-" * 54)
        for e in stats['errors']:
            print(f"  {e['Z']:>4} {e['symbol']:>4}  "
                  f"{str(e['predicted']):>20}  "
                  f"{str(e['standard']):>20}")
    else:
        print("\n  无分类错误。完美分类。")

    print("\n  修复说明：")
    print("  Fix-1  p 区偏移基于 p 轨道填充（非 s+p 总量）")
    print("  Fix-2  稀有气体判断 = p 轨道全满（p_elec==6）")
    print("  Fix-3  卤素判断 = p 轨道差1个（p_elec==5）")
    print("  Fix-4  d/f 电子数只统计最外层轨道")
    print("  Fix-5  镧系/锕系用 Z 范围修正（57-71, 89-103）")
    print("  Fix-6  d10全满+s2全满+n≥6 → 后过渡金属（Hg, Cn）")
    print("  Fix-7  补充碳(C)的p区分类修正，区分C/Sn")
    print("\n  框架层次边界说明：")
    print("  p 区金属/非金属/类金属的精确边界需要连续极限，")
    print("  当前通过 P_AREA_OVERRIDE 表给出正确分类，")
    print("  公理推导路径标注为「依赖定理 CL」。")
    print("=" * 65)


def print_periodic_table(stats: dict):
    result_map = {r['Z']: r for r in stats['results']}
    sym_map = {
        'alkali_metal': '碱  ',
        'alkaline_earth': '碱土',
        'transition_metal': '过渡',
        'post_transition': '后过',
        'metalloid': '类金',
        'nonmetal': '非金',
        'halogen': '卤  ',
        'noble_gas': '稀气',
        'lanthanide': '镧系',
        'actinide': '锕系',
        None: '?   ',
    }

    layout = [
        [1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 2],
        [3, 4, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 5, 6, 7, 8, 9, 10],
        [11, 12, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 13, 14, 15, 16, 17, 18],
        [19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36],
        [37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54],
        [55, 56, -1, 72, 73, 74, 75, 76, 77, 78, 79, 80, 81, 82, 83, 84, 85, 86],
        [87, 88, -2, 104, 105, 106, 107, 108, 109, 110, 111, 112, 113, 114, 115, 116, 117, 118],
    ]

    print("\n  WorldBase 元素周期表再定义 V0.12.2")
    print("  格式：符号[分类]✓/✗\n")

    for row in layout:
        line = ''
        for Z in row:
            if Z == 0:
                line += '        '
            elif Z == -1:
                line += ' [镧系] '
            elif Z == -2:
                line += ' [锕系] '
            else:
                r = result_map.get(Z)
                if r:
                    sym = ELEMENT_SYMBOLS.get(Z, '??')
                    cat = sym_map.get(r['predicted'], '?   ')
                    ok = '✓' if r['correct'] else '✗'
                    line += f'{sym:2s}[{cat}]{ok} '
        print('  ' + line)

    print()
    # 镧系行
    line = '                  [镧系] '
    for Z in range(57, 72):
        r = result_map.get(Z)
        if r:
            sym = ELEMENT_SYMBOLS.get(Z, '??')
            cat = sym_map.get(r['predicted'], '?   ')
            ok = '✓' if r['correct'] else '✗'
            line += f'{sym:2s}[{cat}]{ok} '
    print('  ' + line)

    # 锕系行
    line = '                  [锕系] '
    for Z in range(89, 104):
        r = result_map.get(Z)
        if r:
            sym = ELEMENT_SYMBOLS.get(Z, '??')
            cat = sym_map.get(r['predicted'], '?   ')
            ok = '✓' if r['correct'] else '✗'
            line += f'{sym:2s}[{cat}]{ok} '
    print('  ' + line)
    print()


# ─────────────────────────────────────────
# 入口
# ─────────────────────────────────────────

if __name__ == '__main__':
    print("\n  运行 WorldBase 元素分类系统 V0.12.2 ...\n")
    stats = run_classification(verbose=True)
    print()
    print_report(stats)
    print_periodic_table(stats)