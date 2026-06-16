"""axiom_layer.py — 公理约束层

在九机制和 DifferenceField 之间插入公理约束。
每步运行: 先检查公理约束, 再执行机制, 最后验证结果。

设计原则:
- 机制负责"做什么" (动力学)
- 公理负责"允许什么" (约束)
- 两者正交: 公理不限制机制的内部逻辑, 只约束输入输出
"""
from __future__ import annotations
import numpy as np
from typing import Optional
from .axiom_checker import AxiomChecker
from .core import DifferenceField


class AxiomLayer:
    """公理约束层 — 包裹 DifferenceField, 施加公理约束"""
    
    def __init__(self, field: DifferenceField, checker: Optional[AxiomChecker] = None):
        self.field = field
        self.checker = checker or AxiomChecker(field.N, field.rng)
        self._axiom_violations = []  # 记录违反公理的尝试
    
    # ================================================================
    # 公理约束包装器
    # ================================================================
    
    def apply_flip(self, bit_idx: int, direction: str = 'inject') -> bool:
        """应用一个翻转, 检查公理约束
        
        Args:
            bit_idx: 要翻转的位
            direction: 'inject' (0→1) 或 'absorb' (1→0)
        
        Returns:
            True 如果翻转被允许并执行
        """
        f = self.field
        old_val = int(f.state[bit_idx])
        new_val = 1 if direction == 'inject' else 0
        
        # A4: 检查翻转是否改变了一个位
        if old_val == new_val:
            return False
        
        # A6: 检查方向约束
        allowed, reason = self.checker.check_A6(f.state, bit_idx)
        if not allowed:
            self._axiom_violations.append(('A6', bit_idx, reason))
            return False
        
        # A5: 检查守恒约束
        if direction == 'inject':
            allowed, reason = self.checker.check_A5_inject(f.state, 1)
            if not allowed:
                self._axiom_violations.append(('A5_inject', bit_idx, reason))
                return False
            self.checker.record_inject(1)
        else:
            allowed, reason = self.checker.check_A5_absorb(f.state, 1)
            if not allowed:
                self._axiom_violations.append(('A5_absorb', bit_idx, reason))
                return False
            self.checker.record_absorb(1)
        
        # 执行翻转
        f.state[bit_idx] = new_val
        
        # A6: 更新方向
        self.checker.update_A6_direction(bit_idx, old_val, new_val)
        
        return True
    
    def check_cycle(self) -> bool:
        """A7: 检查循环"""
        active = self.field.active_set()
        detected, reason = self.checker.check_A7(active)
        return detected
    
    def check_sealing(self) -> bool:
        """A9: 检查密封条件"""
        return self.checker.check_A9_sealing(
            self.field.active_set(),
            self.field.organizations
        )
    
    def step(self):
        """每步调用"""
        self.checker.step()
    
    def get_violations(self) -> list:
        """获取公理违反记录"""
        return self._axiom_violations.copy()
    
    def clear_violations(self):
        """清空违反记录"""
        self._axiom_violations.clear()
    
    def get_summary(self) -> dict:
        """获取公理状态摘要"""
        summary = self.checker.get_summary()
        summary['n_violations'] = len(self._axiom_violations)
        return summary
