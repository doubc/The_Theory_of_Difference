# -*- coding: utf-8 -*-
import numpy as np
from diffsim import RecursiveWorld


def test_baseline_is_dead_order():
    """基线: 只向外投影 -> L1 无差异源 -> flux≈0, 不再深入涌现。"""
    w = RecursiveWorld(seed=1, self_encapsulate=False)
    rep = w.run(max_layers=6)
    l1 = [r for r in rep if r["layer"] == 1]
    assert l1, "L0 应密封并产生 L1"
    assert l1[0]["autonomous_flux"] == 0.0, "基线 L1 应为死秩序(flux=0)"


def test_self_reference_is_living_order():
    """修复: 封装自身 -> L1 获得新差异源 -> flux>0, 咬合深入。"""
    w = RecursiveWorld(seed=1, self_encapsulate=True)
    rep = w.run(max_layers=6)
    l1 = [r for r in rep if r["layer"] == 1]
    assert l1, "L0 应密封并产生 L1"
    assert l1[0]["autonomous_flux"] > 0.0, "修复后 L1 应有非零自主 flux"
    assert w.emergence_depth() >= 2, "应至少咬合出 L0->L1"


def test_l0_seals():
    w = RecursiveWorld(seed=3, self_encapsulate=True)
    rep = w.run(max_layers=6)
    assert rep[0]["sealed"], "L0 应能密封"


if __name__ == "__main__":
    test_baseline_is_dead_order()
    test_self_reference_is_living_order()
    test_l0_seals()
    print("all tests passed")
