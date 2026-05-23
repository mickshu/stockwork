"""技术指标计算与信号生成（不依赖 ta-lib / pandas-ta）。

通用输入约定:
    df: 含列 [date, open, high, low, close, volume] 的 DataFrame
        - date 升序排列, dtype 为 datetime64
        - 价格已前复权 (qfq)
        - 不含 NaN / Inf / ≤0 的价格

防前瞻偏差: 所有指标在第 t 行的值仅依赖 [0..t] 行的数据, 不引用未来数据。
做回测时, 决策必须使用 ``df.iloc[t-1]`` 的指标值, 不可使用 ``iloc[t]``。
"""
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd


# ----------------------------- 基础指标 -----------------------------

def add_ma(df: pd.DataFrame, periods: list[int] | None = None) -> pd.DataFrame:
    """添加均线列 MA{period}。"""
    periods = periods or [5, 20, 60]
    out = df.copy()
    for p in periods:
        out[f"MA{p}"] = out["close"].rolling(p, min_periods=p).mean()
    return out


def add_macd(df: pd.DataFrame, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame:
    """添加 MACD: DIF / DEA / HIST。"""
    out = df.copy()
    ema_fast = out["close"].ewm(span=fast, adjust=False).mean()
    ema_slow = out["close"].ewm(span=slow, adjust=False).mean()
    out["DIF"] = ema_fast - ema_slow
    out["DEA"] = out["DIF"].ewm(span=signal, adjust=False).mean()
    out["MACD_HIST"] = (out["DIF"] - out["DEA"]) * 2  # 通达信口径
    return out


def add_rsi(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    """添加 RSI（Wilder 平滑）。"""
    out = df.copy()
    delta = out["close"].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    out[f"RSI{period}"] = 100 - 100 / (1 + rs)
    return out


def add_kdj(df: pd.DataFrame, n: int = 9, m1: int = 3, m2: int = 3) -> pd.DataFrame:
    """添加 KDJ。"""
    out = df.copy()
    low_n = out["low"].rolling(n, min_periods=n).min()
    high_n = out["high"].rolling(n, min_periods=n).max()
    rsv = (out["close"] - low_n) / (high_n - low_n).replace(0, np.nan) * 100
    out["K"] = rsv.ewm(alpha=1 / m1, adjust=False).mean()
    out["D"] = out["K"].ewm(alpha=1 / m2, adjust=False).mean()
    out["J"] = 3 * out["K"] - 2 * out["D"]
    return out


def add_boll(df: pd.DataFrame, period: int = 20, k: float = 2.0) -> pd.DataFrame:
    """添加布林带 BOLL_MID / BOLL_UP / BOLL_LOW。"""
    out = df.copy()
    mid = out["close"].rolling(period, min_periods=period).mean()
    std = out["close"].rolling(period, min_periods=period).std(ddof=0)
    out["BOLL_MID"] = mid
    out["BOLL_UP"] = mid + k * std
    out["BOLL_LOW"] = mid - k * std
    return out


def add_all(df: pd.DataFrame) -> pd.DataFrame:
    """一次性添加 MA / MACD / RSI / KDJ / BOLL 全部指标。"""
    out = add_ma(df)
    out = add_macd(out)
    out = add_rsi(out)
    out = add_kdj(out)
    out = add_boll(out)
    return out


# ----------------------------- 周线趋势 -----------------------------

def weekly_trend(df_daily: pd.DataFrame, ma_period: int = 20) -> dict[str, Any]:
    """日线重采样为周线 → 判断 MA{period} 趋势方向。

    返回: {trend: '上行'|'下行'|'盘整'|'数据不足', ma_value, slope}
    """
    if len(df_daily) < ma_period * 5:
        return {"trend": "数据不足", "ma_value": None, "slope": None}
    df = df_daily.set_index("date").copy()
    weekly = df["close"].resample("W-FRI").last().dropna()
    if len(weekly) < ma_period + 4:
        return {"trend": "数据不足", "ma_value": None, "slope": None}
    ma = weekly.rolling(ma_period, min_periods=ma_period).mean()
    last = float(ma.iloc[-1])
    prev = float(ma.iloc[-5])  # 4 周前
    slope = (last - prev) / prev if prev else 0.0
    if slope > 0.01:
        trend = "上行"
    elif slope < -0.01:
        trend = "下行"
    else:
        trend = "盘整"
    return {"trend": trend, "ma_value": last, "slope": slope}


# ----------------------------- 综合信号 -----------------------------

def gen_signal(df_with_indicators: pd.DataFrame, weekly_info: dict[str, Any]) -> dict[str, Any]:
    """基于最近一根 K 线综合判断交易信号。

    入参 df_with_indicators 应已通过 add_all() 计算好指标。

    规则:
        - 周线上行 + 日线 RSI < 30 + MACD 金叉/红柱抬头  → 买入
        - 周线下行 + 日线 RSI > 70 + MACD 死叉/绿柱抬头  → 卖出
        - 否则 → 观望

    返回: {signal, reason, trigger_price, rsi, macd_hist, weekly_trend}
    """
    if df_with_indicators.empty:
        return {"signal": "数据不足", "reason": "无 K 线数据"}

    latest = df_with_indicators.iloc[-1]
    prev = df_with_indicators.iloc[-2] if len(df_with_indicators) >= 2 else latest

    rsi = float(latest.get("RSI14", np.nan)) if not pd.isna(latest.get("RSI14")) else None
    hist = float(latest.get("MACD_HIST", np.nan)) if not pd.isna(latest.get("MACD_HIST")) else None
    hist_prev = float(prev.get("MACD_HIST", np.nan)) if not pd.isna(prev.get("MACD_HIST")) else None
    trend = weekly_info.get("trend", "数据不足")
    price = float(latest["close"])

    reasons: list[str] = [f"周线趋势 {trend}"]
    score = 0  # +正 → 偏多, -负 → 偏空

    # 周线趋势
    if trend == "上行":
        score += 2
    elif trend == "下行":
        score -= 2

    # RSI
    if rsi is not None:
        reasons.append(f"RSI14 = {rsi:.1f}")
        if rsi < 30:
            score += 2
        elif rsi > 70:
            score -= 2
        elif 30 <= rsi < 50:
            score += 1
        elif 50 < rsi <= 70:
            score -= 1

    # MACD 柱状图变化
    if hist is not None and hist_prev is not None:
        reasons.append(f"MACD柱 {hist:+.3f} (前 {hist_prev:+.3f})")
        if hist > 0 and hist > hist_prev:
            score += 2  # 红柱放大
        elif hist > 0 and hist < hist_prev:
            score += 0  # 红柱缩小
        elif hist < 0 and hist < hist_prev:
            score -= 2  # 绿柱放大
        elif hist < 0 and hist > hist_prev:
            score -= 0  # 绿柱缩小

    if score >= 3:
        signal = "买入"
    elif score <= -3:
        signal = "卖出"
    else:
        signal = "观望"

    return {
        "signal": signal,
        "score": score,
        "reason": "; ".join(reasons),
        "trigger_price": price,
        "rsi": rsi,
        "macd_hist": hist,
        "weekly_trend": trend,
        "timestamp": pd.Timestamp(latest["date"]).strftime("%Y-%m-%d"),
    }
