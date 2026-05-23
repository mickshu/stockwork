"""左侧栏: 代码直填 + 中文搜索下拉 + 最近 5 只快捷按钮, 改动即触发分析。"""
from __future__ import annotations

import streamlit as st

from data.fetcher import _all_code_name


DEFAULT_CODE = "600519"
RECENT_KEY = "recent_symbols"
RECENT_MAX = 5


def _push_recent(symbol: str) -> None:
    """把 symbol 顶到最近列表第一位, 去重, 截断到 RECENT_MAX。"""
    lst = list(st.session_state.get(RECENT_KEY, []))
    if symbol in lst:
        lst.remove(symbol)
    lst.insert(0, symbol)
    st.session_state[RECENT_KEY] = lst[:RECENT_MAX]


def _set_symbol_from_direct() -> None:
    """text_input 的 on_change 回调: 校验并写 symbol。"""
    raw = (st.session_state.get("symbol_direct") or "").strip()
    if raw and raw.isdigit() and len(raw) == 6:
        st.session_state["symbol"] = raw


def _set_symbol_from_select() -> None:
    """selectbox 的 on_change 回调: 从展示串里取代码。"""
    disp = st.session_state.get("symbol_select")
    if disp and "  " in disp:
        st.session_state["symbol"] = disp.split("  ", 1)[0]


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
    """渲染侧边栏。返回 {symbol, period, ma_periods} (symbol 有效时), 否则 None。"""
    st.sidebar.title("📈 A 股分析助手")
    st.sidebar.caption("基本面 + 技术面 + 大师观点 + 综合评分")

    # 当前 symbol (默认 600519)
    cur = st.session_state.get("symbol", DEFAULT_CODE)

    # ---- 1. 代码直填 ----
    st.sidebar.text_input(
        "股票代码（6 位, 回车切换）",
        value=cur,
        key="symbol_direct",
        max_chars=8,
        on_change=_set_symbol_from_direct,
        help="最快的输入方式: 直接敲 6 位代码后回车",
    )

    # ---- 2. 中文搜索下拉 ----
    displays, mapping = _load_options()
    code_to_disp: dict[str, str] = {v: k for k, v in mapping.items()}
    if displays:
        default_disp = code_to_disp.get(cur) or displays[0]
        try:
            default_idx = displays.index(default_disp)
        except ValueError:
            default_idx = 0
        st.sidebar.selectbox(
            "或在全市场中搜索（中文/代码）",
            options=displays,
            index=default_idx,
            key="symbol_select",
            on_change=_set_symbol_from_select,
            help="点开下拉后可直接输入「茅台」等中文联想",
        )
    else:
        st.sidebar.warning("全市场列表加载失败，仅可使用代码直填")

    # ---- 3. 最近查看 ----
    recent = list(st.session_state.get(RECENT_KEY, []))
    if recent:
        st.sidebar.markdown("**最近查看**")
        # 每行最多 3 个按钮
        for row_start in range(0, len(recent), 3):
            row = recent[row_start:row_start + 3]
            cols = st.sidebar.columns(len(row))
            for col, code in zip(cols, row):
                name = mapping_name(mapping, code)
                label = f"{code}\n{name}" if name else code
                if col.button(label, key=f"recent_{code}", use_container_width=True):
                    st.session_state["symbol"] = code
                    st.rerun()

    st.sidebar.divider()

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
    st.sidebar.markdown(
        "**说明**\n"
        "- 代码/下拉/最近 三处任一改动即自动重新分析\n"
        "- 价格强制 **前复权**\n"
        "- 仅供学习研究，不构成投资建议"
    )

    # ---- 校验并返回 ----
    symbol = (st.session_state.get("symbol") or "").strip()
    if not symbol or not symbol.isdigit() or len(symbol) != 6:
        st.sidebar.error("请输入 6 位股票代码")
        return None

    _push_recent(symbol)
    return {"symbol": symbol, "period": period, "ma_periods": ma_periods or [5, 20, 60]}


def mapping_name(mapping: dict[str, str], code: str) -> str:
    """从 mapping 反查 code 对应的中文名 (短名)。"""
    for disp, c in mapping.items():
        if c == code:
            # disp 格式: "600519  贵州茅台"
            parts = disp.split("  ", 1)
            return parts[1] if len(parts) > 1 else ""
    return ""
