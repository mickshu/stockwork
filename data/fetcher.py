"""akshare 数据接入层。

所有函数返回标准化 DataFrame / dict，并通过 streamlit 缓存层降低重复请求。
价格类数据**强制前复权（qfq）**，杜绝复权方式被误改。
"""
from __future__ import annotations

import datetime as dt
import os
import time
from typing import Any, Callable

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

def _retry(fn: Callable, attempts: int = 3, base_delay: float = 0.6) -> Any:
    """失败重试: 第 i 次失败后 sleep base_delay * 2**i 秒。耗尽后抛最后异常。"""
    last_exc: Exception | None = None
    for i in range(attempts):
        try:
            return fn()
        except Exception as e:
            last_exc = e
            if i < attempts - 1:
                time.sleep(base_delay * (2 ** i))
    assert last_exc is not None
    raise last_exc


_EM_RENAME = {
    "日期": "date", "开盘": "open", "收盘": "close", "最高": "high", "最低": "low",
    "成交量": "volume", "成交额": "amount", "涨跌幅": "pct_change",
}


def _normalize_em(raw: pd.DataFrame) -> pd.DataFrame:
    df = raw.rename(columns=_EM_RENAME)[list(_EM_RENAME.values())].copy()
    df["date"] = pd.to_datetime(df["date"])
    return df


def _normalize_tx(raw: pd.DataFrame) -> pd.DataFrame:
    """腾讯接口列名: date open close high low amount (无 amount 时可能为 vol)。"""
    df = raw.copy()
    df.columns = [str(c).strip().lower() for c in df.columns]
    rename = {"vol": "volume", "成交量": "volume", "成交额": "amount"}
    df = df.rename(columns=rename)
    for col in ("open", "close", "high", "low"):
        if col not in df.columns:
            raise RuntimeError(f"tx 数据缺少列 {col}")
    if "volume" not in df.columns:
        df["volume"] = 0.0
    if "amount" not in df.columns:
        df["amount"] = 0.0
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)
    df["pct_change"] = df["close"].pct_change() * 100
    return df[["date", "open", "close", "high", "low", "volume", "amount", "pct_change"]]


def _fetch_em(code: str, period: str, start: str, end: str) -> pd.DataFrame:
    raw = ak.stock_zh_a_hist(
        symbol=code, period=period, start_date=start, end_date=end, adjust="qfq"
    )
    if raw is None or raw.empty:
        return pd.DataFrame()
    return _normalize_em(raw)


def _fetch_tx(code: str, start: str, end: str) -> pd.DataFrame:
    """腾讯 (qq.com) 备用源, 仅支持日线。"""
    prefix = "sh" if code.startswith(("6", "9")) else "sz"
    raw = ak.stock_zh_a_hist_tx(
        symbol=f"{prefix}{code}", start_date=start, end_date=end, adjust="qfq"
    )
    if raw is None or raw.empty:
        return pd.DataFrame()
    return _normalize_tx(raw)


