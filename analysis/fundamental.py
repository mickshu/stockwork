"""基本面指标计算。

输入约定:
    df_fin: 财务指标 DataFrame，来自 data.fetcher.get_financial_indicators
        - 第一列名为 "报告期" (datetime), 按报告期降序排列 (最近的一期在最上方)
        - 其余列为中文指标名，已是数值类型 (百分比指标已转为百分比单位，如 25.3 = 25.3%)

每个函数返回 dict:
    {
        "name": 指标名,
        "value": 数值,
        "threshold": 阈值,
        "pass": 是否通过 (bool),
        "comment": 中文说明,
        "unit": 单位 (% / 倍 / 元 等),
    }
当数据缺失时, value 为 None, pass=False, comment 注明 "数据缺失"。
"""
from __future__ import annotations

from typing import Any

import pandas as pd


# ----------------------------- 工具 -----------------------------

def _find_col(df: pd.DataFrame, *keywords: str) -> str | None:
    """按关键字模糊匹配列名。"""
    for col in df.columns:
        if all(kw in col for kw in keywords):
            return col
    return None


def _latest_value(df: pd.DataFrame, col: str | None) -> float | None:
    if col is None or df.empty:
        return None
    val = df.iloc[0][col]
    return float(val) if pd.notna(val) else None


def _missing(name: str, threshold: Any, unit: str) -> dict[str, Any]:
    return {
        "name": name, "value": None, "threshold": threshold,
        "pass": False, "comment": "数据缺失", "unit": unit,
    }


# ----------------------------- 单项指标 -----------------------------

def calc_roe(df_fin: pd.DataFrame, threshold: float = 15.0) -> dict[str, Any]:
    """净资产收益率 (最新报告期)。阈值默认 15%。"""
    col = _find_col(df_fin, "净资产收益率") or _find_col(df_fin, "ROE")
    v = _latest_value(df_fin, col)
    if v is None:
        return _missing("ROE", threshold, "%")
    return {
        "name": "ROE",
        "value": v,
        "threshold": threshold,
        "pass": v >= threshold,
        "comment": f"{'达标' if v >= threshold else '未达标'}（阈值 {threshold}%）",
        "unit": "%",
    }


def calc_debt_ratio(df_fin: pd.DataFrame, threshold: float = 50.0) -> dict[str, Any]:
    """资产负债率 (最新报告期)。阈值默认 50%（越低越好）。"""
    col = _find_col(df_fin, "资产负债率")
    v = _latest_value(df_fin, col)
    if v is None:
        return _missing("资产负债率", threshold, "%")
    return {
        "name": "资产负债率",
        "value": v,
        "threshold": threshold,
        "pass": v <= threshold,
        "comment": f"{'健康' if v <= threshold else '偏高'}（阈值 {threshold}%）",
        "unit": "%",
    }


def calc_profit_cagr(df_fin: pd.DataFrame, years: int = 3, threshold: float = 10.0) -> dict[str, Any]:
    """近 N 年净利润复合增长率（取年报）。阈值默认 10%。

    仅使用 12 月份的年报。若不足 N+1 个年报，返回数据缺失。
    """
    col = _find_col(df_fin, "净利润") and _find_col(df_fin, "净利润")
    # 优先匹配「净利润(元)」, 避免误抓「净利润同比增长率」
    candidates = [c for c in df_fin.columns if "净利润" in c and "增长" not in c and "率" not in c]
    col = candidates[0] if candidates else None
    if col is None or df_fin.empty:
        return _missing(f"近{years}年净利润 CAGR", threshold, "%")

    df = df_fin.copy()
    df = df.dropna(subset=[col])
    # 仅取年报 (12 月)
    annual = df[df["报告期"].dt.month == 12].sort_values("报告期", ascending=False)
    if len(annual) < years + 1:
        return _missing(f"近{years}年净利润 CAGR", threshold, "%")

    latest = float(annual.iloc[0][col])
    earliest = float(annual.iloc[years][col])
    if earliest <= 0 or latest <= 0:
        return {
            "name": f"近{years}年净利润 CAGR",
            "value": None, "threshold": threshold, "pass": False,
            "comment": "存在亏损年度，CAGR 不适用",
            "unit": "%",
        }
    cagr = ((latest / earliest) ** (1 / years) - 1) * 100
    return {
        "name": f"近{years}年净利润 CAGR",
        "value": cagr,
        "threshold": threshold,
        "pass": cagr >= threshold,
        "comment": (
            f"{annual.iloc[years]['报告期'].year} → {annual.iloc[0]['报告期'].year} "
            f"年化 {cagr:.2f}%"
        ),
        "unit": "%",
    }


def calc_cashflow_quality(df_fin: pd.DataFrame, threshold: float = 0.5) -> dict[str, Any]:
    """经营性现金流 / 净利润 (最新报告期)。阈值默认 0.5。"""
    cf_col = _find_col(df_fin, "经营", "现金流")
    np_candidates = [c for c in df_fin.columns if "净利润" in c and "增长" not in c and "率" not in c]
    np_col = np_candidates[0] if np_candidates else None
    cf = _latest_value(df_fin, cf_col)
    np_ = _latest_value(df_fin, np_col)
    if cf is None or np_ is None or np_ == 0:
        return _missing("现金流质量 (经营现金流/净利润)", threshold, "倍")
    ratio = cf / np_
    return {
        "name": "现金流质量",
        "value": ratio,
        "threshold": threshold,
        "pass": ratio >= threshold,
        "comment": "利润含金量充足" if ratio >= threshold else "利润可能含较多应收账款",
        "unit": "倍",
    }


def calc_valuation(valuation: dict[str, Any], industry_pe: float | None) -> dict[str, Any]:
    """估值评估：与行业 PE 对比。

    valuation: data.fetcher.get_valuation 返回值, 含 pe_ttm
    industry_pe: 行业平均 PE
    """
    pe = valuation.get("pe_ttm") if valuation else None
    if pe is None or pe <= 0:
        return _missing("PE(TTM) vs 行业", industry_pe, "倍")
    if industry_pe is None or industry_pe <= 0:
        return {
            "name": "PE(TTM)",
            "value": pe,
            "threshold": None,
            "pass": pe < 50,  # 兜底：PE < 50 算合理
            "comment": "行业 PE 数据缺失，仅以绝对值评估",
            "unit": "倍",
        }
    return {
        "name": "PE(TTM) vs 行业",
        "value": pe,
        "threshold": industry_pe,
        "pass": pe <= industry_pe,
        "comment": f"{'低于' if pe <= industry_pe else '高于'}行业均值 {industry_pe:.2f}",
        "unit": "倍",
    }


# ----------------------------- 汇总 -----------------------------

def collect_all(
    df_fin: pd.DataFrame,
    valuation: dict[str, Any] | None,
    industry_pe: float | None,
) -> list[dict[str, Any]]:
    """计算全部基本面指标。"""
    return [
        calc_roe(df_fin),
        calc_debt_ratio(df_fin),
        calc_profit_cagr(df_fin, years=3),
        calc_cashflow_quality(df_fin),
        calc_valuation(valuation or {}, industry_pe),
    ]
