"""10 位投资大师视角评估 (本地规则引擎)。

输入约定 (ctx dict):
    fund_map: dict[name, item]  基本面指标 (来自 analysis.fundamental.collect_all)
        - 'ROE'                value=百分数, pass
        - '资产负债率'         value=百分数, pass
        - '近3年净利润 CAGR'   value=百分数, pass
        - '现金流质量'         value=倍数,  pass
        - 'PE(TTM) vs 行业' or 'PE(TTM)'  value=PE, pass
    valuation: {'pe_ttm', 'pb', 'total_mv'}
    industry_pe: float | None
    weekly_info: {'trend': '上行'|'下行'|'盘整'|'数据不足'}
    signal: {'signal', 'score', ...}
    df_fin: 财报 DataFrame (可能为空)

输出 (每位大师):
    {
        'master': str, 'school': str, 'philosophy': str,
        'score': int (1-5), 'verdict': '买入'|'观望'|'回避',
        'reasons': list[str], 'concerns': list[str],
    }
"""
from __future__ import annotations

from typing import Any

import pandas as pd


# ----------------------------- 工具 -----------------------------

def _get(ctx: dict, key: str, default=None):
    return (ctx.get("fund_map", {}).get(key, {}) or {}).get("value", default)


def _pe(ctx: dict) -> float | None:
    pe = (ctx.get("valuation") or {}).get("pe_ttm")
    return float(pe) if pe is not None and pe > 0 else None


def _pb(ctx: dict) -> float | None:
    pb = (ctx.get("valuation") or {}).get("pb")
    return float(pb) if pb is not None and pb > 0 else None


def _verdict(score: int) -> tuple[int, str]:
    """score → (stars 1-5, verdict)。"""
    if score >= 4:
        return 5, "买入"
    if score >= 2:
        return 4, "买入"
    if score >= 0:
        return 3, "观望"
    if score >= -2:
        return 2, "观望"
    return 1, "回避"


def _profit_trend(df_fin: pd.DataFrame | None) -> str:
    """简单判断年报净利润趋势: increasing / declining / mixed / unknown。"""
    if df_fin is None or df_fin.empty:
        return "unknown"
    col = next((c for c in df_fin.columns if "净利润" in c and "增长" not in c and "率" not in c), None)
    if not col:
        return "unknown"
    annual = df_fin[df_fin["报告期"].dt.month == 12].sort_values("报告期", ascending=True)
    series = annual[col].dropna().tolist()
    if len(series) < 3:
        return "unknown"
    diffs = [series[i] - series[i - 1] for i in range(1, len(series))]
    pos = sum(1 for d in diffs if d > 0)
    if pos == len(diffs):
        return "increasing"
    if pos == 0:
        return "declining"
    return "mixed"


# ----------------------------- 大师评估 -----------------------------

def graham(ctx: dict) -> dict[str, Any]:
    """格雷厄姆 - 防御型价值投资：低 PE + 低 PB + 安全边际。"""
    pe, pb = _pe(ctx), _pb(ctx)
    debt = _get(ctx, "资产负债率")
    score, reasons, concerns = 0, [], []

    if pe is not None:
        if pe < 15:
            score += 3; reasons.append(f"PE {pe:.1f} < 15 满足安全边际")
        elif pe < 20:
            score += 1; reasons.append(f"PE {pe:.1f} 处合理区间")
        elif pe > 30:
            score -= 2; concerns.append(f"PE {pe:.1f} 偏高，缺乏安全边际")
    if pb is not None:
        if pb < 1.5:
            score += 2; reasons.append(f"PB {pb:.2f} < 1.5 接近净资产")
        elif pb > 3:
            score -= 1; concerns.append(f"PB {pb:.2f} 偏高")
    if debt is not None:
        if debt < 50:
            score += 1; reasons.append(f"负债率 {debt:.1f}% 财务稳健")
        elif debt > 60:
            score -= 2; concerns.append(f"负债率 {debt:.1f}% 偏高")

    stars, v = _verdict(score)
    return {
        "master": "本杰明·格雷厄姆", "school": "防御型价值投资 (Defensive Value)",
        "philosophy": "买便宜的好公司：PE<15、PB<1.5、低负债，留足安全边际。",
        "score": stars, "verdict": v, "reasons": reasons or ["—"], "concerns": concerns or ["—"],
    }


