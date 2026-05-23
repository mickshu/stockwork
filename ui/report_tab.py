"""综合评分 tab: 评分卡片 + 买卖建议 + 风险提示。"""
from __future__ import annotations

import streamlit as st


def render(report: dict, symbol: str, name: str) -> None:
    st.subheader("综合评分与建议")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("基本面得分", f"{report['fundamental_score']}/100")
    col2.metric("技术面得分", f"{report['technical_score']}/100")
    col3.metric("综合总分", f"{report['total_score']}/100")

    verdict = report["verdict"]
    badge_color = {"推荐关注": "🟢", "观察": "🟡", "暂缓": "🔴"}.get(verdict, "⚪")
    col4.metric("结论", f"{badge_color} {verdict}")

    st.divider()

    # 交易信号块
    sig = report["signal"]
    sig_label = sig.get("signal", "—")
    sig_color = {"买入": "🟢", "卖出": "🔴", "观望": "🟡"}.get(sig_label, "⚪")
    st.markdown(f"### {sig_color} 当前信号：**{sig_label}**")
    st.markdown(
        f"- **时间**：{sig.get('timestamp', '—')}\n"
        f"- **股票**：{name} ({symbol})\n"
        f"- **触发价**：{sig.get('trigger_price', '—')}\n"
        f"- **依据**：{sig.get('reason', '—')}"
    )

    st.divider()

    # 风险提示 (CLAUDE.md 硬性要求至少 3 条)
    st.markdown("### ⚠️ 风险提示")
    for r in report["risks"]:
        st.markdown(f"- {r}")

    st.caption("以上分析仅供学习研究，不构成任何投资建议。市场有风险，投资需谨慎。")
