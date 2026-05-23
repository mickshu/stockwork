"""akshare 数据接入层。

所有函数返回标准化 DataFrame / dict，并通过 streamlit 缓存层降低重复请求。
价格类数据**强制前复权（qfq）**，杜绝复权方式被误改。
"""
from __future__ import annotations

import datetime as dt
import os
from typing import Any

# ---------------------------------------------------------------
# 绕过系统代理: A 股数据接口均在国内, 走代理反而会因代理服务不稳定而失败。
# requests 检查 NO_PROXY 时使用 host.endswith(entry), 故下面写主域名即可。
# 必须在 import akshare/requests 之前设置, 否则不生效。
# ---------------------------------------------------------------
_NO_PROXY_DOMAINS = (
    "eastmoney.com,10jqka.com.cn,baidu.com,sina.com.cn,sina.cn,"
    "sse.com.cn,szse.cn,iwencai.com,xueqiu.com,sinajs.cn"
)
_existing = os.environ.get("NO_PROXY", "")
os.environ["NO_PROXY"] = _existing + ("," if _existing else "") + _NO_PROXY_DOMAINS
os.environ["no_proxy"] = os.environ["NO_PROXY"]

import akshare as ak  # noqa: E402
import pandas as pd  # noqa: E402

try:
    import streamlit as st
    _cache_data = st.cache_data
except Exception:  # streamlit 未安装或非 streamlit 上下文
    def _cache_data(*a, **kw):  # type: ignore
        if a and callable(a[0]) and not kw:
            return a[0]
        def deco(fn):
            return fn
        return deco

from utils.validators import check_price_series, clean_price_df, normalize_symbol


# ----------------------------- 基本信息 -----------------------------

@_cache_data(ttl=86400, show_spinner=False)
def _all_code_name() -> dict[str, str]:
    """全市场 code → name 字典, 用作 push2 主接口失败时的兜底。
    首次约 5 秒, 之后走缓存。"""
    try:
        df = ak.stock_info_a_code_name()
        return dict(zip(df["code"].astype(str).str.zfill(6), df["name"]))
    except Exception:
        return {}


def _empty_info(code: str, name: str = "") -> dict[str, Any]:
    return {
        "code": code, "name": name, "industry": "",
        "total_share": None, "float_share": None,
        "market_cap": None, "float_cap": None, "listing_date": "",
    }


@_cache_data(ttl=3600, show_spinner=False)
def get_stock_info(symbol: str) -> dict[str, Any]:
    """返回个股基本信息: {code, name, industry, total_share, float_share, market_cap, listing_date}

    主接口走 push2.eastmoney.com; 若该 host 在当前网络下不可达, 降级到
    stock_info_a_code_name 拿股票名称, 其余字段留空。
    """
    code = normalize_symbol(symbol)
    try:
        df = ak.stock_individual_info_em(symbol=code)
        info = dict(zip(df["item"], df["value"]))
        return {
            "code": code,
            "name": str(info.get("股票简称", "")),
            "industry": str(info.get("行业", "")),
            "total_share": _safe_float(info.get("总股本")),
            "float_share": _safe_float(info.get("流通股")),
            "market_cap": _safe_float(info.get("总市值")),
            "float_cap": _safe_float(info.get("流通市值")),
            "listing_date": str(info.get("上市时间", "")),
        }
    except Exception:
        return _empty_info(code, name=_all_code_name().get(code, ""))


# ----------------------------- 历史行情 -----------------------------

@_cache_data(ttl=3600, show_spinner=False)
def get_price_history(
    symbol: str,
    period: str = "daily",
    start: str | None = None,
    end: str | None = None,
    adjust: str = "qfq",
) -> pd.DataFrame:
    """获取历史 K 线，**强制前复权**。

    输出 DataFrame 列: [date, open, close, high, low, volume, amount, pct_change]
    date 升序排列，dtype 为 datetime64。

    参数:
        symbol: 6 位股票代码（可带 sh/sz 前缀）
        period: 'daily' | 'weekly' | 'monthly'
        start, end: 'YYYYMMDD' 字符串，默认近 3 年
    """
    assert adjust == "qfq", "本系统强制前复权 (qfq)，禁止使用其他复权方式"
    code = normalize_symbol(symbol)
    if end is None:
        end = dt.date.today().strftime("%Y%m%d")
    if start is None:
        start = (dt.date.today() - dt.timedelta(days=365 * 3)).strftime("%Y%m%d")

    raw = ak.stock_zh_a_hist(
        symbol=code, period=period, start_date=start, end_date=end, adjust=adjust
    )
    if raw is None or raw.empty:
        return pd.DataFrame(columns=["date", "open", "close", "high", "low", "volume", "amount", "pct_change"])

    # akshare 列名映射
    rename = {
        "日期": "date", "开盘": "open", "收盘": "close", "最高": "high", "最低": "low",
        "成交量": "volume", "成交额": "amount", "涨跌幅": "pct_change",
    }
    df = raw.rename(columns=rename)[list(rename.values())].copy()
    df["date"] = pd.to_datetime(df["date"])
    df = clean_price_df(df)
    check_price_series(df)
    return df