def buffett(ctx: dict) -> dict[str, Any]:
    """巴菲特 - 价值投资 + 护城河 + 长期持股。"""
    roe = _get(ctx, "ROE")
    debt = _get(ctx, "资产负债率")
    cf = _get(ctx, "现金流质量")
    pe = _pe(ctx)
    score, reasons, concerns = 0, [], []

    if roe is not None:
        if roe >= 20:
            score += 3; reasons.append(f"ROE {roe:.1f}% 体现强护城河")
        elif roe >= 15:
            score += 2; reasons.append(f"ROE {roe:.1f}% 达标")
        elif roe < 10:
            score -= 2; concerns.append(f"ROE {roe:.1f}% 缺乏资本回报")
    if cf is not None:
        if cf >= 0.8:
            score += 2; reasons.append(f"经营现金流/净利润 = {cf:.2f}，利润含金量充足")
        elif cf < 0.5:
            score -= 2; concerns.append(f"现金流质量 {cf:.2f}，可能存在应收高企")
    if debt is not None:
        if debt < 50:
            score += 1; reasons.append(f"负债率 {debt:.1f}% 健康")
        elif debt > 60:
            score -= 2; concerns.append(f"负债率 {debt:.1f}% 不符稳健偏好")
    if pe is not None:
        if pe < 25:
            score += 1; reasons.append(f"PE {pe:.1f} 估值可接受")
        elif pe > 40:
            score -= 1; concerns.append(f"PE {pe:.1f} 偏离合理区间")

    stars, v = _verdict(score)
    return {
        "master": "沃伦·巴菲特", "school": "价值投资 + 护城河 + 长期持股",
        "philosophy": "以合理价格买入伟大公司，长期持有：高 ROE、低杠杆、强现金流、可理解的商业模式。",
        "score": stars, "verdict": v, "reasons": reasons or ["—"], "concerns": concerns or ["—"],
    }


def munger(ctx: dict) -> dict[str, Any]:
    """芒格 - 高质量企业 + 心智模型。"""
    roe = _get(ctx, "ROE")
    cagr = _get(ctx, "近3年净利润 CAGR")
    cf = _get(ctx, "现金流质量")
    pe = _pe(ctx)
    score, reasons, concerns = 0, [], []

    if roe is not None and roe >= 15:
        score += 2; reasons.append(f"ROE {roe:.1f}% 体现高资本效率")
    elif roe is not None:
        score -= 1; concerns.append(f"ROE {roe:.1f}% 不够优秀")
    if cagr is not None and cagr >= 10:
        score += 2; reasons.append(f"净利润 CAGR {cagr:.1f}% 持续成长")
    elif cagr is not None and cagr < 0:
        score -= 2; concerns.append("净利润 CAGR 为负，质量存疑")
    if cf is not None and cf >= 0.7:
        score += 1; reasons.append("现金流充裕")
    if pe is not None and pe > 40:
        score -= 1; concerns.append(f"PE {pe:.1f} 太贵, 宁愿等待")

    stars, v = _verdict(score)
    return {
        "master": "查理·芒格", "school": "高质量企业 + 多元思维模型",
        "philosophy": "买进可识别的高质量公司，宁愿付合理价格买卓越，也不要便宜的平庸。",
        "score": stars, "verdict": v, "reasons": reasons or ["—"], "concerns": concerns or ["—"],
    }


