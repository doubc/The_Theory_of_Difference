"""
主题管理器 — 支持暗色/亮色主题切换
"""

from __future__ import annotations
import streamlit as st


# ─── 主题定义 ──────────────────────────────────────────────

THEMES = {
    "dark": {
        "name": "🌙 暗色",
        "bg_primary": "#0a192f",
        "bg_secondary": "#112240",
        "bg_card": "#1a1a2e",
        "text_primary": "#ccd6f6",
        "text_secondary": "#8892b0",
        "accent": "#64ffda",
        "accent_hover": "#4cd6b0",
        "border": "#233554",
        "success": "#4caf50",
        "warning": "#ff9800",
        "error": "#ef5350",
        "info": "#2196f3",
    },
    "light": {
        "name": "☀️ 亮色",
        "bg_primary": "#ffffff",
        "bg_secondary": "#f8f9fa",
        "bg_card": "#ffffff",
        "text_primary": "#0d1b2a",
        "text_secondary": "#495057",
        "accent": "#1d3557",
        "accent_hover": "#457b9d",
        "border": "#dee2e6",
        "success": "#2e7d32",
        "warning": "#f57c00",
        "error": "#c62828",
        "info": "#1565c0",
    },
}


def get_current_theme() -> dict:
    """获取当前主题配置"""
    theme_name = st.session_state.get("theme", "dark")
    return THEMES.get(theme_name, THEMES["dark"])


def render_theme_toggle():
    """渲染主题切换按钮"""
    current = st.session_state.get("theme", "dark")
    new_theme = "light" if current == "dark" else "dark"

    if st.button(THEMES[new_theme]["name"], key="theme_toggle", use_container_width=True):
        st.session_state["theme"] = new_theme
        st.rerun()


def get_theme_css(theme: dict) -> str:
    """生成主题 CSS"""
    return f"""
    <style>
        .stApp {{
            background-color: {theme['bg_primary']};
            color: {theme['text_primary']};
        }}

        [data-testid="stSidebar"] {{
            background: linear-gradient(180deg, {theme['bg_primary']} 0%, {theme['bg_secondary']} 100%);
        }}

        .stTabs [data-baseweb="tab-list"] {{
            background: {theme['bg_primary']};
        }}

        .stTabs [aria-selected="true"] {{
            background: {theme['bg_secondary']} !important;
            color: {theme['accent']} !important;
        }}

        [data-testid="stMetric"] {{
            background: linear-gradient(135deg, {theme['bg_card']} 0%, {theme['bg_secondary']} 100%);
            border-left: 4px solid {theme['accent']};
        }}

        .stButton > button {{
            border-color: {theme['border']};
        }}

        .stButton > button:hover {{
            border-color: {theme['accent']};
            box-shadow: 0 4px 12px rgba(100, 255, 218, 0.15);
        }}

        .structure-card {{
            background: linear-gradient(135deg, {theme['bg_secondary']} 0%, {theme['bg_card']} 100%);
            border-left-color: {theme['accent']};
            color: {theme['text_primary']};
        }}

        .nav-group-title {{
            color: {theme['accent']};
        }}
    </style>
    """
