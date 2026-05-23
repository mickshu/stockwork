"""输入与数据校验工具。"""
from __future__ import annotations

import re
import warnings

import numpy as np
import pandas as pd

A_SHARE_CODE = re.compile(r"^(?:sh|sz)?\d{6}$", re.IGNORECASE)


def normalize_symbol(symbol: str) -> str:
    """将用户输入的股票代码标准化为 6 位数字（去除 sh/sz 前缀）。

    >>> normalize_symbol(' SH600519 ')
    '600519'
    """
    s = symbol.strip().lower().replace("sh", "").replace("sz", "")
    if not s.isdigit() or len(s) != 6:
        raise ValueError(f"非法 A 股代码: {symbol!r}（应为 6 位数字，可选 sh/sz 前缀）")
    return s


def is_valid_symbol(symbol: str) -> bool:
    return bool(A_SHARE_CODE.match(symbol.strip()))


def check_price_series(df: pd.DataFrame, price_cols=("open", "high", "low", "close")) -> list[str]:
    """检测价格序列中的 NaN/Inf/非正值，返回警告信息列表（同时通过 warnings 模块发出）。

    输入 DataFrame 需含 price_cols 中的列。返回的字符串可由调用方在 UI 中渲染。
    """
    issues: list[str] = []
    for col in price_cols:
        if col not in df.columns:
            continue
        series = df[col]
        n_nan = int(series.isna().sum())
        n_inf = int(np.isinf(series.replace([np.inf, -np.inf], np.nan).fillna(0)).sum())  # noqa: E501
        n_nonpos = int((series.dropna() <= 0).sum())
        if n_nan:
            msg = f"列 {col} 含 {n_nan} 个 NaN"
            issues.append(msg)
            warnings.warn(msg)
        if n_inf:
            msg = f"列 {col} 含 {n_inf} 个 Inf"
            issues.append(msg)
            warnings.warn(msg)
        if n_nonpos:
            msg = f"列 {col} 含 {n_nonpos} 个 ≤0 的异常值"
            issues.append(msg)
            warnings.warn(msg)
    return issues


def clean_price_df(df: pd.DataFrame) -> pd.DataFrame:
    """删除关键价格列含 NaN/Inf 的行，按 date 升序排序。"""
    df = df.replace([np.inf, -np.inf], np.nan)
    df = df.dropna(subset=[c for c in ("open", "high", "low", "close") if c in df.columns])
    if "date" in df.columns:
        df = df.sort_values("date").reset_index(drop=True)
    return df