def duanyongping(ctx: dict) -> dict[str, Any]:
    """段永平 - 本分长期主义 + 商业模式。"""
    roe = _get(ctx, "ROE")
    cf = _get(ctx, "现金流质量")
    debt = _get(ctx, "资产负债率")
    trend = _profit_trend(ctx.get("df_fin"))
    score, reasons, concerns = 0, [], []

    if roe is not None and roe >= 15:
        score += 2; reasons.append(f"ROE {roe:.1f}% 表明盈利能力扎实")
    if cf is not None and cf >= 0.8:
        score += 2; reasons.append("利润有现金流支撑，符合「本分」要求")
    elif cf is not None and cf < 0.5:
        score -= 2; concerns.append("现金流偏弱，警惕账面利润失真")
    if debt is not None and debt < 50:
        score += 1; reasons.append("低负债，无生存压力")
    if trend == "increasing":
        score += 2; reasons.append("年报净利润持续增长，商业模式稳定")
    elif trend == "declining":
        score -= 3; concerns.append("利润持续下滑，违背长期主义")

    stars, v = _verdict(score)
    return {
        "master": "段永平", "school": "本分 + 长期主义",
        "philosophy": "做对的事，把事做对：选择简单可懂、能持续赚钱、不需要复杂判断的企业。",
        "score": stars, "verdict": v, "reasons": reasons or ["—"], "concerns": concerns or ["—"],
    }


def lynch(ctx: dict) -> dict[str, Any]:
    """彼得·林奇 - PEG 选股 + 业务可懂。"""
    pe = _pe(ctx)
    cagr = _get(ctx, "近3年净利润 CAGR")
    score, reasons, concerns = 0, [], []

    if pe is not None and cagr is not None and cagr > 0:
        peg = pe / cagr
        if peg < 0.5:
            score += 5; reasons.append(f"PEG {peg:.2f} 极低 (PE {pe:.1f} / CAGR {cagr:.1f}%)，明显低估的成长股")
        elif peg < 1:
            score += 3; reasons.append(f"PEG {peg:.2f} < 1 (PE {pe:.1f} / CAGR {cagr:.1f}%)，估值与成长匹配")
        elif peg < 1.5:
            score += 1; reasons.append(f"PEG {peg:.2f} 略偏高但可接受")
        elif peg > 2:
            score -= 2; concerns.append(f"PEG {peg:.2f} 估值远超成长性")
    elif cagr is not None and cagr <= 0:
        score -= 3; concerns.append("净利润 CAGR ≤ 0，不属于成长股范畴")
    if cagr is not None and cagr >= 20:
        score += 1; reasons.append(f"CAGR {cagr:.1f}% 属高速成长 (Fast Grower)")

    stars, v = _verdict(score)
    return {
        "master": "彼得·林奇", "school": "PEG 选股 + 业务可懂",
        "philosophy": "买你了解的东西：PEG<1 的成长股最有吸引力，业务越简单越好。",
        "score": stars, "verdict": v, "reasons": reasons or ["—"], "concerns": concerns or ["—"],
    }


def fisher(ctx: dict) -> dict[str, Any]:
    """费雪 - 优质成长股 + 长期持有。"""
    cagr = _get(ctx, "近3年净利润 CAGR")
    roe = _get(ctx, "ROE")
    cf = _get(ctx, "现金流质量")
    trend = _profit_trend(ctx.get("df_fin"))
    score, reasons, concerns = 0, [], []

    if cagr is not None:
        if cagr >= 25:
            score += 4; reasons.append(f"净利润 CAGR {cagr:.1f}% 高速成长")
        elif cagr >= 15:
            score += 2; reasons.append(f"CAGR {cagr:.1f}% 良好成长")
        elif cagr < 5:
            score -= 2; concerns.append(f"CAGR {cagr:.1f}% 偏低，不符成长股标准")
    if roe is not None and roe >= 15:
        score += 1; reasons.append("高 ROE 体现持续盈利能力")
    if cf is not None and cf >= 0.7:
        score += 1; reasons.append("现金流稳健")
    if trend == "declining":
        score -= 2; concerns.append("利润趋势恶化")

    stars, v = _verdict(score)
    return {
        "master": "菲利普·费雪", "school": "成长股投资 + 长期持有",
        "philosophy": "找到少数卓越的成长公司, 长期持有，不在意短期估值波动。",
        "score": stars, "verdict": v, "reasons": reasons or ["—"], "concerns": concerns or ["—"],
    }


