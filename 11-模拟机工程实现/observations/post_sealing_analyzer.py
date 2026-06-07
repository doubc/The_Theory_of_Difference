"""
observations/post_sealing_analyzer.py — Phase 13 P1: 密封后动力学分析器

目标：分析密封事件之后系统继续演化的行为。

核心问题链（Phase 13 P1）：
  H155-1: 密封后继续运行（保持 A1 持续 +1），sealed bits 是否重新激活？
           → 密封是否单向不可逆？
  H155-2: 密封后若大幅增加差异密度（N0 扩张），sealed bits 是否解封？
           → 差异被"压缩"后能否被"重新激活"？

设计原则：
  1. 不修改现有 engine 或 TemporalTrace 代码
  2. 增量式分析：接收 TemporalTrace 结果，事后分析
  3. 分割三个阶段：Pre-seal / During-seal / Post-seal
  4. 可扩展：支持 exp_155 中条件 A/B/C 三种配置

使用方式：
    trace = TemporalTrace(N=48, total_steps=3000, sample_interval=1)
    trace.run(verbose=False)
    
    analyzer = PostSealingAnalyzer(trace)
    report = analyzer.full_report()
    print(report['summary'])
"""

import numpy as np
from typing import Dict, List, Optional, Set, Tuple


class PhaseBoundary:
    """密封事件的阶段边界检测"""

    def __init__(self, cascade_series: List[int],
                 seal_step: int,
                 n_bits: int,
                 pre_buffer: int = 20,
                 post_buffer: int = 50):
        """
        Args:
            cascade_series: TemporalTrace.get_cascade_series() 输出
            seal_step: TemporalTrace.seal_step (首个密封发生的 step)
            n_bits: 总比特数
            pre_buffer: 密封前用于"pre"阶段的缓冲步数
            post_buffer: 密封后用于"post"阶段的缓冲步数（排除 cascade 窗口）
        """
        self.cascade_series = cascade_series
        self.seal_step = seal_step
        self.n_bits = n_bits
        self.pre_buffer = pre_buffer
        self.post_buffer = post_buffer

        # 通过 cascade 分析推断密封事件窗口
        self.cascade_window_start, self.cascade_window_end = self._find_cascade_window()
        self.pre_seal_end = self.cascade_window_start - 1
        self.post_seal_start = self.cascade_window_end + 1

    def _find_cascade_window(self) -> Tuple[int, int]:
        """检测密封事件的主 cascade 窗口

        方法：从 seal_step 开始向两边扩展，找到连续的"活跃密封"步。
        核心密封事件是指：连续步中至少有一个比特被密封。
        窗口边界是第一个和最后一个有密封活动的步。

        Returns:
            (start_step, end_step) — cascade 窗口的起止步索引
        """
        if self.seal_step < 0 or self.seal_step >= len(self.cascade_series):
            return (-1, -1)

        # 从 seal_step 向后找第一个非零 cascade
        start = self.seal_step
        while start > 0 and self.cascade_series[start - 1] > 0:
            start -= 1

        # 从 seal_step 向前找最后一个非零 cascade
        end = self.seal_step
        while end < len(self.cascade_series) - 1 and self.cascade_series[end + 1] > 0:
            end += 1

        return (start, end)

    def get_phases(self) -> Dict[str, slice]:
        """获取三个阶段对应的 slice

        Returns:
            {
                'pre': slice(...),      # 密封前
                'cascade': slice(...),  # 密封事件窗口
                'post': slice(...),     # 密封后
            }
        """
        if self.cascade_window_start < 0:
            return {'pre': slice(0, 0), 'cascade': slice(0, 0), 'post': slice(0, 0)}

        return {
            'pre': slice(0, self.pre_seal_end + 1) if self.pre_seal_end > 0 else slice(0, 0),
            'cascade': slice(self.cascade_window_start, self.cascade_window_end + 1),
            'post': slice(self.post_seal_start, len(self.cascade_series)),
        }


