""""运行器：完整的时间步循环。

runner 是 Real_World 的主入口：
1. 初始化世界（加载差异/主体/通道）
2. 运行时间步循环
3. 每次迭代：转移→守恒检查→破缺检查→锁定更新→稳态判定→状态快照
4. 输出轨迹/状态/报告
"""

import copy
from typing import Dict, List, Optional

from ..core.world import World
from ..core.difference import DifferenceSource, DifferenceStatus
from ..domains.futures.futures_rules import ExchangeIntervention
from .transfer import choose_channel, transfer_difference
from .conservation import check_conservation
from .lock_in import update_lock_in
from .break_event import check_break_events
from .nearest_stable import check_nearest_stable


class Runner:
    """差异结构推理机运行器。"""

    def __init__(self, world: World, verbose: bool = True, exchange_intervention: bool = True):
        self.world = world
        self.verbose = verbose
        self._initial_total_pressure: float = 0.0
        self.exchange = ExchangeIntervention() if exchange_intervention else None

    def run(self, steps: Optional[int] = None) -> World:
        """运行推理机。

        Args:
            steps: 步数，默认使用 world.max_steps

        Returns:
            运行后的世界对象
        """
        steps = steps or self.world.max_steps
        self._initial_total_pressure = self.world.total_pressure()

        if self.verbose:
            print(f"[Runner] 开始运行: {self.world.name}, 最大步数={steps}, 初始总压力={self._initial_total_pressure:.2f}")

        for step in range(1, steps + 1):
            self.world.step()
            time = self.world.time

            if self.verbose:
                print(f"\n--- Step {time} ---")

            # 1. 通道使用量部分恢复（每步重置）
            for ch in self.world.channels.values():
                ch.reset_step()

            # 1.5 差异持续生成（recurrent 机制）
            for diff in self.world.differences.values():
                diff.tick_recurrence()

            # 2. 差异转移
            self._run_transfers(time)

            # 3. 守恒检查
            self._check_conservation(time)

            # 4. 破缺检查
            self._check_breaks(time)

            # 5. 锁定更新
            self._update_lock_in(time)

            # 5.5 交易所干预检查（持续破缺时介入）
            self._check_exchange_intervention(time)

            # 6. 状态快照（移到稳态判定之前，快照后立即写入稳态标签）
            state = self.world.snapshot_state()

            # 7. 最近稳态判定 → 写入刚创建的 state
            self._check_stable(time)

            if self.verbose:
                dom_diff = self.world.dominant_difference()
                print(f"  总压力={state.total_pressure:.2f}, 活跃差异={state.active_differences}, 稳态={state.nearest_stable_label}")
                if dom_diff:
                    print(f"  主导差异: {dom_diff.id} ({dom_diff.type}), 压力={dom_diff.pressure:.2f}")

        if self.verbose:
            print(f"\n[Runner] 运行完成: 最终步数={self.world.time}, 总破缺事件={len(self.world.events)}")

        return self.world

    def _run_transfers(self, time: int):
        """对所有活跃差异执行转移（含 Entity 承接检查）。

        流程：
        1. 差异选择通道
        2. 查找通道的承接主体
        3. 主体承接差异压力（减少 available_capacity）
        4. 主体承接不足时，差异积累
        5. 无主体或主体退出时，通道仍可转移但差异可能积累
        """
        for diff_id, diff in list(self.world.differences.items()):
            if diff.status != DifferenceStatus.ACTIVE or diff.pressure <= 0:
                continue

            channel = choose_channel(diff, list(self.world.channels.values()))
            if channel is None:
                diff.accumulate(0)
                self.world.trace.add_event(
                    time=time,
                    event_type="accumulate",
                    difference_id=diff_id,
                    amount=diff.pressure,
                    reason="无可用通道，差异继续积累",
                )
                continue

            # ---- Entity 承接检查 ----
            entities = self.world.get_channel_entities(channel.id)
            if entities:
                # 有承接主体：主体必须先承接，再通过通道转移
                total_absorbed = 0.0
                remaining_pressure = diff.pressure

                for entity in entities:
                    if not entity.can_absorb(remaining_pressure * 0.1):  # 至少能承接 10%
                        continue
                    # Entity 承接量 = min(差异压力, Entity 可用能力)
                    absorb_amount = min(remaining_pressure, entity.available_capacity * 0.5)
                    if absorb_amount <= 0:
                        continue
                    entity.absorb(absorb_amount)
                    total_absorbed += absorb_amount
                    remaining_pressure -= absorb_amount

                    self.world.trace.add_event(
                        time=time,
                        event_type="entity_absorb",
                        difference_id=diff_id,
                        channel_id=channel.id,
                        amount=absorb_amount,
                        reason=f"主体 {entity.id} 承接 {absorb_amount:.1f} 压力，剩余能力 {entity.available_capacity:.1f}",
                    )

                    if remaining_pressure <= 0.01:
                        break

                if total_absorbed > 0:
                    # 主体承接后，通过通道转移
                    transferred, remaining = transfer_difference(diff, channel, self.world.trace, time)
                    if self.verbose and transferred > 0:
                        print(f"  转移: {diff_id} -> {channel.id}, 量={transferred:.2f}, 主体承接={total_absorbed:.2f}")
                else:
                    # 主体无法承接，差异积累
                    diff.accumulate(remaining_pressure)
                    self.world.trace.add_event(
                        time=time,
                        event_type="accumulate",
                        difference_id=diff_id,
                        channel_id=channel.id,
                        amount=remaining_pressure,
                        reason=f"主体承接能力不足，差异积累 {remaining_pressure:.1f}",
                    )
                    if self.verbose:
                        print(f"  积累: {diff_id}, 主体承接不足，积累={remaining_pressure:.2f}")
            else:
                # 无承接主体：差异直接通过通道转移（老逻辑）
                transferred, remaining = transfer_difference(diff, channel, self.world.trace, time)
                if self.verbose and transferred > 0:
                    print(f"  转移: {diff_id} -> {channel.id}, 量={transferred:.2f}, 剩余={remaining:.2f}")

                if remaining > 0:
                    diff.accumulate(remaining)

    def _check_conservation(self, time: int):
        """守恒检查。"""
        passed, msg = check_conservation(
            self._initial_total_pressure,
            self.world.differences,
            self.world.trace,
            time,
        )
        if self.verbose:
            print(f"  守恒: {'通过' if passed else '失败'} - {msg}")

    def _check_breaks(self, time: int):
        """破缺检查。"""
        events = check_break_events(
            self.world.differences,
            self.world.break_thresholds,
            self.world.trace,
            time,
        )
        for event in events:
            self.world.events.append(event)
            if self.verbose:
                print(f"  破缺: {event.event_type.value} - {event.description}")

    def _update_lock_in(self, time: int):
        """更新通道锁定度。"""
        # 从轨迹中提取本次转移事件
        transfer_events = [e for e in self.world.trace.events if e.time == time and e.event_type == "transfer"]
        for te in transfer_events:
            channel = self.world.channels.get(te.channel_id)
            if channel:
                update_lock_in(channel, te.amount, self.world.trace, time)

    def _check_exchange_intervention(self, time: int):
        """交易所干预检查（持续破缺时介入）。
        
        交易所是二阶承接位置——当市场承接不足时介入，
        但介入不是消除差异，而是重组差异结构。
        """
        if self.exchange is None:
            return
        
        # 计算主体压力比例
        from ..core.entity import EntityStatus
        total_entities = len(self.world.entities)
        if total_entities == 0:
            return
        stressed = sum(
            1 for e in self.world.entities.values()
            if e.status in (EntityStatus.STRESSED, EntityStatus.MARGIN_CALLED, EntityStatus.FORCED_OUT)
        )
        stress_ratio = stressed / total_entities
        
        if self.exchange.should_intervene(self.world.total_pressure(), stress_ratio):
            # 交易所介入：先尝试提高保证金
            self.exchange.intervene_margin_increase(self.world, time, increase=0.2)
            if self.verbose:
                print(f"  交易所干预: 提高保证金，压力={self.world.total_pressure():.1f}, 主体压力比={stress_ratio:.0%}")
            
            # 如果压力持续极高，强制减仓
            if self.world.total_pressure() > self.exchange.threshold_pressure * 1.5:
                self.exchange.intervene_position_limit(self.world, time, reduction=0.3)
                if self.verbose:
                    print(f"  交易所干预: 强制减仓，极高压力={self.world.total_pressure():.1f}")

    def _check_stable(self, time: int):
        """最近稳态判定。"""
        stable_label, reason = check_nearest_stable(
            self.world.differences,
            self.world.channels,
            self.world.entities,
            self.world.states,
            self.world.trace,
            time,
        )
        if self.world.states:
            self.world.states[-1].nearest_stable_label = stable_label
            self.world.states[-1].detail["stable_reason"] = reason
        if self.verbose:
            print(f"  稳态: {stable_label} - {reason}")