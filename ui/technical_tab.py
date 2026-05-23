"""技术面 tab: K 线 + MA + BOLL + MACD + RSI 的 plotly 子图, 下方追加资金面。"""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots


def render(
    df_ind: pd.DataFrame,
    weekly_info: dict,
    signal: dict,
    ma_periods: list[int],
    fund_flow_df: pd.DataFrame | None = None,
    north_df: pd.DataFrame | None = None,
    margin_df: pd.DataFrame | None = None,
) -> None:
    st.subheader("技术指标")

    # 顶部摘要
    col1, col2, col3 = st.columns(3)
    col1.metric("周线趋势", weekly_info.get("trend", "—"))
    col2.metric("最新 RSI14", f"{signal.get('rsi'):.1f}" if signal.get("rsi") is not None else "—")
    col3.metric("交易信号", signal.get("signal", "—"))

    st.caption(signal.get("reason", ""))

    if df_ind is None or df_ind.empty:
        st.info("无 K 线数据")
        return

    # 只画最近 250 个交易日，避免图过密
    df = df_ind.tail(250).copy()

    fig = make_subplots(
        rows=3, cols=1, shared_xaxes=True,
        row_heights=[0.55, 0.22, 0.23],
        vertical_spacing=0.04,
        subplot_titles=("K线 + MA + 布林带", "MACD", "RSI14"),
    )

    # --- K线 ---
    fig.add_trace(
        go.Candlestick(
            x=df["date"], open=df["open"], high=df["high"], low=df["low"], close=df["close"],
            name="K线",
            increasing_line_color="#ef4444", decreasing_line_color="#10b981",
        ),
        row=1, col=1,
    )

    # --- MA ---
    for p in ma_periods:
        col = f"MA{p}"
        if col in df.columns:
            fig.add_trace(
                go.Scatter(x=df["date"], y=df[col], name=col, mode="lines",
                           line=dict(width=1)),
                row=1, col=1,
            )

    # --- BOLL ---
    if "BOLL_UP" in df.columns:
        fig.add_trace(
            go.Scatter(x=df["date"], y=df["BOLL_UP"], name="BOLL上轨", mode="lines",
                       line=dict(color="#9ca3af", width=1, dash="dot")),
            row=1, col=1,
        )
        fig.add_trace(
            go.Scatter(x=df["date"], y=df["BOLL_LOW"], name="BOLL下轨", mode="lines",
                       line=dict(color="#9ca3af", width=1, dash="dot"),
                       fill="tonexty", fillcolor="rgba(156,163,175,0.08)"),
            row=1, col=1,
        )

    # --- MACD ---
    if "DIF" in df.columns:
        fig.add_trace(go.Scatter(x=df["date"], y=df["DIF"], name="DIF",
                                  line=dict(color="#3b82f6", width=1)), row=2, col=1)
        fig.add_trace(go.Scatter(x=df["date"], y=df["DEA"], name="DEA",
                                  line=dict(color="#f59e0b", width=1)), row=2, col=1)
        colors = ["#ef4444" if v >= 0 else "#10b981" for v in df["MACD_HIST"].fillna(0)]
        fig.add_trace(go.Bar(x=df["date"], y=df["MACD_HIST"], name="MACD柱",
                              marker_color=colors), row=2, col=1)

    # --- RSI ---
    if "RSI14" in df.columns:
        fig.add_trace(go.Scatter(x=df["date"], y=df["RSI14"], name="RSI14",
                                  line=dict(color="#8b5cf6", width=1)), row=3, col=1)
        fig.add_hline(y=70, line_dash="dash", line_color="#ef4444", row=3, col=1)
        fig.add_hline(y=30, line_dash="dash", line_color="#10b981", row=3, col=1)

    fig.update_layout(
        height=720,
        showlegend=True,
        xaxis_rangeslider_visible=False,
        margin=dict(l=10, r=10, t=40, b=10),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    fig.update_xaxes(rangeslider_visible=False)
    st.plotly_chart(fig, use_container_width=True)

    # ===================================================
    # 资金面 section
    # ===================================================
    st.divider()
    st.subheader("💰 资金面")
    st.caption("主力资金 / 北向持股 / 全市场融资融券——结合技术信号判断主力与情绪。")

    _render_fund_flow(fund_flow_df)
    _render_north(north_df)
    _render_margin(margin_df)


def _render_fund_flow(df: pd.DataFrame | None) -> None:
    st.markdown("**① 个股主力资金净流入**")
    if df is None or df.empty:
        st.info("个股资金流向接口暂不可达（push2his 节点偶发性问题），可稍后重试。")
        return
    d = df.tail(120).copy()
    colors = ["#ef4444" if v >= 0 else "#10b981" for v in d["main_net"].fillna(0)]
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(
        go.Bar(x=d["date"], y=d["main_net"], name="主力净流入(元)", marker_color=colors),
        secondary_y=False,
    )
    fig.add_trace(
        go.Scatter(x=d["date"], y=d["close"], name="收盘价", mode="lines",
                   line=dict(color="#3b82f6", width=1.5)),
        secondary_y=True,
    )
    fig.update_layout(height=320, margin=dict(l=10, r=10, t=10, b=10),
                      legend=dict(orientation="h", y=1.08))
    fig.update_yaxes(title_text="净流入(元)", secondary_y=False)
    fig.update_yaxes(title_text="收盘价", secondary_y=True)
    st.plotly_chart(fig, use_container_width=True)
    with st.expander("数据说明"):
        st.markdown(
            "- **正值（红柱）= 主力净买入**, 负值（绿柱）= 主力净卖出\n"
            "- 持续多日主力净流入 + 股价同步走高 → 主力建仓/拉升\n"
            "- 主力净流入但股价不涨 → 可能在派发对倒\n"
            "- 数据来源: 东方财富, 最近 120 个交易日"
        )


def _render_north(df: pd.DataFrame | None) -> None:
    st.markdown("**② 北向资金持股趋势**")
    if df is None or df.empty:
        st.info("无北向持股数据（个股可能未纳入沪深港通）。")
        return
    d = df.dropna(subset=["market_value"]).copy()
    if d.empty:
        st.info("无有效北向持股记录。")
        return
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(
        go.Scatter(x=d["date"], y=d["market_value"] / 1e8, name="持股市值(亿元)",
                   mode="lines", line=dict(color="#3b82f6", width=1.5)),
        secondary_y=False,
    )
    fig.add_trace(
        go.Scatter(x=d["date"], y=d["pct_of_a"], name="持股占A股流通比(%)",
                   mode="lines", line=dict(color="#f59e0b", width=1.5, dash="dot")),
        secondary_y=True,
    )
    fig.update_layout(height=320, margin=dict(l=10, r=10, t=10, b=10),
                      legend=dict(orientation="h", y=1.08))
    fig.update_yaxes(title_text="持股市值(亿元)", secondary_y=False)
    fig.update_yaxes(title_text="占A股流通比(%)", secondary_y=True)
    st.plotly_chart(fig, use_container_width=True)
    with st.expander("数据说明"):
        st.markdown(
            f"- 数据范围: {d['date'].min():%Y-%m-%d} 至 {d['date'].max():%Y-%m-%d}\n"
            "- **占 A 股流通比持续抬升** → 北向资金加仓, 长期通常对应基本面认可\n"
            "- **占比快速回落** → 外资减仓, 注意止盈情绪/汇率/政策因素\n"
            "- 数据来源: 东方财富沪深港通"
        )


def _render_margin(df: pd.DataFrame | None) -> None:
    st.markdown("**③ 全市场融资融券余额**")
    if df is None or df.empty:
        st.info("融资融券数据加载失败。")
        return
    d = df.tail(500).copy()  # 近 ~2 年
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(
        go.Scatter(x=d["date"], y=d["finance_balance"], name="融资余额(亿)",
                   mode="lines", line=dict(color="#ef4444", width=1.5)),
        secondary_y=False,
    )
    fig.add_trace(
        go.Scatter(x=d["date"], y=d["securities_balance"], name="融券余额(亿)",
                   mode="lines", line=dict(color="#10b981", width=1.5)),
        secondary_y=True,
    )
    fig.update_layout(height=320, margin=dict(l=10, r=10, t=10, b=10),
                      legend=dict(orientation="h", y=1.08))
    fig.update_yaxes(title_text="融资余额(亿)", secondary_y=False)
    fig.update_yaxes(title_text="融券余额(亿)", secondary_y=True)
    st.plotly_chart(fig, use_container_width=True)
    with st.expander("数据说明"):
        st.markdown(
            "- 注意: 这是**全市场**数据, 不是个股的融资融券\n"
            "- 融资余额走高 → 散户/机构加杠杆做多情绪升温, 也意味系统性杠杆风险上升\n"
            "- 融券余额走高 → 做空力量增强, 通常出现在指数顶部区间\n"
            "- 数据来源: 中国证券金融公司"
        )
