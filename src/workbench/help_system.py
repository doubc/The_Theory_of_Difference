"""
快速帮助系统 — 内置使用指南和术语解释

功能：
  - 浮动帮助按钮
  - 术语工具提示
  - 快速入门指南
  - 快捷键说明
"""

from __future__ import annotations
import streamlit as st


# ─── 术语字典 ──────────────────────────────────────────────

GLOSSARY = {
    "Zone": "关键区 — 多个极值点聚集形成的价位区间，有共同的反差驱动",
    "Structure": "结构 — Zone + 多个 Cycle 的组合，携带运动态和投影觉知",
    "Cycle": "循环 — 价格围绕 Zone 的一次完整试探过程",
    "Motion": "运动态 — 结构的运动状态，包括阶段、通量、运动类型",
    "Flux": "通量 — 守恒通量，衡量结构内部差异的释放/压缩状态",
    "Phase": "阶段 — 结构所处的阶段（形成/稳态/突破/确认/回落）",
    "Pivot": "极值点 — 价格序列中的局部极大/极小值",
    "Segment": "段 — 两个相邻极值点之间的连线",
    "DTW": "动态时间规整 — 用于衡量两个时间序列的相似度",
    "Invariant": "不变量 — 从价格结构中提取的结构性特征",
    "Blind": "盲区 — 高压缩结构，价格在 Zone 附近密集试探",
    "Breakout": "突破 — 价格脱离 Zone 的运动",
    "Confirmation": "确认 — 突破后的确认阶段",
    "Quality": "质量分 — 结构的质量评估分数（A/B/C/D 层）",
    "Departure": "离稳态 — 衡量结构正在离开均衡态的程度",
    "Resonance": "共振 — 多个品种同时出现相似结构",
    "Projection": "投影觉知 — 结构对未来价格走势的预测能力",
    "Conservation": "守恒 — 结构内部差异的守恒性质",
}

# ─── 快速入门指南 ──────────────────────────────────────────

QUICK_START = """
## 🚀 快速入门

### 第一步：选择品种
在左侧栏选择要分析的期货品种，支持搜索和收藏。

### 第二步：查看仪表盘
仪表盘展示品种概览、快速入口和使用指南。

### 第三步：全市场扫描
点击「📡 今日扫描」Tab，执行全市场扫描，查看：
- 🔴 破缺中 — 价格正在脱离 Zone
- 🟢 确认中 — 突破已确认
- 🔵 形成中 — 结构正在形成
- ⚪ 稳态 — 价格在 Zone 内运行

### 第四步：查看信号
点击任何合约查看详情，包括：
- 信号类型（突破确认/假突破/回踩确认）
- 入场价、止损价、目标价
- 盈亏比和仓位建议

### 第五步：生成简报
点击「📋 每日简报」Tab，一键生成今日市场结构摘要，可导出为 Markdown。

### 第六步：复盘记录
在「📝 复盘日志」Tab 记录交易想法和复盘笔记。

---

## 📊 核心概念

| 概念 | 说明 |
|------|------|
| Zone | 关键区 — 价格反复试探的区间 |
| 结构 | Zone + 试探次数 + 运动态 |
| 通量 | 结构内部差异的度量 |
| 质量分 | A(优) > B(良) > C(中) > D(差) |
| 离稳态 | 结构离开均衡态的程度 |

---

## ⌨️ 快捷键

| 快捷键 | 功能 |
|--------|------|
| `R` | 刷新数据 |
| `F` | 收藏当前品种 |
| `S` | 跳转到扫描页 |
| `B` | 跳转到简报页 |
"""


def render_help_button():
    """渲染浮动帮助按钮"""
    st.markdown("""
    <style>
    .help-button {
        position: fixed;
        bottom: 20px;
        right: 20px;
        width: 50px;
        height: 50px;
        border-radius: 50%;
        background: linear-gradient(135deg, #1d3557 0%, #457b9d 100%);
        color: #64ffda;
        font-size: 1.5em;
        display: flex;
        align-items: center;
        justify-content: center;
        cursor: pointer;
        box-shadow: 0 4px 12px rgba(0,0,0,0.3);
        z-index: 1000;
        transition: all 0.2s;
        border: 2px solid #64ffda;
    }
    .help-button:hover {
        transform: scale(1.1);
        box-shadow: 0 6px 16px rgba(100, 255, 218, 0.3);
    }
    </style>
    <div class="help-button" onclick="document.getElementById('help-modal').style.display='block'">
        ?
    </div>
    """, unsafe_allow_html=True)


def render_help_modal():
    """渲染帮助模态框"""
    st.markdown("""
    <div id="help-modal" style="display:none;position:fixed;top:0;left:0;width:100%;height:100%;
         background:rgba(0,0,0,0.8);z-index:1001;padding:40px;overflow-y:auto">
        <div style="max-width:800px;margin:0 auto;background:#0a192f;border-radius:12px;
                    padding:30px;border:1px solid #233554">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:20px">
                <h2 style="color:#ccd6f6;margin:0">📖 使用指南</h2>
                <button onclick="document.getElementById('help-modal').style.display='none'"
                        style="background:none;border:none;color:#64ffda;font-size:1.5em;cursor:pointer">
                    ✕
                </button>
            </div>
            <div style="color:#8892b0;font-size:0.95em;line-height:1.8">
    """, unsafe_allow_html=True)

    st.markdown(QUICK_START)

    st.markdown("""
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)


def render_glossary_tooltip(term: str) -> str:
    """为术语添加工具提示"""
    if term in GLOSSARY:
        return f'<span title="{GLOSSARY[term]}" style="border-bottom:1px dotted #64ffda;cursor:help">{term}</span>'
    return term


def render_quick_help(section: str = "general"):
    """渲染上下文相关的快速帮助"""
    help_texts = {
        "general": """
        **💡 使用提示**
        - 在左侧栏选择品种开始分析
        - 点击「📡 今日扫描」查看全市场机会
        - 点击「📋 每日简报」生成今日摘要
        - 收藏常用品种方便快速访问
        """,
        "scan": """
        **📡 扫描说明**
        - 🔴 破缺 — 价格正在脱离 Zone，可能是趋势开始
        - 🟢 确认 — 突破已确认，趋势延续
        - 🔵 形成 — 结构正在形成，关注后续发展
        - ⚪ 稳态 — 价格在 Zone 内运行，高抛低吸区间
        - 通量 > 0 表示差异释放，< 0 表示差异压缩
        """,
        "signal": """
        **📢 信号说明**
        - ✅ 突破确认 — 价格突破 Zone 并站稳
        - ⚠️ 假突破 — 突破后快速回撤，可能是陷阱
        - 🔄 回踩确认 — 突破后回踩 Zone 边界确认
        - 💀 结构失效 — 价格回到 Zone 内部，突破失败
        - 盈亏比 > 2 为优质信号
        """,
        "quality": """
        **🔬 质量评分**
        - A 层 (≥80分) — 优质结构，信号可靠
        - B 层 (≥60分) — 良好结构，值得关注
        - C 层 (≥40分) — 一般结构，谨慎参考
        - D 层 (<40分) — 较差结构，不建议交易
        """,
    }

    text = help_texts.get(section, help_texts["general"])
    st.info(text)


def render_keyboard_shortcuts():
    """渲染快捷键说明"""
    st.markdown("""
    **⌨️ 快捷键**
    - `R` — 刷新数据
    - `F` — 收藏/取消收藏
    - `S` — 跳转到扫描页
    - `B` — 跳转到简报页
    - `H` — 显示/隐藏帮助
    """)
