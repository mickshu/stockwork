"""概览 tab: 公司基本信息 + 实时报价。"""
from __future__ import annotations

import streamlit as st

from utils.format import fmt_money, fmt_num, fmt_pct


def render(info: dict, quote: dict, valuation: dict) -> None:
    st.subheader(f"{info.get('name', '—')} ({info.get('code', '—')})")
    st.caption(f"行业：{info.get('industry') or '—'}  ·  上市日期：{info.get('listing_date') or '—'}")

    col1, col2, col3, col4 = st.columns(4)
    price = quote.get("price")
    pct = quote.get("pct_change")
    prev_close = quote.get("prev_close")
    delta = None
    if price is not None and prev_close:
        delta = price - prev_close

    col1.metric(
        "现价",
        fmt_num(price),
        delta=f"{delta:+.2f} ({pct:+.2f}%)" if delta is not None and pct is not None else None,
    )
    col2.metric("今开 / 昨收", f"{fmt_num(quote.get('open'))} / {fmt_num(prev_close)}")
    col3.metric("最高 / 最低", f"{fmt_num(quote.get('high'))} / {fmt_num(quote.get('low'))}")
    col4.metric("成交额", fmt_money(quote.get("amount")))

    st.divider()

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("总市值", fmt_money(info.get("market_cap") or valuation.get("total_mv")))
    col2.metric("流通市值", fmt_money(info.get("float_cap")))
    col3.metric("PE (TTM)", fmt_num(valuation.get("pe_ttm")))
    col4.metric("PB", fmt_num(valuation.get("pb")))