def _resample(df_daily: pd.DataFrame, period: str) -> pd.DataFrame:
    """日线 → 周/月线 (OHLC 聚合, 成交量求和)。"""
    rule = {"weekly": "W-FRI", "monthly": "ME"}[period]
    s = df_daily.set_index("date")
    out = pd.DataFrame({
        "open": s["open"].resample(rule).first(),
        "high": s["high"].resample(rule).max(),
        "low": s["low"].resample(rule).min(),
        "close": s["close"].resample(rule).last(),
        "volume": s["volume"].resample(rule).sum(),
        "amount": s["amount"].resample(rule).sum(),
    }).dropna(subset=["open", "close"]).reset_index()
    out["pct_change"] = out["close"].pct_change() * 100
    return out


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

    源切换策略:
        1. eastmoney (push2his) 重试 3 次
        2. 失败后切腾讯日线源; 周/月线由日线 resample 得到
    """
    assert adjust == "qfq", "本系统强制前复权 (qfq)，禁止使用其他复权方式"
    code = normalize_symbol(symbol)
    if end is None:
        end = dt.date.today().strftime("%Y%m%d")
    if start is None:
        start = (dt.date.today() - dt.timedelta(days=365 * 3)).strftime("%Y%m%d")

    empty_cols = ["date", "open", "close", "high", "low", "volume", "amount", "pct_change"]

    df: pd.DataFrame | None = None
    em_err: Exception | None = None
    try:
        df = _retry(lambda: _fetch_em(code, period, start, end))
    except Exception as e:
        em_err = e

    if df is None or df.empty:
        try:
            daily = _retry(lambda: _fetch_tx(code, start, end))
        except Exception as tx_err:
            if em_err is not None:
                raise em_err
            raise tx_err
        if daily.empty:
            return pd.DataFrame(columns=empty_cols)
        df = daily if period == "daily" else _resample(daily, period)

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


# ----------------------------- 资金面: 个股资金流向 -----------------------------

def _market_of(code: str) -> str:
    """A 股代码 → 交易所标识 (sh/sz/bj), 用于 stock_individual_fund_flow。"""
    if code.startswith(("6", "9")):
        return "sh"
    if code.startswith(("0", "3")):
        return "sz"
    if code.startswith(("4", "8")):
        return "bj"
    return "sh"


@_cache_data(ttl=3600, show_spinner=False)
def get_fund_flow(symbol: str) -> pd.DataFrame:
    """个股资金流向历史 (近 ~250 个交易日)。

    输出列: [date, close, pct_change, main_net, main_pct,
            super_net, big_net, mid_net, small_net]
    单位: 净额=元, pct=百分数。
    push2his 接口偶发不可达——失败重试 3 次后返回空 DataFrame, 由上层 UI 提示降级。
    """
    code = normalize_symbol(symbol)
    empty_cols = ["date", "close", "pct_change", "main_net", "main_pct",
                  "super_net", "big_net", "mid_net", "small_net"]
    try:
        raw = _retry(lambda: ak.stock_individual_fund_flow(stock=code, market=_market_of(code)))
    except Exception:
        return pd.DataFrame(columns=empty_cols)
    if raw is None or raw.empty:
        return pd.DataFrame(columns=empty_cols)

    rename = {
        "日期": "date", "收盘价": "close", "涨跌幅": "pct_change",
        "主力净流入-净额": "main_net", "主力净流入-净占比": "main_pct",
        "超大单净流入-净额": "super_net",
        "大单净流入-净额": "big_net",
        "中单净流入-净额": "mid_net",
        "小单净流入-净额": "small_net",
    }
    keep = [c for c in rename if c in raw.columns]
    df = raw[keep].rename(columns={k: rename[k] for k in keep}).copy()
    df["date"] = pd.to_datetime(df["date"])
    for c in df.columns:
        if c != "date":
            df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df.sort_values("date").reset_index(drop=True)
    # 确保所有列存在
    for c in empty_cols:
        if c not in df.columns:
            df[c] = pd.NA
    return df[empty_cols]


# ----------------------------- 资金面: 北向资金 -----------------------------

@_cache_data(ttl=3600, show_spinner=False)
def get_north_holding(symbol: str) -> pd.DataFrame:
    """北向资金对该股的持股历史 (2017 至今, 沪/深股通成立后才有数据)。

    输出列: [date, close, shares, market_value, pct_of_a, net_buy_amount]
        - shares: 持股数量
        - market_value: 持股市值 (元)
        - pct_of_a: 持股数量占 A 股流通比 (%)
        - net_buy_amount: 当日净增持资金 (元)
    """
    code = normalize_symbol(symbol)
    empty_cols = ["date", "close", "shares", "market_value", "pct_of_a", "net_buy_amount"]
    try:
        raw = _retry(lambda: ak.stock_hsgt_individual_em(symbol=code))
    except Exception:
        return pd.DataFrame(columns=empty_cols)
    if raw is None or raw.empty:
        return pd.DataFrame(columns=empty_cols)

    rename = {
        "持股日期": "date", "当日收盘价": "close",
        "持股数量": "shares", "持股市值": "market_value",
        "持股数量占A股百分比": "pct_of_a",
        "今日增持资金": "net_buy_amount",
    }
    keep = [c for c in rename if c in raw.columns]
    df = raw[keep].rename(columns={k: rename[k] for k in keep}).copy()
    df["date"] = pd.to_datetime(df["date"])
    for c in df.columns:
        if c != "date":
            df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df.sort_values("date").reset_index(drop=True)
    for c in empty_cols:
        if c not in df.columns:
            df[c] = pd.NA
    return df[empty_cols]


# ----------------------------- 资金面: 全市场融资融券 -----------------------------

@_cache_data(ttl=86400, show_spinner=False)
def get_margin_market() -> pd.DataFrame:
    """全市场融资融券余额历史 (2012-09 至今, 日级)。

    输出列: [date, finance_balance, securities_balance, total_balance]
        - finance_balance: 融资余额 (亿元)
        - securities_balance: 融券余额 (亿元)
        - total_balance: 融资融券余额 (亿元)
    注意: akshare 返回单位为亿元, 不再换算。
    """
    empty_cols = ["date", "finance_balance", "securities_balance", "total_balance"]
    try:
        raw = _retry(lambda: ak.stock_margin_account_info())
    except Exception:
        return pd.DataFrame(columns=empty_cols)
    if raw is None or raw.empty:
        return pd.DataFrame(columns=empty_cols)

    rename = {
        "日期": "date",
        "融资余额": "finance_balance",
        "融券余额": "securities_balance",
    }
    keep = [c for c in rename if c in raw.columns]
    df = raw[keep].rename(columns={k: rename[k] for k in keep}).copy()
    df["date"] = pd.to_datetime(df["date"])
    for c in df.columns:
        if c != "date":
            df[c] = pd.to_numeric(df[c], errors="coerce")
    df["total_balance"] = df["finance_balance"].fillna(0) + df["securities_balance"].fillna(0)
    df = df.sort_values("date").reset_index(drop=True)
    return df[empty_cols]


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