def soros(ctx: dict) -> dict[str, Any]:
    """索罗斯 - 趋势 + 反身性 (主看技术面)。"""
    trend = (ctx.get("weekly_info") or {}).get("trend")
    sig = ctx.get("signal") or {}
    s = sig.get("score", 0)
    rsi = sig.get("rsi")
    score, reasons, concerns = 0, [], []

    if trend == "上行":
        score += 3; reasons.append("周线 MA20 上行，确认中期趋势")
    elif trend == "下行":
        score -= 3; concerns.append("周线 MA20 下行，趋势不利")
    if s >= 3:
        score += 2; reasons.append(f"日线综合信号 +{s}, 多头共振")
    elif s <= -3:
        score -= 2; concerns.append(f"日线信号 {s}, 空头共振")
    if rsi is not None:
        if rsi > 80:
            score -= 1; concerns.append(f"RSI {rsi:.0f} 超买, 反身性反转风险")
        elif rsi < 20:
            score += 1; reasons.append(f"RSI {rsi:.0f} 超卖, 可能拐点临近")

    stars, v = _verdict(score)
    return {
        "master": "乔治·索罗斯", "school": "趋势跟随 + 反身性理论",
        "philosophy": "趋势是朋友, 直到极端处反转。关键看大趋势与市场情绪的反身循环。",
        "score": stars, "verdict": v, "reasons": reasons or ["—"], "concerns": concerns or ["—"],
    }


def marks(ctx: dict) -> dict[str, Any]:
    """霍华德·马克斯 - 周期 + 逆向投资 + 风险优先。"""
    pe = _pe(ctx)
    ind_pe = ctx.get("industry_pe")
    roe = _get(ctx, "ROE")
    score, reasons, concerns = 0, [], []

    if pe is not None and ind_pe and ind_pe > 0:
        ratio = pe / ind_pe
        if ratio < 0.7:
            score += 3; reasons.append(f"PE {pe:.1f} 仅为行业均值 {ind_pe:.1f} 的 {ratio:.0%}, 周期低位机会")
        elif ratio < 0.9:
            score += 1; reasons.append(f"PE 较行业均值有 {(1-ratio)*100:.0f}% 折价")
        elif ratio > 1.3:
            score -= 2; concerns.append(f"PE 较行业溢价 {(ratio-1)*100:.0f}%, 估值不安全")
    elif pe is not None and pe < 15:
        score += 1; reasons.append(f"PE {pe:.1f} 绝对值较低")
    if roe is not None and roe > 0:
        score += 1; reasons.append("公司仍盈利, 不属周期底部困境股")
    elif roe is not None and roe <= 0:
        score -= 1; concerns.append("亏损公司, 周期反转需更长等待")

    stars, v = _verdict(score)
    return {
        "master": "霍华德·马克斯", "school": "周期 + 逆向 + 风险优先",
        "philosophy": "了解你在周期中的位置：在别人贪婪时谨慎，在别人恐惧时进取, 安全边际优先。",
        "score": stars, "verdict": v, "reasons": reasons or ["—"], "concerns": concerns or ["—"],
    }


