"""统一设计 token: 颜色 / 字体 / plotly 模板 / 全局 CSS。

所有 tab 与 plotly 图表都应从这里取色, 避免散落硬编码 hex。
"""
from __future__ import annotations

from typing import Any

import plotly.graph_objects as go
import streamlit as st


# ============================================================
# 颜色 token (深蓝专业型, 单主题)
# ============================================================
COLORS: dict[str, str] = {
    # --- 品牌 ---
    "primary": "#1E40AF",
    "primary_soft": "#DBEAFE",
    "accent": "#3B82F6",

    # --- 涨跌 (A 股惯例: 红涨绿跌) ---
    "bull": "#E63946",
    "bear": "#16A34A",
    "neutral": "#64748B",

    # --- 结论徽章 (大师/评分 tab 沿用) ---
    "verdict_buy": "#16A34A",
    "verdict_watch": "#F59E0B",
    "verdict_avoid": "#DC2626",

    # --- 表面 / 文本 ---
    "text_primary": "#0F172A",
    "text_muted": "#64748B",
    "text_subtle": "#94A3B8",
    "divider": "#E2E8F0",
    "card_bg": "#FFFFFF",
    "page_bg": "#F8FAFC",

    # --- 通用图表序列 (6 色, 互不冲突) ---
    "series_1": "#3B82F6",
    "series_2": "#F59E0B",
    "series_3": "#8B5CF6",
    "series_4": "#EC4899",
    "series_5": "#14B8A6",
    "series_6": "#84CC16",

    # --- 技术指标专用 ---
    "ma_5":   "#F59E0B",
    "ma_10":  "#FB923C",
    "ma_20":  "#3B82F6",
    "ma_30":  "#0EA5E9",
    "ma_60":  "#8B5CF6",
    "ma_120": "#A855F7",
    "ma_250": "#DB2777",
    "boll_band": "#94A3B8",
    "boll_fill": "rgba(148,163,184,0.10)",
    "rsi_line": "#8B5CF6",
    "rsi_over": "#E63946",
    "rsi_under": "#16A34A",
    "macd_dif": "#3B82F6",
    "macd_dea": "#F59E0B",

    # --- 资金面专用 ---
    "fund_main": "#3B82F6",     # 个股资金流 副轴收盘价
    "north_value": "#1E40AF",   # 北向持股市值
    "north_pct": "#F59E0B",     # 北向占A股流通比
    "margin_finance": "#E63946",
    "margin_securities": "#16A34A",
}


def ma_color(period: int) -> str:
    """按均线周期返回对应颜色, 未定义则降级到 series_1。"""
    return COLORS.get(f"ma_{period}", COLORS["series_1"])


# ============================================================
# 字体 token
# ============================================================
# CJK 优先, 再回退到系统 sans。Streamlit 字体设置只控部分元素,
# 这里同时通过 inject_css() 注入到 body, 让中文显示更细腻。
FONT_STACK = (
    '"PingFang SC", "Microsoft YaHei", "Hiragino Sans GB", '
    '"Noto Sans CJK SC", "Source Han Sans SC", '
    "system-ui, -apple-system, Segoe UI, Roboto, sans-serif"
)
FONT_MONO = (
    '"SF Mono", "JetBrains Mono", Menlo, Consolas, '
    '"Liberation Mono", monospace'
)


