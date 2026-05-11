"""
coarse_grain.py — 粗粒化映射

将 L0 稳定结构映射到 L1 抽象层。
对应《差异即世界》中"层级"机制：结构获得递归展开的能力。

映射逻辑：
1. 从 StableStructure.mask 提取稳定区域
2. 按 block_size 分块
3. 每块取均值 → L1 状态空间
4. L1 守恒量 = 各块激活量之和
"""

from typing import Tuple, Optional
import torch
import torch.nn.functional as F


def coarse_grain_state(
    state: torch.Tensor,
    mask: torch.Tensor,
    block_size: int = 4,
) -> Tuple[torch.Tensor, torch.Tensor]:
    """将 L0 状态粗粒化为 L1 状态

    Args:
        state: L0 状态 (B, C, H, W)
        mask: 稳定区域掩码 (B, C, H, W) 或 (H, W)
        block_size: 分块大小

    Returns:
        l1_state: 粗粒化后的状态 (B, C, H', W')
        l1_mask: 粗粒化后的掩码 (B, C, H', W')
    """
    # 确保 mask 与 state 形状一致
    if mask.dim() == 2:
        mask = mask.unsqueeze(0).unsqueeze(0)
    elif mask.dim() == 3:
        mask = mask.unsqueeze(0)

    mask = mask.expand_as(state).float()

    # 应用掩码
    masked_state = state * mask

    # 分块池化
    b, c, h, w = masked_state.shape
    # 计算填充后的尺寸
    pad_h = (block_size - h % block_size) % block_size
    pad_w = (block_size - w % block_size) % block_size

    if pad_h > 0 or pad_w > 0:
        masked_state = F.pad(masked_state, (0, pad_w, 0, pad_h))
        mask = F.pad(mask, (0, pad_w, 0, pad_h))

    # 分块均值池化
    bh = (h + pad_h) // block_size
    bw = (w + pad_w) // block_size

    l1_state = masked_state.reshape(b, c, bh, block_size, bw, block_size)
    l1_state = l1_state.mean(dim=(3, 5))

    l1_mask = mask.reshape(b, c, bh, block_size, bw, block_size)
    l1_mask = l1_mask.mean(dim=(3, 5))
    # 掩码二值化：块内超过一半像素被标记则该块被标记
    l1_mask = (l1_mask > 0.5).float()

    return l1_state, l1_mask


def coarse_grain_measure_invariant(l1_state: torch.Tensor, l1_mask: torch.Tensor) -> torch.Tensor:
    """L1 层的守恒量：被标记区域的总激活量"""
    return (l1_state * l1_mask).sum(dim=(-1, -2), keepdim=True)


def compute_block_boundary_map(l1_mask: torch.Tensor) -> torch.Tensor:
    """计算 L1 块级别的边界图

    边界 = 标记块中至少有一个非标记邻居的块
    """
    mask = l1_mask.float()
    # 填充一圈零
    padded = F.pad(mask, (1, 1, 1, 1), mode='constant', value=0)
    # 4-邻域检查
    up = padded[:, :, :-2, 1:-1]
    down = padded[:, :, 2:, 1:-1]
    left = padded[:, :, 1:-1, :-2]
    right = padded[:, :, 1:-1, 2:]

    # 自身在 mask 内，且至少有一个邻居不在 mask 内
    min_neighbor = torch.min(torch.min(up, down), torch.min(left, right))
    boundary = mask * (1.0 - min_neighbor)
    return boundary


def compute_block_turnover(
    history: list,
    l1_mask: torch.Tensor,
    block_size: int = 4,
) -> float:
    """计算 L1 块级别的物质周转率

    周转率 = 历史中 L1 块状态的时间标准差的均值
    """
    if len(history) < 2:
        return 0.0

    # 对历史中的每个状态做粗粒化
    l1_history = []
    for state in history[-16:]:
        l1_s, _ = coarse_grain_state(state, l1_mask.squeeze(0).squeeze(0), block_size)
        l1_history.append(l1_s)

    stacked = torch.stack(l1_history, dim=0)  # (T, B, C, H', W')
    turnover = float(stacked.std(dim=0).mean())
    return turnover