def dalio(ctx: dict) -> dict[str, Any]:
    """达利欧 - 全天候 + 分散均衡 (偏中性)。"""
    roe = _get(ctx, "ROE")
    debt = _get(ctx, "资产负债率")
    cf = _get(ctx, "现金流质量")
    pe = _pe(ctx)
    score, reasons, concerns = 0, [], []

    healthy = []
    if roe is not None and roe >= 10: healthy.append("ROE")
    if debt is not None and debt < 60: healthy.append("负债率")
    if cf is not None and cf >= 0.3: healthy.append("现金流")
    if pe is not None and pe < 35: healthy.append("PE")
    score += len(healthy) - 2  # 4 项中达 3+ 项加分, ≤1 项减分

    if len(healthy) >= 3:
        reasons.append(f"核心指标 {len(healthy)}/4 健康，适合作为组合中均衡持仓")
    else:
        concerns.append(f"仅 {len(healthy)}/4 核心指标达标，配置权重应控制")
    if pe is not None and pe > 50:
        score -= 1; concerns.append("估值过高, 不符全天候稳健原则")
    if roe is not None and roe < 0:
        score -= 2; concerns.append("亏损公司不入选")

    stars, v = _verdict(score)
    return {
        "master": "瑞·达利欧", "school": "全天候 + 风险平价",
        "philosophy": "通过分散与均衡跨越所有经济环境, 单只标的健康度决定其权重。",
        "score": stars, "verdict": v, "reasons": reasons or ["—"], "concerns": concerns or ["—"],
    }


def simons(ctx: dict) -> dict[str, Any]:
    """西蒙斯 - 量化 + 纯技术信号 (复刻技术面打分)。"""
    sig = ctx.get("signal") or {}
    s = sig.get("score", 0)
    trend = (ctx.get("weekly_info") or {}).get("trend")
    score, reasons, concerns = 0, [], []

    score += s  # 直接映射技术 score
    reasons.append(f"量化综合 score = {s} (RSI+MACD+周线 加权)")
    if trend == "上行":
        score += 1; reasons.append("周线趋势上行, 因子环境友好")
    elif trend == "下行":
        score -= 1; concerns.append("周线趋势下行, 因子环境不利")

    stars, v = _verdict(score)
    return {
        "master": "詹姆斯·西蒙斯", "school": "量化交易 + 纯模型驱动",
        "philosophy": "不预测公司, 只跟随数据：技术信号与因子打分给出统计意义上的优势。",
        "score": stars, "verdict": v, "reasons": reasons or ["—"], "concerns": concerns or ["—"],
    }


# ----------------------------- 入口 -----------------------------

MASTERS = [graham, buffett, munger, duanyongping, lynch, fisher, soros, marks, dalio, simons]


def evaluate_all(
    fund_items: list[dict],
    valuation: dict | None,
    industry_pe: float | None,
    weekly_info: dict,
    signal: dict,
    df_fin: "pd.DataFrame | None" = None,
) -> list[dict[str, Any]]:
    """计算 10 位大师对当前股票的视角。"""
    ctx = {
        "fund_map": {it["name"]: it for it in (fund_items or [])},
        "valuation": valuation or {},
        "industry_pe": industry_pe,
        "weekly_info": weekly_info or {},
        "signal": signal or {},
        "df_fin": df_fin,
    }
    return [m(ctx) for m in MASTERS]


def consensus(views: list[dict]) -> dict[str, Any]:
    """10 位大师的共识汇总。"""
    if not views:
        return {"avg_score": 0, "verdict": "—", "buy": 0, "watch": 0, "avoid": 0}
    buy = sum(1 for v in views if v["verdict"] == "买入")
    watch = sum(1 for v in views if v["verdict"] == "观望")
    avoid = sum(1 for v in views if v["verdict"] == "回避")
    avg = sum(v["score"] for v in views) / len(views)
    if avg >= 4:
        verdict = "多数大师推荐"
    elif avg >= 3:
        verdict = "中性偏多"
    elif avg >= 2:
        verdict = "中性偏空"
    else:
        verdict = "多数大师回避"
    return {"avg_score": round(avg, 2), "verdict": verdict, "buy": buy, "watch": watch, "avoid": avoid}
