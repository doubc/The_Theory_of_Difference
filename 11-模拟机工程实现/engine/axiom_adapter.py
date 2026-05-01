"""
差异论模拟机 - 公理系统适配层 (LEGACY)

⚠️  此文件为 M0 阶段遗留代码，使用 NumPy + 简化接口。
    M1 及之后请使用：
    - engine/reactor.py  → DifferenceReactor (PyTorch)
    - engine/trainer.py  → AxiomTrainer (PyTorch)
    - acl/axiom_base.py  → AxiomEngine + AxiomReport

    此文件中的 WorldEngine / AxiomSystem / AxiomReport 均为
    旧版实现，与新版不兼容。保留仅作参考。
"""
import warnings
warnings.warn(
    "engine.axiom_adapter is LEGACY. Use engine.reactor + engine.trainer instead.",
    DeprecationWarning,
    stacklevel=2,
)

import numpy as np
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field


# ============================================================
# 公理报告
# ============================================================

@dataclass
class AxiomReport:
    """公理违背报告"""
    axiom_id: str
    violated: bool
    value: float
    threshold: float
    message: str = ""


@dataclass
class StableStructure:
    """稳定结构"""
    region: np.ndarray
    stability_score: float
    step: int
    region_id: Tuple[int, ...] = None


@dataclass  
class StepReport:
    """单步报告"""
    step: int
    state: np.ndarray
    violations: Dict[str, AxiomReport]
    stable_structures: List[StableStructure]
    region_stats: Dict = field(default_factory=dict)


# ============================================================
# 公理系统 (适配层)
# ============================================================

class AxiomSystem:
    """
    公理系统适配层。
    
    将实际的公理类包装为统一的接口。
    """
    
    # A7 稳定结构阈值
    STABLE_STRUCTURE_THRESHOLD = 0.01
    
    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}
        self.reports: List[StepReport] = []
        
        # 导入实际公理
        from acl import axioms
        self.axioms = axioms
        
        # 公理ID映射
        self.axiom_map = {
            'A1': axioms.A1_DifferenceSource,
            'A2': axioms.A2_DiscreteEncoding,
            'A3': axioms.A3_Locality,
            'A4': axioms.A4_MinimalVariation,
            'A5': axioms.A5_Conservation,
            'A6': axioms.A6_FlowCoupling,
            'A7': axioms.A7_Stability,
            'A8': axioms.A8_SymmetrySink,
            'A9': axioms.A9_MinimalSufficient,
        }
    
    def check_all(self, state: np.ndarray) -> Dict[str, AxiomReport]:
        """
        检查所有公理。
        
        Args:
            state: 当前状态
            
        Returns:
            Dict[axiom_id -> AxiomReport]
        """
        reports = {}
        
        for axiom_id, axiom_class in self.axiom_map.items():
            try:
                # 实例化公理并检查
                axiom = axiom_class()
                violated, value, threshold = axiom.check(state)
                
                reports[axiom_id] = AxiomReport(
                    axiom_id=axiom_id,
                    violated=violated,
                    value=value,
                    threshold=threshold,
                    message=f"A{axiom_id}: value={value:.4f}, threshold={threshold:.4f}"
                )
            except Exception as e:
                reports[axiom_id] = AxiomReport(
                    axiom_id=axiom_id,
                    violated=True,
                    value=0.0,
                    threshold=0.0,
                    message=f"Error checking {axiom_id}: {e}"
                )
        
        return reports
    
    def check_a7(self, state: np.ndarray) -> List[StableStructure]:
        """
        检查 A7 稳定结构。
        
        Args:
            state: 当前状态
            
        Returns:
            找到的稳定结构列表
        """
        stable_structures = []
        
        try:
            axiom = self.axioms.A7_Stability()
            regions = axiom.detect_stable_regions(state)
            
            for reg in regions:
                stable_structures.append(StableStructure(
                    region=reg,
                    stability_score=axiom.stability_score,
                    step=getattr(axiom, 'step', 0)
                ))
        except Exception as e:
            pass
        
        return stable_structures
    
    def get_violation_summary(self, reports: Dict[str, AxiomReport]) -> Dict:
        """
        获取违背摘要。
        
        Args:
            reports: 公理报告字典
            
        Returns:
            摘要统计
        """
        total = len(reports)
        violated = sum(1 for r in reports.values() if r.violated)
        
        return {
            'total': total,
            'violated': violated,
            'violation_rate': violated / total if total > 0 else 0,
            'axiom_ids': list(reports.keys())
        }


# ============================================================
# 世界引擎 (简化版，与现有代码兼容)
# ============================================================

