"""Streamlit 入口: A 股基本面 + 技术面分析助手。

启动:
    streamlit run app.py
"""
from __future__ import annotations

import streamlit as st

from analysis.fundamental import collect_all
from analysis.masters import consensus as masters_consensus
from analysis.masters import evaluate_all as evaluate_masters
from analysis.risk import detect_risks
from analysis.scoring import evaluate
from analysis.technical import add_all, gen_signal, weekly_trend
from data.fetcher import (
    get_financial_indicators,
    get_fund_flow,
    get_industry_pe,
    get_margin_market,
    get_north_holding,
    get_price_history,
    get_realtime_quote,
    get_stock_info,
    get_valuation,
)
from ui.fundamental_tab import render as render_fundamental
from ui.masters_tab import render as render_masters
from ui.overview_tab import render as render_overview
from ui.report_tab import render as render_report
from ui.sidebar import render_sidebar
from ui.technical_tab import render as render_technical


st.set_page_config(page_title="A股分析助手", page_icon="📈", layout="wide")


def main() -> None:
    cfg = render_sidebar()
    if cfg is None:
        st.title("📈 A 股基本面 + 技术面分析助手")
        st.info("请在左侧输入有效的 6 位股票代码 (如 `600519`) 开始分析。")
        return

    symbol = cfg["symbol"]
    period = cfg["period"]
    ma_periods = cfg["ma_periods"]

    # ---------- 数据加载 ----------
    with st.spinner(f"正在拉取 {symbol} 的全部数据..."):
        try:
            info = get_stock_info(symbol)
        except Exception as e:
            st.error(f"获取股票基本信息失败: {e}")
            return

        try:
            df_price = get_price_history(symbol, period=period)
        except Exception as e:
            st.error(f"获取行情数据失败: {e}")
            return

        df_fin = _safe_call(get_financial_indicators, symbol, default=None)
        valuation = _safe_call(get_valuation, symbol, default={}) or {}
        quote = _safe_call(get_realtime_quote, symbol, default={}) or {}
        industry_pe = _safe_call(get_industry_pe, info.get("industry", ""), default=None)
        df_fund_flow = _safe_call(get_fund_flow, symbol, default=None)
        df_north = _safe_call(get_north_holding, symbol, default=None)
        df_margin = _safe_call(get_margin_market, default=None)

    # ---------- 计算 ----------
    if df_price is None or df_price.empty:
        st.error("行情数据为空，无法分析")
        return

    # 实时报价兜底: push2 接口不可达时, 用 K 线最后一根近似
    if not quote.get("price"):
        last = df_price.iloc[-1]
        prev = df_price.iloc[-2] if len(df_price) >= 2 else last
        prev_close = float(prev["close"])
        last_close = float(last["close"])
        quote = {
            "price": last_close,
            "open": float(last["open"]),
            "high": float(last["high"]),
            "low": float(last["low"]),
            "prev_close": prev_close,
            "pct_change": (last_close / prev_close - 1) * 100 if prev_close else None,
            "volume": float(last["volume"]) if "volume" in last else None,
            "amount": float(last["amount"]) if "amount" in last else None,
        }
        st.info("⚠️ 实时报价接口不可达，已用最新 K 线收盘价代替", icon="ℹ️")

    df_ind = add_all(df_price)
    weekly_info = weekly_trend(df_price) if period == "daily" else {"trend": "数据不足"}
    signal = gen_signal(df_ind, weekly_info)

    fund_items = collect_all(df_fin if df_fin is not None else df_price.iloc[:0], valuation, industry_pe)
    risks = detect_risks(df_fin, valuation, industry_pe, info)
    report = evaluate(fund_items, weekly_info, signal, risks)
    master_views = evaluate_masters(fund_items, valuation, industry_pe, weekly_info, signal, df_fin)
    master_consensus = masters_consensus(master_views)

    # ---------- 渲染 ----------
    st.title(f"📈 {info.get('name', '—')}  ({info.get('code', '—')})  分析报告")

    tab_overview, tab_fund, tab_tech, tab_masters, tab_report = st.tabs(
        ["📊 概览", "📑 基本面", "📈 技术面", "🎓 大师观点", "🎯 综合评分"]
    )

    with tab_overview:
        render_overview(info, quote, valuation)
    with tab_fund:
        render_fundamental(fund_items, df_fin)
    with tab_tech:
        render_technical(
            df_ind, weekly_info, signal, ma_periods,
            fund_flow_df=df_fund_flow, north_df=df_north, margin_df=df_margin,
        )
    with tab_masters:
        render_masters(master_views, master_consensus)
    with tab_report:
        render_report(report, symbol, info.get("name", ""))


def _safe_call(fn, *args, default=None, **kwargs):
    """调用 fetcher，失败时返回默认值并在 UI 顶部弹 warning。"""
    try:
        return fn(*args, **kwargs)
    except Exception as e:
        st.warning(f"{fn.__name__} 失败: {e}")
        return default


if __name__ == "__main__":
    main()