class PostSealingAnalyzer:
    """密封后动力学分析器

    对 TemporalTrace 的结果进行事后分析，聚焦密封后的行为。
    """

    def __init__(self, trace: 'TemporalTrace'):
        """
        Args:
            trace: 已运行的 TemporalTrace 实例
        """
        self.trace = trace
        self.history = trace.history
        self.N = trace.N

        # 阶段边界
        self.cascade_series = trace.get_cascade_series()
        self.boundary = PhaseBoundary(
            cascade_series=self.cascade_series,
            seal_step=trace.seal_step,
            n_bits=trace.N,
        )

    # ============================================================
    # 密封后稳定性分析
    # ============================================================

    def sealed_bit_stability(self) -> Dict:
        """分析密封后 sealed bits 的稳定性

        核心问题：密封后，已密封的比特是否一直保持密封状态？

        Returns:
            {
                'fraction_always_sealed': float,   # 始终密封的比例
                'fraction_ever_unsealed': float,   # 曾解密封的比例
                'unseal_events': int,               # 解封事件总数
                'max_consecutive_unsealed': int,    # 最大连续解封步数
                'unseal_bit_ids': List[int],        # 曾解封的比特索引
                'per_bit_stats': Dict[int, Dict],   # 逐比特统计
            }
        """
        post = self.boundary.get_phases().get('post')
        if not post or post.stop <= post.start:
            return {
                'fraction_always_sealed': 0.0,
                'fraction_ever_unsealed': 0.0,
                'n_pre_sealed_bits': 0,
                'n_always_sealed': 0,
                'n_ever_unsealed': 0,
                'unseal_events': 0,
                'max_consecutive_unsealed': 0,
                'unseal_bit_ids': [],
                'per_bit_stats': {},
            }

        post_records = self.history[post]

        # 获取密封后每个比特的密封状态序列
        n_steps = len(post_records)
        per_bit = {}

        for bit in range(self.N):
            # 检查此比特在密封前是否已被密封
            was_sealed_pre = False
            for r in self.history[:post.start]:
                if bit in r.sealed_bits:
                    was_sealed_pre = True
                    break

            if not was_sealed_pre:
                continue  # 只分析密封时已密封的比特

            # 跟踪密封后的密封状态
            sealed_after = [1 if bit in r.sealed_bits else 0 for r in post_records]
            n_always = sum(sealed_after)
            n_unsealed = n_steps - n_always

            # 检测解封事件（从1变0的转换）
            unseal_events = 0
            max_run = 0
            current_run = 0
            for i, s in enumerate(sealed_after):
                if s == 0:
                    current_run += 1
                    if i == 0 or sealed_after[i - 1] == 1:
                        unseal_events += 1
                else:
                    max_run = max(max_run, current_run)
                    current_run = 0
            max_run = max(max_run, current_run)

            per_bit[bit] = {
                'always_sealed': n_always == n_steps,
                'n_steps_unsealed': n_unsealed,
                'n_unseal_events': unseal_events,
                'max_consecutive_unsealed': max_run,
                'fraction_time_sealed': n_always / max(n_steps, 1),
            }

        if not per_bit:
            return {
                'fraction_always_sealed': 0.0,
                'fraction_ever_unsealed': 0.0,
                'unseal_events': 0,
                'max_consecutive_unsealed': 0,
                'unseal_bit_ids': [],
                'per_bit_stats': {},
            }

        always_sealed_bits = [b for b, s in per_bit.items() if s['always_sealed']]
        ever_unsealed_bits = [b for b, s in per_bit.items() if not s['always_sealed']]
        total_pre_sealed = len(per_bit)

        return {
            'fraction_always_sealed': len(always_sealed_bits) / max(total_pre_sealed, 1),
            'fraction_ever_unsealed': len(ever_unsealed_bits) / max(total_pre_sealed, 1),
            'n_pre_sealed_bits': total_pre_sealed,
            'n_always_sealed': len(always_sealed_bits),
            'n_ever_unsealed': len(ever_unsealed_bits),
            'unseal_events': sum(s['n_unseal_events'] for s in per_bit.values()),
            'max_consecutive_unsealed': max(s['max_consecutive_unsealed'] for s in per_bit.values()),
            'unseal_bit_ids': ever_unsealed_bits,
            'per_bit_stats': per_bit,
        }

    # ============================================================
    # 密封后活跃度分析
    # ============================================================

    def residual_activity(self) -> Dict:
        """分析密封后剩余未密封比特的活跃度

        核心问题：密封后，非密封比特是否还在活跃演化？

        Returns:
            {
                'post_seal_n_free': int,               # 密封后最终自由比特数
                'post_seal_free_flip_rate': float,     # 自由比特翻转率（per step）
                'post_seal_injection_rate': float,     # 注射率（per step）
                'post_seal_absorption_rate': float,    # 吸收率（per step）
                'post_seal_lateral_rate': float,       # 横向演化率（per step）
                'vs_pre_injection_ratio': float,       # 后/前 注射比
                'vs_pre_flip_ratio': float,            # 后/前 翻转比
            }
        """
        phases = self.boundary.get_phases()
        pre = phases.get('pre')
        post = phases.get('post')

        if not pre or not post or pre.stop <= pre.start or post.stop <= post.start:
            return {
                'post_seal_n_free': 0,
                'post_seal_free_flip_rate': 0.0,
                'post_seal_injection_rate': 0.0,
                'post_seal_absorption_rate': 0.0,
                'post_seal_lateral_rate': 0.0,
                'vs_pre_injection_ratio': 0.0,
                'vs_pre_flip_ratio': 0.0,
            }

        pre_records = self.history[pre]
        post_records = self.history[post]

        def _phase_stats(records):
            if not records:
                return {'flip_rate': 0.0, 'inject_rate': 0.0, 'absorb_rate': 0.0, 'lateral_rate': 0.0}
            n = len(records)
            total_flips = sum(1 for r in records if r.flip_idx >= 0)
            total_inj = sum(r.n_inject for r in records)
            total_abs = sum(r.n_absorb for r in records)
            total_lat = sum(r.n_lateral for r in records)
            return {
                'flip_rate': total_flips / max(n, 1),
                'inject_rate': total_inj / max(n, 1),
                'absorb_rate': total_abs / max(n, 1),
                'lateral_rate': total_lat / max(n, 1),
                'n_steps': n,
            }

        pre_stats = _phase_stats(pre_records)
        post_stats = _phase_stats(post_records)

        # 密封后最终自由比特数
        if post_records:
            last_record = post_records[-1]
            n_free = last_record.state.numel() - len(last_record.sealed_bits)
            # 更精确：计算汉明重量中未密封的部分
            n_free_zeros = int((last_record.state < 0.5).sum().item())
            n_sealed = len(last_record.sealed_bits)
        else:
            n_free = 0
            n_free_zeros = 0
            n_sealed = 0

        return {
            'post_seal_n_free': n_free_zeros - n_sealed,  # 自由非密封比特
            'post_seal_free_flip_rate': post_stats['flip_rate'],
            'post_seal_injection_rate': post_stats['inject_rate'],
            'post_seal_absorption_rate': post_stats['absorb_rate'],
            'post_seal_lateral_rate': post_stats['lateral_rate'],
            'post_seal_n_steps': post_stats['n_steps'],
            'pre_flip_rate': pre_stats['flip_rate'],
            'pre_injection_rate': pre_stats['inject_rate'],
            'vs_pre_injection_ratio': (
                post_stats['inject_rate'] / max(pre_stats['inject_rate'], 1e-8)
                if pre_stats['inject_rate'] > 0 else float('inf')
            ),
            'vs_pre_flip_ratio': (
                post_stats['flip_rate'] / max(pre_stats['flip_rate'], 1e-8)
                if pre_stats['flip_rate'] > 0 else float('inf')
            ),
        }

    # ============================================================
    # 汉明重量趋势分析
    # ============================================================

    def weight_trend(self) -> Dict:
        """分析密封后汉明重量的变化趋势

        核心问题：密封后，系统重量（w）是否继续变化？
        是趋向稳定还是继续震荡？

        Returns:
            {
                'pre_mean_w': float,            # 密封前平均重量
                'post_mean_w': float,           # 密封后平均重量
                'post_w_std': float,            # 密封后重量标准差
                'post_w_slope': float,          # 密封后重量变化斜率（每步）
                'post_w_drift': float,          # 密封后总漂移量
                'post_w_min': int,              # 密封后最小重量
                'post_w_max': int,              # 密封后最大重量
            }
        """
        phases = self.boundary.get_phases()
        pre = phases.get('pre')
        post = phases.get('post')

        if not pre or not post or pre.stop <= pre.start or post.stop <= post.start:
            return {
                'pre_mean_w': 0.0,
                'post_mean_w': 0.0,
                'post_w_std': 0.0,
                'post_w_slope': 0.0,
                'post_w_drift': 0.0,
            }

        pre_w = np.array([r.w for r in self.history[pre]])
        post_w = np.array([r.w for r in self.history[post]])

        if len(post_w) < 2:
            slope = 0.0
        else:
            x = np.arange(len(post_w))
            slope = np.polyfit(x, post_w, 1)[0]

        return {
            'pre_mean_w': float(pre_w.mean()) if len(pre_w) > 0 else 0.0,
            'post_mean_w': float(post_w.mean()),
            'post_w_std': float(post_w.std()),
            'post_w_slope': float(slope),
            'post_w_drift': float(post_w[-1] - post_w[0]) if len(post_w) > 1 else 0.0,
            'post_w_min': int(post_w.min()),
            'post_w_max': int(post_w.max()),
            'pre_w_series': pre_w.tolist() if len(pre_w) <= 200 else pre_w[::len(pre_w)//200].tolist(),
            'post_w_series': post_w.tolist() if len(post_w) <= 200 else post_w[::len(post_w)//200].tolist(),
        }

    # ============================================================
    # 完整报告
    # ============================================================

    def full_report(self) -> Dict:
        """生成密封后动力学完整分析报告

        Returns:
            {
                'metadata': {...},         # 运行参数
                'boundary': {...},         # 阶段边界
                'sealed_bit_stability': {...},  # H155-1 检测
                'residual_activity': {...},     # 残余活跃度
                'weight_trend': {...},          # 重量趋势
                'summary': str,                 # 文字摘要
                'h155_1_verdict': str,          # H155-1 检验结果
            }
        """
        metadata = {
            'N': self.N,
            'total_steps': len(self.history),
            'seal_step': self.trace.seal_step,
            'n_sealed_bits': len(self.trace._seal_step_per_bit),
        }

        phases = self.boundary.get_phases()
        boundary_info = {
            'pre_steps': (phases['pre'].stop - phases['pre'].start) if phases['pre'].stop > phases['pre'].start else 0,
            'cascade_steps': (phases['cascade'].stop - phases['cascade'].start) if phases['cascade'].stop > phases['cascade'].start else 0,
            'post_steps': (phases['post'].stop - phases['post'].start) if phases['post'].stop > phases['post'].start else 0,
            'cascade_window': [self.boundary.cascade_window_start, self.boundary.cascade_window_end],
        }

        stability = self.sealed_bit_stability()
        activity = self.residual_activity()
        weight = self.weight_trend()

        # H155-1 检验：密封是否单向不可逆？
        if stability['n_pre_sealed_bits'] > 0:
            if stability['fraction_ever_unsealed'] < 0.05:
                h155_1 = {
                    'verdict': 'H155-1 成立 (确实单向不可逆)',
                    'confidence': 'high' if stability['n_pre_sealed_bits'] > 10 else 'medium',
                    'detail': f'{stability["fraction_always_sealed"]:.1%} 的密封比特始终保持密封'
                }
            elif stability['fraction_ever_unsealed'] < 0.30:
                h155_1 = {
                    'verdict': 'H155-1 部分成立 (大部分单向不可逆，少量边缘比特有波动)',
                    'confidence': 'medium',
                    'detail': f'{stability["fraction_always_sealed"]:.1%} 始终密封, {stability["n_ever_unsealed"]} 个比特有解封事件'
                }
            else:
                h155_1 = {
                    'verdict': 'H155-1 不成立 (密封具有可逆性)',
                    'confidence': 'high',
                    'detail': f'{stability["fraction_ever_unsealed"]:.1%} 的密封比特曾解除密封'
                }
        else:
            h155_1 = {
                'verdict': 'H155-1 无法判断 (无密封比特供分析)',
                'confidence': 'none',
                'detail': '实验运行未产生密封事件'
            }

        # 生成文字摘要
        summary_parts = [
            f"Phase 13 P1 — 密封后动力学分析",
            f"  系统: N={metadata['N']}, total_steps={metadata['total_steps']}",
            f"  密封: step {metadata['seal_step']}, {metadata['n_sealed_bits']} bits",
            f"  阶段: pre={boundary_info['pre_steps']}步, cascade={boundary_info['cascade_steps']}步, post={boundary_info['post_steps']}步",
            f"",
            f"  [H155-1] {h155_1['verdict']}",
            f"    {h155_1['detail']}",
        ]

        if weight['post_n_steps'] if 'post_n_steps' in weight else activity.get('post_seal_n_steps', 0) > 0:
            summary_parts.extend([
                f"  [残余活跃度]",
                f"    密封后翻转率: {activity['post_seal_free_flip_rate']:.4f}/步",
                f"    密封后注射率: {activity['post_seal_injection_rate']:.4f}/步",
                f"    注射率比(后/前): {activity['vs_pre_injection_ratio']:.2f}",
                f"  [重量趋势]",
                f"    前后均值: {weight['pre_mean_w']:.1f} → {weight['post_mean_w']:.1f}",
                f"    漂移量: {weight['post_w_drift']:+.1f} (斜率={weight['post_w_slope']:.4f}/步)",
            ])

        summary = '\n'.join(summary_parts)

        return {
            'metadata': metadata,
            'boundary': boundary_info,
            'sealed_bit_stability': stability,
            'residual_activity': activity,
            'weight_trend': weight,
            'summary': summary,
            'h155_1_verdict': h155_1,
        }

    # ============================================================
    # 批量分析
    # ============================================================

    @staticmethod
    def batch_report(traces: List['TemporalTrace']) -> Dict:
        """对多次运行进行批量分析，汇总统计

        Args:
            traces: TemporalTrace 实例列表（已运行）

        Returns:
            {
                'n_runs': int,
                'post_seal_activity_rate': Dict,    # 密封后活跃率统计
                'sealed_stability': Dict,            # 密封稳定性统计
                'h155_1_votes': Dict[str, int],      # H155-1 判定汇总
                'summary': str,
            }
        """
        if not traces:
            return {'n_runs': 0, 'summary': 'No runs to analyze.'}

        results = []
        for trace in traces:
            analyzer = PostSealingAnalyzer(trace)
            results.append(analyzer.full_report())

        # 汇总 H155-1 投票
        h155_votes = {'stable': 0, 'partial': 0, 'reversible': 0, 'unknown': 0}
        for r in results:
            v = r['h155_1_verdict']['verdict']
            if '成立' in v and '部分' not in v:
                h155_votes['stable'] += 1
            elif '部分成立' in v:
                h155_votes['partial'] += 1
            elif '不成立' in v:
                h155_votes['reversible'] += 1
            else:
                h155_votes['unknown'] += 1

        # 汇总密封后活跃率
        post_flip_rates = [r['residual_activity']['post_seal_free_flip_rate'] for r in results]
        post_inj_rates = [r['residual_activity']['post_seal_injection_rate'] for r in results]
        pre_inj_rates = [r['residual_activity']['pre_injection_rate'] for r in results if 'pre_injection_rate' in r['residual_activity']]
        inj_ratios = [r['residual_activity']['vs_pre_injection_ratio'] for r in results
                     if 'vs_pre_injection_ratio' in r['residual_activity']
                     and r['residual_activity']['vs_pre_injection_ratio'] != float('inf')]

        # 汇总密封稳定性
        always_fractions = [r['sealed_bit_stability']['fraction_always_sealed']
                           for r in results if r['sealed_bit_stability']['n_pre_sealed_bits'] > 0]

        summary_parts = [
            f"Phase 13 P1 批量分析 ({len(traces)} runs)",
            f"  H155-1 投票: 稳定={h155_votes['stable']}, 部分={h155_votes['partial']}, 可逆={h155_votes['reversible']}, 未知={h155_votes['unknown']}",
        ]

        if post_flip_rates:
            summary_parts.append(
                f"  密封后翻转率: μ={np.mean(post_flip_rates):.4f}, σ={np.std(post_flip_rates):.4f}"
            )
        if inj_ratios:
            summary_parts.append(
                f"  注射率比(后/前): μ={np.mean(inj_ratios):.2f}x, σ={np.std(inj_ratios):.2f}"
            )
        if always_fractions:
            summary_parts.append(
                f"  密封比特保持率: μ={np.mean(always_fractions):.3f}, σ={np.std(always_fractions):.3f}"
            )

        return {
            'n_runs': len(traces),
            'h155_1_votes': h155_votes,
            'post_seal_activity_rate': {
                'mean_flip_rate': float(np.mean(post_flip_rates)) if post_flip_rates else 0.0,
                'std_flip_rate': float(np.std(post_flip_rates)) if post_flip_rates else 0.0,
                'mean_inj_ratio': float(np.mean(inj_ratios)) if inj_ratios else 0.0,
                'std_inj_ratio': float(np.std(inj_ratios)) if inj_ratios else 0.0,
            },
            'sealed_stability': {
                'mean_always_fraction': float(np.mean(always_fractions)) if always_fractions else 0.0,
                'std_always_fraction': float(np.std(always_fractions)) if always_fractions else 0.0,
            },
            'summary': '\n'.join(summary_parts),
        }