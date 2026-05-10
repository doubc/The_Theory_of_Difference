""""核心对象单元测试"""

import pytest
from Real_world.core.channel import Channel, ChannelStatus
from Real_world.core.difference import DifferenceSource, DifferenceStatus
from Real_world.core.entity import Entity, EntityStatus
from Real_world.core.event import Event, EventType
from Real_world.core.state import State
from Real_world.core.trace import Trace, TraceEvent
from Real_world.core.world import World


class TestDifferenceSource:
    def test_pressure_computation(self):
        diff = DifferenceSource(
            id="test_diff", type="inventory",
            source_node="A", target_node="B",
            magnitude=80, visibility=0.9, persistence=0.8,
        )
        assert diff.pressure == pytest.approx(80 * 0.9 * 0.8, abs=0.1)

    def test_reduce_pressure(self):
        diff = DifferenceSource(
            id="test_diff", type="inventory",
            source_node="A", target_node="B",
            magnitude=80, visibility=0.9, persistence=0.8,
        )
        diff.reduce_pressure(30)
        assert diff.pressure == pytest.approx(80 * 0.9 * 0.8 - 30, abs=0.1)
        assert diff.status == DifferenceStatus.ACTIVE

    def test_resolve_when_zero(self):
        diff = DifferenceSource(
            id="test_diff", type="inventory",
            source_node="A", target_node="B",
            magnitude=10, visibility=0.5, persistence=0.5,
        )
        diff.reduce_pressure(diff.pressure)
        assert diff.status == DifferenceStatus.RESOLVED


class TestEntity:
    def test_absorb(self):
        entity = Entity(id="test_entity", type="speculator", capacity=100, available_capacity=80)
        entity.absorb(30)
        assert entity.available_capacity == 50
        assert entity.status == EntityStatus.ACTIVE

    def test_stress_when_full(self):
        entity = Entity(id="test_entity", type="speculator", capacity=100, available_capacity=15)
        entity.absorb(10)
        assert entity.available_capacity == 5
        assert entity.status == EntityStatus.STRESSED

    def test_forced_out(self):
        entity = Entity(id="test_entity", type="speculator", capacity=100, available_capacity=5)
        entity.absorb(5)
        assert entity.status == EntityStatus.FORCED_OUT


class TestChannel:
    def test_effective_cost(self):
        ch = Channel(id="test_ch", from_type="inventory", to_type="basis",
                     base_cost=20, congestion=0.5, lock_in=0.3)
        expected = 20 + 0.5 * 10 + 0 - 0.3 * 10  # 20 + 5 - 3 = 22
        assert ch.effective_cost() == pytest.approx(expected, abs=0.1)

    def test_transfer(self):
        ch = Channel(id="test_ch", from_type="inventory", to_type="basis",
                     capacity=100)
        actual = ch.transfer(40)
        assert actual == 40
        assert ch.used_capacity == 40

    def test_partial_transfer(self):
        ch = Channel(id="test_ch", from_type="inventory", to_type="basis",
                     capacity=100, used_capacity=90)
        actual = ch.transfer(20)
        assert actual == 10  # only 10 remaining


class TestWorld:
    def test_create_and_add(self):
        world = World(name="test_world")
        diff = DifferenceSource(id="d1", type="inventory", source_node="A", target_node="B")
        entity = Entity(id="e1", type="speculator")
        channel = Channel(id="c1", from_type="inventory", to_type="basis")

        world.add_difference(diff)
        world.add_entity(entity)
        world.add_channel(channel)

        assert len(world.differences) == 1
        assert len(world.entities) == 1
        assert len(world.channels) == 1

    def test_total_pressure(self):
        world = World(name="test_world")
        d1 = DifferenceSource(id="d1", type="inventory", source_node="A", target_node="B",
                              magnitude=50, visibility=0.8, persistence=0.7)
        d2 = DifferenceSource(id="d2", type="expectation", source_node="C", target_node="D",
                              magnitude=30, visibility=0.9, persistence=0.6)
        world.add_difference(d1)
        world.add_difference(d2)
        expected = d1.pressure + d2.pressure
        assert world.total_pressure() == pytest.approx(expected, abs=0.1)