# ============================================================
# Plotly 模板
# ============================================================
def apply_plotly_theme(
    fig: go.Figure,
    *,
    height: int | None = None,
    show_legend: bool = True,
) -> go.Figure:
    """给 plotly 图加上全局视觉规范, 调用方只关心数据/trace。"""
    layout: dict[str, Any] = dict(
        paper_bgcolor=COLORS["card_bg"],
        plot_bgcolor=COLORS["card_bg"],
        font=dict(family=FONT_STACK, size=12, color=COLORS["text_primary"]),
        margin=dict(l=12, r=12, t=36, b=12),
        hoverlabel=dict(
            bgcolor=COLORS["text_primary"],
            font=dict(family=FONT_STACK, size=12, color="#FFFFFF"),
            bordercolor=COLORS["text_primary"],
        ),
        showlegend=show_legend,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
            bgcolor="rgba(255,255,255,0)",
            font=dict(family=FONT_STACK, size=11, color=COLORS["text_muted"]),
        ),
    )
    if height is not None:
        layout["height"] = height
    fig.update_layout(**layout)
    fig.update_xaxes(
        showgrid=False,
        showline=True,
        linecolor=COLORS["divider"],
        tickcolor=COLORS["divider"],
        tickfont=dict(family=FONT_STACK, size=10, color=COLORS["text_muted"]),
    )
    fig.update_yaxes(
        showgrid=True,
        gridcolor=COLORS["divider"],
        gridwidth=1,
        zeroline=False,
        showline=False,
        tickfont=dict(family=FONT_STACK, size=10, color=COLORS["text_muted"]),
    )
    return fig


# ============================================================
# 全局 CSS (排版微调 + CJK 字体栈 + 表格数字等宽)
# ============================================================
def inject_css() -> None:
    """注入一段 <style>, 在 app.py 入口调一次即可。"""
    css = f"""
    <style>
    /* ----- 全局字体栈, 让中文优先用屏显友好的西式 + CJK 组合 ----- */
    html, body, [class*="css"], .stMarkdown, .stText, .stButton, button {{
        font-family: {FONT_STACK};
    }}

    /* ----- 主标题更紧凑、稳重 ----- */
    h1 {{
        font-weight: 700;
        letter-spacing: -0.01em;
        color: {COLORS["text_primary"]};
    }}
    h2, h3 {{
        font-weight: 600;
        letter-spacing: -0.005em;
        color: {COLORS["text_primary"]};
    }}

    /* ----- Tab 栏: 文字更清晰、当前项更醒目 ----- */
    .stTabs [data-baseweb="tab-list"] {{
        gap: 4px;
        border-bottom: 1px solid {COLORS["divider"]};
    }}
    .stTabs [data-baseweb="tab"] {{
        padding: 8px 16px;
        font-weight: 500;
        color: {COLORS["text_muted"]};
    }}
    .stTabs [aria-selected="true"] {{
        color: {COLORS["primary"]} !important;
        font-weight: 600;
    }}

    /* ----- Metric: 数字使用 tabular figures, 防止跳动 ----- */
    [data-testid="stMetricValue"] {{
        font-variant-numeric: tabular-nums;
        font-family: {FONT_STACK};
        font-weight: 600;
        color: {COLORS["text_primary"]};
    }}
    [data-testid="stMetricLabel"] {{
        color: {COLORS["text_muted"]};
        font-size: 0.85rem;
    }}
    [data-testid="stMetricDelta"] {{
        font-variant-numeric: tabular-nums;
        font-family: {FONT_MONO};
    }}

    /* ----- Caption: 更柔和的灰 ----- */
    .stCaption, [data-testid="stCaptionContainer"] {{
        color: {COLORS["text_muted"]};
    }}

    /* ----- 表格: 数字等宽 ----- */
    [data-testid="stDataFrame"] td, [data-testid="stTable"] td {{
        font-variant-numeric: tabular-nums;
        font-family: {FONT_MONO};
    }}

    /* ----- 卡片容器(st.container border=True): 更柔和的边框 ----- */
    [data-testid="stVerticalBlockBorderWrapper"] {{
        border-color: {COLORS["divider"]} !important;
        border-radius: 10px !important;
    }}

    /* ----- 侧栏: 与品牌主色呼应的细节 ----- */
    [data-testid="stSidebar"] {{
        background-color: {COLORS["card_bg"]};
        border-right: 1px solid {COLORS["divider"]};
    }}

    /* ----- 分隔线更细 ----- */
    hr {{
        border-color: {COLORS["divider"]};
        opacity: 0.6;
    }}
    </style>
    """
    st.markdown(css, unsafe_allow_html=True)