# ----------------------------- 财务指标 -----------------------------

@_cache_data(ttl=3600, show_spinner=False)
def get_financial_indicators(symbol: str) -> pd.DataFrame:
    """获取近若干年的核心财务指标。

    输出 DataFrame 列（中文）:
        [报告期, 净资产收益率(%), 资产负债率(%), 净利润(元), 净利润同比增长率(%),
         营业总收入(元), 营业总收入同比增长率(%), 销售毛利率(%), 销售净利率(%),
         经营活动产生的现金流量净额(元)]
    数据按报告期降序，最近的一期在最上方。
    """
    code = normalize_symbol(symbol)
    df = ak.stock_financial_abstract_ths(symbol=code, indicator="按报告期")
    if df is None or df.empty:
        return pd.DataFrame()

    df = df.copy()
    # 数值列清洗（akshare 有时返回字符串带单位）
    for col in df.columns:
        if col == "报告期":
            continue
        df[col] = df[col].map(_parse_cn_number)
    df["报告期"] = pd.to_datetime(df["报告期"], errors="coerce")
    df = df.dropna(subset=["报告期"]).sort_values("报告期", ascending=False).reset_index(drop=True)
    return df


# ----------------------------- 实时报价 -----------------------------

@_cache_data(ttl=60, show_spinner=False)
def get_realtime_quote(symbol: str) -> dict[str, Any]:
    """获取实时报价: {price, pct_change, open, high, low, prev_close, volume, amount, pe_ttm, pb}"""
    code = normalize_symbol(symbol)
    try:
        df = ak.stock_bid_ask_em(symbol=code)
        m = dict(zip(df["item"], df["value"]))
        return {
            "price": _safe_float(m.get("最新")),
            "pct_change": _safe_float(m.get("涨幅")),
            "open": _safe_float(m.get("今开")),
            "high": _safe_float(m.get("最高")),
            "low": _safe_float(m.get("最低")),
            "prev_close": _safe_float(m.get("昨收")),
            "volume": _safe_float(m.get("总手")),
            "amount": _safe_float(m.get("金额")),
        }
    except Exception:
        return {}


@_cache_data(ttl=3600, show_spinner=False)
def get_valuation(symbol: str) -> dict[str, Any]:
    """从百度股市通获取最新 PE(TTM)/PB/总市值。"""
    code = normalize_symbol(symbol)
    out: dict[str, Any] = {}
    pairs = [
        ("pe_ttm", "市盈率(TTM)"),
        ("pb", "市净率"),
        ("total_mv", "总市值"),
    ]
    for key, ind in pairs:
        try:
            df = ak.stock_zh_valuation_baidu(symbol=code, indicator=ind, period="近一年")
            if df is None or df.empty:
                out[key] = None
                continue
            df = df.sort_values("date" if "date" in df.columns else df.columns[0])
            out[key] = _safe_float(df.iloc[-1, -1])
        except Exception:
            out[key] = None
    return out


# ----------------------------- 行业 PE -----------------------------

@_cache_data(ttl=3600, show_spinner=False)
def get_industry_pe(industry_name: str) -> float | None:
    """根据行业名称返回行业平均 PE。找不到则返回 None。"""
    if not industry_name:
        return None
    try:
        df = ak.stock_board_industry_name_em()
        if df is None or df.empty:
            return None
        # 模糊匹配
        mask = df["板块名称"].str.contains(industry_name[:2], na=False)
        if not mask.any():
            return None
        row = df[mask].iloc[0]
        # 优先用「市盈率-动态」字段（不同 akshare 版本字段名略有差异）
        for col in ("市盈率-动态", "市盈率", "动态市盈率"):
            if col in df.columns:
                return _safe_float(row[col])
        return None
    except Exception:
        return None


# ----------------------------- 内部工具 -----------------------------

def _safe_float(x: Any) -> float | None:
    if x is None:
        return None
    try:
        v = float(x)
        if pd.isna(v):
            return None
        return v
    except (TypeError, ValueError):
        return None


def _parse_cn_number(x: Any) -> float | None:
    """解析可能带「亿/万/%」单位的字符串数字。"""
    if x is None:
        return None
    if isinstance(x, (int, float)):
        return float(x) if not pd.isna(x) else None
    s = str(x).strip().replace(",", "")
    if s in ("", "--", "-", "nan", "NaN", "None"):
        return None
    mult = 1.0
    if s.endswith("亿"):
        mult = 1e8
        s = s[:-1]
    elif s.endswith("万"):
        mult = 1e4
        s = s[:-1]
    elif s.endswith("%"):
        mult = 1.0
        s = s[:-1]
    try:
        return float(s) * mult
    except ValueError:
        return None
