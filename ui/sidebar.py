"""左侧栏: 股票选择 (中文/代码联想补全) 与分析参数。"""
from __future__ import annotations

import streamlit as st

from data.fetcher import _all_code_name


DEFAULT_CODE = "600519"


@st.cache_data(ttl=86400, show_spinner="正在加载全市场股票列表...")
def _load_options() -> tuple[list[str], dict[str, str]]:
    """返回 (display_list, display→code 映射)。"""
    code_name = _all_code_name()
    if not code_name:
        return [], {}
    pairs = sorted(code_name.items(), key=lambda x: x[0])
    displays = [f"{c}  {n}" for c, n in pairs]
    mapping = {f"{c}  {n}": c for c, n in pairs}
    return displays, mapping


def render_sidebar() -> dict | None:
    """渲染侧边栏。返回 {symbol, period, ma_periods} 或 None。"""
    st.sidebar.title("📈 A 股分析助手")
    st.sidebar.caption("基本面 + 技术面 + 大师观点 + 综合评分")

    displays, mapping = _load_options()

    if displays:
        # 找到默认 code 在 options 中的索引
        default_display = next(
            (d for d in displays if d.startswith(st.session_state.get("symbol", DEFAULT_CODE))),
            None,
        )
        default_idx = displays.index(default_display) if default_display else 0

        choice = st.sidebar.selectbox(
            "股票（支持代码或中文名搜索）",
            options=displays,
            index=default_idx,
            help="点击下拉框后可直接输入代码（600519）或中文（茅台），自动过滤匹配项",
        )
        symbol = mapping[choice]
    else:
        # 兜底: 加载失败时退回文本输入
        st.sidebar.warning("全市场列表加载失败，请直接输入 6 位代码")
        symbol = st.sidebar.text_input(
            "股票代码",
            value=st.session_state.get("symbol", DEFAULT_CODE),
            max_chars=8,
        ).strip()

    period = st.sidebar.selectbox(
        "K 线周期",
        options=["daily", "weekly", "monthly"],
        format_func=lambda x: {"daily": "日线", "weekly": "周线", "monthly": "月线"}[x],
        index=0,
    )
    ma_periods = st.sidebar.multiselect(
        "均线参数",
        options=[5, 10, 20, 30, 60, 120, 250],
        default=[5, 20, 60],
    )

    st.sidebar.divider()
    run = st.sidebar.button("🔍 开始分析", use_container_width=True, type="primary")

    st.sidebar.divider()
    st.sidebar.markdown(
        "**说明**\n"
        "- 数据来源: akshare（东财/同花顺/百度）\n"
        "- 价格强制 **前复权**\n"
        "- 仅供学习研究，不构成投资建议"
    )

    if not run:
        return None

    if not symbol or not symbol.isdigit() or len(symbol) != 6:
        st.sidebar.error("未选中有效股票")
        return None

    st.session_state["symbol"] = symbol
    return {"symbol": symbol, "period": period, "ma_periods": ma_periods or [5, 20, 60]}
