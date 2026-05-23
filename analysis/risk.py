"""风险因子自动识别。

按 CLAUDE.md 要求, 任何分析报告必须列出至少 3 条核心风险。
不足 3 条时, 自动补充通用市场风险。
"""
from __future__ import annotations

from typing import Any

import pandas as pd

GENERIC_RISKS = [
    "市场系统性风险：A 股整体估值波动可能拖累个股表现",
    "行业周期风险：所处行业的供需周期可能进入下行阶段",
    "政策风险：监管政策调整可能改变行业竞争格局",
    "流动性风险：资金面收紧时中小盘股可能出现明显回撤",
]


def _find_col(df: pd.DataFrame, *keywords: str) -> str | None:
    for col in df.columns:
        if all(kw in col for kw in keywords):
            return col
    return None


def detect_risks(
    df_fin: pd.DataFrame,
    valuation: dict[str, Any] | None,
    industry_pe: float | None,
    info: dict[str, Any] | None = None,
) -> list[str]:
    """根据财务/估值数据识别风险，保证返回至少 3 条。"""
    risks: list[str] = []

    if df_fin is not None and not df_fin.empty:
        # 资产负债率过高
        col = _find_col(df_fin, "资产负债率")
        if col:
            v = df_fin.iloc[0][col]
            if pd.notna(v) and float(v) > 60:
                risks.append(f"高杠杆：资产负债率 {float(v):.1f}%，偿债压力偏大")

        # 现金流质量差
        cf_col = _find_col(df_fin, "经营", "现金流")
        np_col = next((c for c in df_fin.columns if "净利润" in c and "增长" not in c and "率" not in c), None)
        if cf_col and np_col:
            cf = df_fin.iloc[0][cf_col]
            np_ = df_fin.iloc[0][np_col]
            if pd.notna(cf) and pd.notna(np_) and float(np_) != 0:
                ratio = float(cf) / float(np_)
                if ratio < 0.5:
                    risks.append(
                        f"现金流质量差：经营现金流/净利润 = {ratio:.2f}，利润含金量低"
                    )

        # 营收下滑 (年报)
        rev_col = next((c for c in df_fin.columns if ("营业总收入" in c or "营业收入" in c) and "率" not in c and "增长" not in c), None)
        if rev_col:
            annual = df_fin[df_fin["报告期"].dt.month == 12].sort_values("报告期", ascending=False)
            if len(annual) >= 2:
                latest = annual.iloc[0][rev_col]
                prev = annual.iloc[1][rev_col]
                if pd.notna(latest) and pd.notna(prev) and float(prev) > 0:
                    growth = (float(latest) - float(prev)) / float(prev)
                    if growth < -0.05:
                        risks.append(
                            f"增长乏力：最近一期营收同比 {growth*100:.1f}%，业务承压"
                        )

        # 净利润亏损或大幅下滑
        if np_col:
            annual = df_fin[df_fin["报告期"].dt.month == 12].sort_values("报告期", ascending=False)
            if len(annual) >= 1:
                np_latest = annual.iloc[0][np_col]
                if pd.notna(np_latest) and float(np_latest) < 0:
                    risks.append("亏损警示：最近年报净利润为负")
                elif len(annual) >= 2:
                    np_prev = annual.iloc[1][np_col]
                    if pd.notna(np_prev) and float(np_prev) > 0:
                        d = (float(np_latest) - float(np_prev)) / float(np_prev)
                        if d < -0.3:
                            risks.append(f"利润下滑：年报净利润同比 {d*100:.1f}%")

    # 估值偏高
    if valuation:
        pe = valuation.get("pe_ttm")
        if pe is not None and pe > 0:
            if industry_pe and industry_pe > 0 and pe > industry_pe * 1.5:
                risks.append(
                    f"估值偏高：PE(TTM) {pe:.1f} 显著高于行业均值 {industry_pe:.1f}"
                )
            elif industry_pe is None and pe > 60:
                risks.append(f"估值偏高：PE(TTM) {pe:.1f} 处于绝对值高位")
        elif pe is not None and pe < 0:
            risks.append("估值预警：公司当前亏损，PE 为负，估值难以判断")

    # 兜底：补足至 3 条
    for generic in GENERIC_RISKS:
        if len(risks) >= 3:
            break
        if generic not in risks:
            risks.append(generic)

    return risks
