"""基本面 tab: 指标卡片 + 财务历史表。"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from utils.format import fmt_num, pass_emoji


def render(items: list[dict], df_fin: pd.DataFrame) -> None:
    st.subheader("基本面核心指标")
    st.caption("阈值依据 CLAUDE.md：ROE > 15% · 资产负债率 < 50% · 近 3 年净利润 CAGR > 10%")

    # 三列网格展示指标
    cols = st.columns(min(len(items), 3) or 1)
    for i, it in enumerate(items):
        with cols[i % 3]:
            value_str = fmt_num(it.get("value")) + (it.get("unit") or "")
            st.metric(
                label=f"{pass_emoji(it.get('pass', False))} {it.get('name')}",
                value=value_str if it.get("value") is not None else "—",
                help=it.get("comment"),
            )
            st.caption(it.get("comment", ""))

    st.divider()
    st.subheader("近期财务历史")
    if df_fin is None or df_fin.empty:
        st.info("未获取到财务历史数据")
        return

    keep = ["报告期"]
    for kw in ["净资产收益率", "资产负债率", "净利润", "营业总收入", "销售毛利率", "销售净利率", "经营活动"]:
        keep += [c for c in df_fin.columns if kw in c and c not in keep]
    show = df_fin[[c for c in keep if c in df_fin.columns]].head(8).copy()
    if "报告期" in show.columns:
        show["报告期"] = show["报告期"].dt.strftime("%Y-%m-%d")
    st.dataframe(show, use_container_width=True, hide_index=True)
