"""大师观点 tab: 展示 10 位投资大师的视角与共识。"""
from __future__ import annotations

import streamlit as st


_VERDICT_COLOR = {"买入": "🟢", "观望": "🟡", "回避": "🔴"}


def _stars(n: int) -> str:
    return "★" * n + "☆" * (5 - n)


def render(views: list[dict], consensus: dict) -> None:
    st.subheader("🎓 投资大师视角")
    st.caption(
        "10 位大师按各自核心方法论对当前股票打分。**这不是预测，而是把同一组数据放到不同分析框架下，看哪些大师会买、哪些会避。**"
    )

    # ---- 共识汇总 ----
    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("共识结论", consensus.get("verdict", "—"))
    col2.metric("平均星级", f"{consensus.get('avg_score', 0)}/5")
    col3.metric("🟢 买入", f"{consensus.get('buy', 0)}/10")
    col4.metric("🟡 观望", f"{consensus.get('watch', 0)}/10")
    col5.metric("🔴 回避", f"{consensus.get('avoid', 0)}/10")

    st.divider()

    # ---- 大师卡片网格 ----
    for i in range(0, len(views), 2):
        cols = st.columns(2, gap="medium")
        for col, v in zip(cols, views[i:i + 2]):
            with col:
                _render_card(v)


def _render_card(v: dict) -> None:
    badge = _VERDICT_COLOR.get(v["verdict"], "⚪")
    with st.container(border=True):
        st.markdown(
            f"### {badge} {v['master']}  &nbsp;&nbsp;<span style='font-size:0.85em;color:#888'>{_stars(v['score'])}</span>",
            unsafe_allow_html=True,
        )
        st.caption(f"**学派**：{v['school']}")
        st.caption(f"**理念**：{v['philosophy']}")

        if v.get("reasons") and v["reasons"] != ["—"]:
            st.markdown("**✅ 看好的理由**")
            for r in v["reasons"]:
                st.markdown(f"- {r}")
        if v.get("concerns") and v["concerns"] != ["—"]:
            st.markdown("**⚠️ 主要顾虑**")
            for c in v["concerns"]:
                st.markdown(f"- {c}")
        st.markdown(f"**建议**：**{v['verdict']}**")
