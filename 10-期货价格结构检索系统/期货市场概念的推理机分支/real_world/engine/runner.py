""""运行器：完整的时间步循环（Phase 2）。

runner 是 Real_World 的主入口：
1. 初始化世界（加载差异/主体/通道）
2. 运行时间步循环
3. 每次迭代：转移+变形→反馈→守恒检查→破缺检查→锁定更新→交易所干预→状态快照→稳态判定
4. 输出轨迹/状态/报告

Phase 2 新增：
- 变形链：差异经通道转移后，按变形规则生成新类型差异（递归，最大深度5）
- 反馈循环：承接体承压后生成新的反馈差异，注入世界
- 干预多动作：三种干预（降低差异生成率、扩大通道容量、释放承接力）+ 副作用差异
"""

import copy
from typing import Dict, List, Optional

from ..core.world import World
from ..core.difference import DifferenceSource, DifferenceStatus
from ..core.entity import Entity, EntityStatus
from ..core.intervention import Intervention
from ..domains.futures.futures_rules import ExchangeIntervention
from .intervention_engine import InterventionEngine
from .transfer import choose_channel, transfer_difference, transfer_and_transform
from .conservation import check_conservation, reset_conservation
from .lock_in import update_lock_in
from .break_event import check_break_events
from .nearest_stable import check_nearest_stable

# 变形链最大深度，防止无限循环
MAX_CHAIN_DEPTH = 5

# Phase 3: 每步全局反馈差异数量上限
MAX_FEEDBACK_PER_STEP = 10


