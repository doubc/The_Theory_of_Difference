"""干预执行引擎。

职责：
1. 在指定时间步执行干预
2. 记录干预前后状态变化
3. 评估干预效果
"""

from typing import Dict, List, Optional, Any

from ..core.world import World
from ..core.intervention import Intervention, InterventionResult, InterventionType


class InterventionEngine:
    """干预执行引擎。"""
    
    def __init__(self, world: World):
        self.world = world
        self.interventions: List[Intervention] = []
        self.executed: List[InterventionResult] = []
    
    def add_intervention(self, intervention: Intervention):
        """注册干预事件。"""
        self.interventions.append(intervention)
    
    def check_and_execute(self, time: int) -> Optional[InterventionResult]:
        """检查并执行当前时间步的干预。"""
        for inv in self.interventions:
            if inv.time == time and inv not in [r.intervention for r in self.executed]:
                result = self._execute(inv)
                self.executed.append(result)
                return result
        return None
    
    def _capture_state(self) -> Dict[str, Any]:
        """捕获当前系统状态快照。"""
        return {
            "total_pressure": self.world.total_pressure(),
            "active_differences": len(self.world.get_active_differences()),
            "active_entities": len([e for e in self.world.entities.values() if e.available_capacity > 0]),
            "dominant_type": self.world.dominant_difference().type if self.world.dominant_difference() else None,
        }
    
    def _execute(self, intervention: Intervention) -> InterventionResult:
        """执行具体干预。"""
        # 记录干预前状态
        intervention.pre_state = self._capture_state()
        pre_pressure = intervention.pre_state["total_pressure"]
        
        try:
            if intervention.type == InterventionType.MARGIN_ADJUST:
                self._apply_margin_adjust(intervention)
            elif intervention.type == InterventionType.CHANNEL_RESTRICT:
                self._apply_channel_restrict(intervention)
            elif intervention.type == InterventionType.COMPOSITE:
                self._apply_composite(intervention)
            else:
                return InterventionResult(
                    intervention=intervention,
                    success=False,
                    message=f"未知干预类型: {intervention.type}"
                )
            
            # 记录干预后状态
            intervention.post_state = self._capture_state()
            post_pressure = intervention.post_state["total_pressure"]
            
            # 计算效果
            pressure_change = post_pressure - pre_pressure
            pressure_change_rate = (pressure_change / pre_pressure) if pre_pressure > 0 else 0
            stability_improved = post_pressure < pre_pressure * 0.9  # 压力降低10%视为改善
            
            # 记录干预事件到轨迹
            self.world.trace.add_event(
                time=intervention.time,
                event_type="intervention",
                difference_id="intervention",
                reason=f"干预执行: {intervention.description}, 压力变化={pressure_change:+.2f}",
                amount=pressure_change,
            )
            
            return InterventionResult(
                intervention=intervention,
                success=True,
                pressure_change=pressure_change,
                pressure_change_rate=pressure_change_rate,
                stability_improved=stability_improved,
                message=f"干预成功: {intervention.description}"
            )
            
        except Exception as e:
            return InterventionResult(
                intervention=intervention,
                success=False,
                message=f"干预失败: {str(e)}"
            )
    
    def _apply_margin_adjust(self, inv: Intervention):
        """调整保证金比例（降低杠杆）。"""
        target_id = inv.target
        if target_id not in self.world.entities:
            raise ValueError(f"目标主体不存在: {target_id}")
        
        entity = self.world.entities[target_id]
        old_leverage = entity.leverage
        
        # 获取新杠杆值（默认降至原来的50%）
        new_leverage = inv.params.get("leverage", old_leverage * 0.5)
        new_leverage = max(1.0, new_leverage)  # 最低1倍杠杆
        
        # 计算保证金占用变化
        # 杠杆降低 = 保证金比例提高 = 可用承接能力下降
        if old_leverage > 0 and new_leverage < old_leverage:
            # 已用容量需要更多保证金
            margin_impact = entity.used_capacity * (old_leverage / new_leverage - 1) * 0.1
            entity.available_capacity = max(0, entity.available_capacity - margin_impact)
        
        entity.leverage = new_leverage
        
        inv.description = f"{target_id} 杠杆 {old_leverage:.1f}x → {new_leverage:.1f}x"
    
    def _apply_channel_restrict(self, inv: Intervention):
        """限制通道容量。"""
        target_id = inv.target
        if target_id not in self.world.channels:
            raise ValueError(f"目标通道不存在: {target_id}")
        
        channel = self.world.channels[target_id]
        old_capacity = channel.capacity
        
        # 获取新容量（默认降至原来的50%）
        new_capacity = inv.params.get("capacity", old_capacity * 0.5)
        new_capacity = max(10, new_capacity)  # 最低保留10容量
        
        channel.capacity = new_capacity
        
        # 增加拥堵度
        congestion_increase = inv.params.get("congestion_increase", 0.3)
        channel.congestion = min(1.0, channel.congestion + congestion_increase)
        
        inv.description = f"{target_id} 容量 {old_capacity:.0f} → {new_capacity:.0f}, 拥堵度 +{congestion_increase}"
    
    def _apply_composite(self, inv: Intervention):
        """综合干预：同时调整多个参数。"""
        descriptions = []
        
        # 全局杠杆调整
        if "global_leverage_multiplier" in inv.params:
            multiplier = inv.params["global_leverage_multiplier"]
            for entity in self.world.entities.values():
                old_lev = entity.leverage
                entity.leverage = max(1.0, entity.leverage * multiplier)
                # 同步调整可用容量
                if multiplier < 1:
                    entity.available_capacity *= multiplier
            descriptions.append(f"全局杠杆×{multiplier}")
        
        # 全局容量调整
        if "global_capacity_multiplier" in inv.params:
            multiplier = inv.params["global_capacity_multiplier"]
            for channel in self.world.channels.values():
                old_cap = channel.capacity
                channel.capacity = max(10, channel.capacity * multiplier)
            descriptions.append(f"全局容量×{multiplier}")
        
        # 破缺阈值调整
        if "threshold_multiplier" in inv.params:
            multiplier = inv.params["threshold_multiplier"]
            for key in self.world.break_thresholds:
                self.world.break_thresholds[key] *= multiplier
            descriptions.append(f"阈值×{multiplier}")
        
        inv.description = "综合干预: " + ", ".join(descriptions) if descriptions else "综合干预"
