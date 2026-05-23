"""数值/百分比/货币格式化辅助。"""
from __future__ import annotations

import math


def fmt_pct(x: float | None, digits: int = 2) -> str:
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return "—"
    return f"{x * 100:.{digits}f}%" if abs(x) < 5 else f"{x:.{digits}f}%"


def fmt_num(x: float | None, digits: int = 2) -> str:
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return "—"
    return f"{x:,.{digits}f}"


def fmt_money(x: float | None) -> str:
    """以亿为单位展示大额数字。"""
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return "—"
    if abs(x) >= 1e8:
        return f"{x / 1e8:,.2f} 亿"
    if abs(x) >= 1e4:
        return f"{x / 1e4:,.2f} 万"
    return f"{x:,.2f}"


def pass_emoji(passed: bool) -> str:
    return "✅" if passed else "❌"