class Runner:
    """差异结构推理机运行器。"""

    def __init__(self, world: World, verbose: bool = True, exchange_intervention: bool = True):
        self.world = world
        self.verbose = verbose
        self._initial_total_pressure: float = 0.0
        self.exchange = ExchangeIntervention() if exchange_intervention else None
        self.intervention_engine = InterventionEngine(world)

    def run(self, steps: Optional[int] = None) -> World:
        """运行推理机。"""
        steps = steps or self.world.max_steps
        self._initial_total_pressure = self.world.total_pressure()
        reset_conservation()

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
                old_pressure = diff.pressure
                diff.tick_recurrence()
                if diff.pressure - old_pressure > 0.01:
                    self.world.trace.add_event(
                        time=time,
                        event_type="recurrent_generate",
                        difference_id=diff.id,
                        amount=diff.pressure - old_pressure,
                        reason=f"recurrent 生成 {diff.pressure - old_pressure:.2f} 压力",
                    )

            # 2. 差异转移 + 变形链 + 反馈循环
            self._run_transfers_with_chain(time)

            # 3. 破缺检查（在守恒检查之前，这样守恒可以看到本步的破缺释放）
            self._check_breaks(time)

            # 4. 守恒检查
            self._check_conservation(time)

            # 5. 锁定更新
            self._update_lock_in(time)

            # 5.5 交易所干预检查（三重干预 + 副作用差异）
            self._check_exchange_intervention(time)

            # 5.6 制度边界干预检查（Exp 009）
            self._check_intervention(time)

            # 6. 状态快照
            state = self.world.snapshot_state()

            # 7. 最近稳态判定
            self._check_stable(time)

            if self.verbose:
                dom_diff = self.world.dominant_difference()
                print(f"  总压力={state.total_pressure:.2f}, 活跃差异={state.active_differences}, 稳态={state.nearest_stable_label}")
                if dom_diff:
                    print(f"  主导差异: {dom_diff.id} ({dom_diff.type}), 压力={dom_diff.pressure:.2f}")

        if self.verbose:
            print(f"\n[Runner] 运行完成: 最终步数={self.world.time}, 总破缺事件={len(self.world.events)}")

        return self.world

    def _run_transfers_with_chain(self, time: int):
        """差异转移 + 变形链 + 反馈循环（Phase 3 核心）。

        流程：
        1. 取当前所有活跃差异
        2. 对每个差异：选择通道 → 执行转移 → 检查变形
        3. 变形产生的新差异进入下一轮（队列）
        4. 最多执行 MAX_CHAIN_DEPTH 轮（防止无限循环）
        5. 反馈差异仅在深度0生成（防止递归爆炸）
        6. 反馈差异可在深度1+继续转移/变形，但不触发新反馈

        Phase 3 改进（反馈深度约束）：
        - 衰减约束：反馈 magnitude 应用 FEEDBACK_DECAY（50%衰减）
        - 类型冷却：同主体同类型每步最多1次（Entity._feedback_cooldown）
        - 全局上限：每步最多 MAX_FEEDBACK_PER_STEP 个反馈差异
        """
        # 初始差异列表
        pending = [
            (diff_id, diff)
            for diff_id, diff in self.world.differences.items()
            if diff.status == DifferenceStatus.ACTIVE and diff.pressure > 0
        ]

        chain_depth = 0
        while pending and chain_depth < MAX_CHAIN_DEPTH:
            next_round = []
            feedback_diffs = []

            for diff_id, diff in pending:
                if diff.status != DifferenceStatus.ACTIVE or diff.pressure <= 0:
                    continue

                # 选择通道
                channel = choose_channel(diff, list(self.world.channels.values()))
                if channel is None:
                    # 无可用通道：压力保持不动，不调用 accumulate（避免自增）
                    self.world.trace.add_event(
                        time=time,
                        event_type="accumulate",
                        difference_id=diff_id,
                        amount=0,
                        reason=f"无可用通道，差异压力保持 {diff.pressure:.1f}（深度 {chain_depth}）",
                    )
                    continue

                # ---- Entity 承接检查 ----
                entities = self.world.get_channel_entities(channel.id)
                if entities:
                    total_absorbed = 0.0
                    remaining_pressure = diff.pressure

                    for entity in entities:
                        if not entity.can_absorb(remaining_pressure * 0.1):
                            continue
                        absorb_amount = min(remaining_pressure, entity.available_capacity * 0.5)
                        if absorb_amount <= 0:
                            continue
                        entity.absorb(absorb_amount)
                        total_absorbed += absorb_amount
                        remaining_pressure -= absorb_amount
                        diff.reduce_pressure(absorb_amount)  # 同步减少差异压力

                        self.world.trace.add_event(
                            time=time,
                            event_type="entity_absorb",
                            difference_id=diff_id,
                            channel_id=channel.id,
                            amount=absorb_amount,
                            reason=f"主体 {entity.id} 承接 {absorb_amount:.1f}，剩余能力 {entity.available_capacity:.1f}（深度 {chain_depth}）",
                        )

                        # 收集反馈差异（仅在深度0生成，防止递归爆炸）
                        if chain_depth == 0:
                            fb = entity.generate_feedback_differences(absorb_amount, time)
                            feedback_diffs.extend(fb)

                        if remaining_pressure <= 0.01:
                            break

                    if total_absorbed > 0:
                        # 执行转移 + 变形
                        transferred, remaining, transform_info = transfer_and_transform(
                            diff, channel, self.world.trace, time, chain_depth
                        )
                        if self.verbose and transferred > 0:
                            print(f"  转移: {diff_id} -> {channel.id}, 量={transferred:.2f}, 深度={chain_depth}")

                        # 变形差异进入下一轮
                        if transform_info:
                            transform_diff = DifferenceSource.from_dict(transform_info)
                            self.world.add_difference(transform_diff)
                            next_round.append((transform_diff.id, transform_diff))
                            if self.verbose:
                                print(f"  变形: {diff.type} → {transform_info['type']}, 压力={transform_info['pressure']:.2f}")

                    else:
                        # 主体无法承接：差异压力保持不动
                        self.world.trace.add_event(
                            time=time,
                            event_type="accumulate",
                            difference_id=diff_id,
                            channel_id=channel.id,
                            amount=0,
                            reason=f"主体承接能力不足，差异压力保持 {diff.pressure:.1f}（深度 {chain_depth}）",
                        )
                else:
                    # 无承接主体：直接转移 + 变形
                    transferred, remaining, transform_info = transfer_and_transform(
                        diff, channel, self.world.trace, time, chain_depth
                    )
                    if self.verbose and transferred > 0:
                        print(f"  转移: {diff_id} -> {channel.id}, 量={transferred:.2f}, 深度={chain_depth}")

                    if transform_info:
                        transform_diff = DifferenceSource.from_dict(transform_info)
                        self.world.add_difference(transform_diff)
                        next_round.append((transform_diff.id, transform_diff))
                        if self.verbose:
                            print(f"  变形: {diff.type} → {transform_info['type']}, 压力={transform_info['pressure']:.2f}")

                    if remaining > 0:
                        # 剩余压力保持，不自增
                        pass

            # 注入反馈差异到世界（Phase 3: 应用全局上限）
            feedback_injected = 0
            for fb in feedback_diffs:
                if feedback_injected >= MAX_FEEDBACK_PER_STEP:
                    if self.verbose:
                        print(f"  反馈: 达到全局上限 {MAX_FEEDBACK_PER_STEP}，停止注入新反馈")
                    break
                fb_diff = DifferenceSource.from_dict(fb)
                self.world.add_difference(fb_diff)
                next_round.append((fb_diff.id, fb_diff))
                feedback_injected += 1
                if self.verbose:
                    print(f"  反馈: {fb['type']} 差异从 {fb['source_node']} 生成, 压力={fb['magnitude']:.2f} ({feedback_injected}/{MAX_FEEDBACK_PER_STEP})")

            pending = next_round
            chain_depth += 1

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
        transfer_events = [e for e in self.world.trace.events if e.time == time and e.event_type == "transfer"]
        for te in transfer_events:
            channel = self.world.channels.get(te.channel_id)
            if channel:
                update_lock_in(channel, te.amount, self.world.trace, time)

    def _check_exchange_intervention(self, time: int):
        """交易所干预检查（Phase 2：三重干预 + 副作用差异）。

        交易所是二阶承接位置——当市场承接不足时介入，
        但介入不是消除差异，而是重组差异结构。
        """
        if self.exchange is None:
            return

        # 计算主体压力比例
        total_entities = len(self.world.entities)
        if total_entities == 0:
            return
        stressed = sum(
            1 for e in self.world.entities.values()
            if e.status in (EntityStatus.STRESSED, EntityStatus.MARGIN_CALLED, EntityStatus.FORCED_OUT)
        )
        stress_ratio = stressed / total_entities

        if not self.exchange.should_intervene(self.world.total_pressure(), stress_ratio):
            return

        # 选择干预动作组合
        actions = self.exchange.choose_interventions(self.world)
        side_effects = []

        for action in actions:
            if action == "reduce_recurrent":
                se = self.exchange.intervene_reduce_recurrent(self.world, time, reduction=0.3)
                if se:
                    side_effects.append(se)
                if self.verbose:
                    print(f"  交易所干预: 降低差异生成率，压力={self.world.total_pressure():.1f}")

            elif action == "expand_channel":
                se = self.exchange.intervene_expand_channel(self.world, time, expansion=0.5)
                if se:
                    side_effects.append(se)
                if self.verbose:
                    print(f"  交易所干预: 扩大通道容量，压力={self.world.total_pressure():.1f}")

            elif action == "release_entity":
                se = self.exchange.intervene_release_entity(self.world, time, entity_type="speculator", release=0.3)
                if se:
                    side_effects.append(se)
                if self.verbose:
                    print(f"  交易所干预: 释放承接力，压力={self.world.total_pressure():.1f}")

        # 注入副作用差异到世界
        for se in side_effects:
            se_diff = DifferenceSource.from_dict(se)
            self.world.add_difference(se_diff)

    def _check_intervention(self, time: int):
        """制度边界干预检查（Exp 009）。
        
        干预改变系统的条件结构，迫使系统在新的约束下重新组织。
        这是差异论"最近稳态"概念的实验验证。
        """
        # 首先将 world.interventions 注册到干预引擎
        for inv in self.world.interventions:
            if inv not in self.intervention_engine.interventions:
                self.intervention_engine.add_intervention(inv)
        
        # 检查并执行当前时间步的干预
        result = self.intervention_engine.check_and_execute(time)
        if result and result.success:
            if self.verbose:
                print(f"  [干预] {result.message}")
                print(f"    压力变化: {result.pressure_change:+.2f} ({result.pressure_change_rate*100:+.1f}%)")
                print(f"    稳态改善: {'是' if result.stability_improved else '否'}")

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
