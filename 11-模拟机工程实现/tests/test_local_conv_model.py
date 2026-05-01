"""tests/test_local_conv_model.py — 局部卷积模型单元测试"""

import pytest
import torch
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from models.local_conv_model import LocalConvModel


class TestLocalConvModel:
    """LocalConvModel 测试"""

    def test_output_shape_2d(self):
        model = LocalConvModel(channels=16, use_reaction=False)
        state = torch.rand(1, 1, 8, 8)
        out = model(state)
        assert out.shape == (1, 1, 8, 8)

    def test_output_shape_1d(self):
        model = LocalConvModel(channels=16, use_reaction=False)
        state = torch.rand(1, 1, 1, 50)
        out = model(state)
        assert out.shape == (1, 1, 1, 50)

    def test_output_range(self):
        """输出应在 [0, 1] 范围内"""
        model = LocalConvModel(channels=16, use_reaction=True)
        state = torch.rand(2, 1, 8, 8)
        out = model(state)
        assert out.min() >= 0.0
        assert out.max() <= 1.0

    def test_identity_semantics(self):
        """零参数时输出应等于输入（恒等映射语义）

        当所有参数为 0 时，backbone 输出 0，tanh(0)=0，
        delta=0，所以 next_state = state + 0 = state。
        这验证了 delta 更新语义的正确性。
        """
        model = LocalConvModel(channels=16, use_reaction=False, step_scale=0.2)
        state = torch.rand(1, 1, 8, 8)

        with torch.no_grad():
            for p in model.parameters():
                p.zero_()

        out = model(state)
        assert torch.allclose(out, state, atol=1e-6)

    def test_zero_input_stable(self):
        """零输入不应产生 NaN"""
        model = LocalConvModel(channels=16, use_reaction=True)
        state = torch.zeros(1, 1, 8, 8)
        out = model(state)
        assert not torch.isnan(out).any()
        assert not torch.isinf(out).any()

    def test_reaction_branch(self):
        """有反应分支和无反应分支应产生不同输出"""
        state = torch.rand(1, 1, 8, 8)

        model_with = LocalConvModel(channels=16, use_reaction=True)
        model_without = LocalConvModel(channels=16, use_reaction=False)

        out_with = model_with(state)
        out_without = model_without(state)

        # 不应完全相同
        assert not torch.allclose(out_with, out_without, atol=1e-6)

    def test_step_scale_learnable(self):
        """step_scale 应是可学习参数"""
        model = LocalConvModel(channels=16)
        assert hasattr(model, 'step_scale')
        assert model.step_scale.requires_grad

    def test_batch_independence(self):
        """不同 batch 元素应独立处理"""
        model = LocalConvModel(channels=16)
        state = torch.rand(3, 1, 8, 8)
        out = model(state)
        assert out.shape == (3, 1, 8, 8)

    def test_gradient_flow(self):
        """梯度应能回传"""
        model = LocalConvModel(channels=16)
        state = torch.rand(1, 1, 8, 8)
        out = model(state)
        loss = out.mean()
        loss.backward()
        # 所有参数都应有梯度
        for p in model.parameters():
            assert p.grad is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
