"""技术面 tab: K 线 + MA + BOLL + MACD + RSI 的 plotly 子图。"""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots


def render(df_ind: pd.DataFrame, weekly_info: dict, signal: dict, ma_periods: list[int]) -> None:
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
