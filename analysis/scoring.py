"""三步框架综合评分。

得分模型:
    fundamental_score (0-100): 5 项基本面指标各 20 分, pass 给满分, 否则按距离阈值衰减
    technical_score   (0-100): 周线趋势 40 分 + 信号 score 映射 60 分
    total_score = 0.6 * fundamental_score + 0.4 * technical_score
    verdict:
        ≥80  → 推荐关注
        60-79 → 观察
        <60   → 暂缓
"""
from __future__ import annotations

from typing import Any


def _item_score(item: dict[str, Any]) -> float:
    """单项基本面指标得分 (0-20)。"""
    if item.get("value") is None:
        return 0.0
    if item.get("pass"):
        return 20.0
    # 未通过 → 按偏离程度衰减; 阈值方向由 comment 隐含, 这里给固定半分
    return 10.0


def fundamental_score(items: list[dict[str, Any]]) -> float:
    if not items:
        return 0.0
    return sum(_item_score(it) for it in items) * (100 / (20 * len(items)))


def technical_score(weekly: dict[str, Any], signal: dict[str, Any]) -> float:
    score = 0.0
    trend = weekly.get("trend")
    if trend == "上行":
        score += 40
    elif trend == "盘整":
        score += 20
    elif trend == "数据不足":
        score += 10

    s = signal.get("score", 0) if signal else 0
    # signal.score 范围大约 [-6, +6] → 映射到 [0, 60]
    score += max(0.0, min(60.0, (s + 6) * 5))
    return min(score, 100.0)


def verdict_of(total: float) -> str:
    if total >= 80:
        return "推荐关注"
    if total >= 60:
        return "观察"
    return "暂缓"


def evaluate(
    fund_items: list[dict[str, Any]],
    weekly: dict[str, Any],
    signal: dict[str, Any],
    risks: list[str],
) -> dict[str, Any]:
    fs = fundamental_score(fund_items)
    ts = technical_score(weekly, signal)
    total = 0.6 * fs + 0.4 * ts
    return {
        "fundamental_score": round(fs, 1),
        "technical_score": round(ts, 1),
        "total_score": round(total, 1),
        "verdict": verdict_of(total),
        "signal": signal,
        "risks": risks,
    }