class WorldEngine:
    """
    差异论模拟机世界引擎。
    
    简化版，直接使用上面的适配层。
    """
    
    def __init__(self, grid_size: Tuple[int, ...] = (8, 8)):
        self.grid_size = grid_size
        self.axiom_system = AxiomSystem()
        
        self.step_count = 0
        self.state: np.ndarray = None
        self.history: List[np.ndarray] = []
        self.reports: List[StepReport] = []
        self.stable_structures: List[StableStructure] = []
    
    def init_world(self, state: Optional[np.ndarray] = None) -> None:
        """初始化世界状态"""
        self.step_count = 0
        self.history = []
        self.reports = []
        self.stable_structures = []
        
        if state is None:
            # 默认：左侧源，右侧汇
            state = np.zeros(self.grid_size, dtype=np.float32)
            state[:, :2] = 1.0
            state[:, -2:] = -1.0
        
        self.state = state.copy()
        self.history.append(self.state.copy())
    
    def step(self) -> StepReport:
        """
        执行一步模拟 (含公理约束)。
        
        Returns:
            StepReport
        """
        self.step_count += 1
        old_state = self.state.copy()
        
        # 1. 简化扩散
        new_state = self._diffuse(self.state)
        
        # 2. [A2 离散编码] 量化到 {-1, 0, 1}
        new_state = self._enforce_discretization(new_state)
        
        # 3. [A4 最小变化] 限制变化幅度
        diff = np.abs(new_state - old_state)
        max_change = 0.1
        change_mask = diff > max_change
        new_state[change_mask] = old_state[change_mask] + np.sign(new_state[change_mask]) * max_change
        
        # 4. 源汇保持
        new_state[:, :2] = 1
        new_state[:, -2:] = -1
        
        # 5. 检查公理
        axiom_reports = self.axiom_system.check_all(new_state)
        
        # 6. 检查稳定结构 (A7)
        stable_structures = self.axiom_system.check_a7(new_state)
        
        # 7. 记录
        self.state = new_state
        self.history.append(new_state.copy())
        
        step_report = StepReport(
            step=self.step_count,
            state=new_state,
            violations=axiom_reports,
            stable_structures=stable_structures
        )
        
        self.reports.append(step_report)
        
        if stable_structures:
            self.stable_structures.extend(stable_structures)
        
        return step_report
    
    def _enforce_discretization(self, state: np.ndarray) -> np.ndarray:
        """[A2 离散编码] 量化到 {-1, 0, 1}"""
        # >0.5 -> 1, <-0.5 -> -1, else -> 0
        result = np.where(state > 0.5, 1, np.where(state < -0.5, -1, 0))
        return result.astype(np.float32)
    
    def _diffuse(self, state: np.ndarray) -> np.ndarray:
        """简化扩散"""
        new = state.copy()
        for i in range(1, state.shape[0]-1):
            for j in range(1, state.shape[1]-1):
                new[i, j] = (
                    state[i-1, j] + state[i+1, j] +
                    state[i, j-1] + state[i, j+1]
                ) / 4
        return new
    
    def detect_stable_structures(self, history: list = None) -> bool:
        """[A7 稳定性] 检测最近10步是否稳定"""
        if history is None:
            history = self.history
        
        if len(history) < 10:
            return False
        
        recent = history[-10:]
        reference = recent[0]
        
        for state in recent[1:]:
            if not np.array_equal(reference, state):
                return False
        
        return True
    
    def run(self, max_steps: int = 100) -> Dict:
        """
        运行模拟。
        
        Args:
            max_steps: 最大步数
            
        Returns:
            实验结果字典
        """
        self.init_world()
        
        for step in range(max_steps):
            self.step()
        
        # 统计
        total_violations = 0
        for report in self.reports:
            for ax_id, ax_report in report.violations.items():
                if ax_report.violated:
                    total_violations += 1
        
        return {
            'steps': max_steps,
            'total_violations': total_violations,
            'stable_structures': len(self.stable_structures),
            'final_state': self.state,
            'history': self.history
        }
    
    def print_summary(self) -> None:
        """打印摘要"""
        print(f"\n{'='*50}")
        print("实验摘要")
        print(f"{'='*50}")
        print(f"总步数: {self.step_count}")
        print(f"稳定结构数: {len(self.stable_structures)}")
        
        if self.reports:
            last = self.reports[-1]
            summary = self.axiom_system.get_violation_summary(last.violations)
            print(f"最终公理违背: {summary['violated']}/{summary['total']}")
            print(f"违背率: {summary['violation_rate']*100:.1f}%")


# ============================================================
# 主测试
# ============================================================

if __name__ == '__main__':
    engine = WorldEngine((8, 8))
    result = engine.run(20)
    
    print(f"Steps: {result['steps']}")
    print(f"Violations: {result['total_violations']}")
    print(f"Stable: {result['stable_structures']}")
    
    engine.print_summary()