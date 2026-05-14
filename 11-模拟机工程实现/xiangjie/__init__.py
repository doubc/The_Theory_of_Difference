"""xiangjie — 象界显现链检测器

对应《象界》八章生成链：
  边界 → 界面 → 自维持 → 记忆 → 复制 → 筛选 → 功能 → 前主体态

象界是差异从底层存在进入高语义世界之间的不可省略的显现层。
每个门槛检测器判断结构是否跨越了对应的组织密度门槛。

使用方式：
  from xiangjie import XiangjieChain, XiangjieReport
  chain = XiangjieChain()
  report = chain.evaluate(structures, history, layer)
"""

from .chain import XiangjieChain, XiangjieReport, ThresholdReport

__all__ = ["XiangjieChain", "XiangjieReport", "ThresholdReport"]
