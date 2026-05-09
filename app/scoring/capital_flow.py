import pandas as pd
import numpy as np
from app.models.schemas import SubDimension, ScoreItem


def score_capital_flow(moneyflow) -> SubDimension:
    """大单净量与资金评分 (满分15分)"""
    if moneyflow is None or moneyflow.empty or "net_mf_vol" not in moneyflow.columns:
        return SubDimension(
            score=4, max=15,
            items={
                "daily_net": ScoreItem(score=4, max=8, note="资金流向数据缺失"),
                "trend": ScoreItem(score=0, max=4, note="数据缺失"),
                "ma_compare": ScoreItem(score=0, max=3, note="数据缺失"),
            },
        )

    net_vols = moneyflow["net_mf_vol"].values

    # 1. 当日大单净量为正 (8分)
    latest_net = net_vols[-1] if len(net_vols) > 0 else 0
    if latest_net > 0:
        daily_score, daily_note = 8, "当日大单净量为正"
    else:
        daily_score, daily_note = 0, "当日大单净量为负"

    # 2. 5日均值大单净量方向 (4分)
    if len(net_vols) >= 5:
        recent_5 = net_vols[-5:]
        positive_streak = 0
        for v in reversed(recent_5):
            if v > 0:
                positive_streak += 1
            else:
                break
        if positive_streak >= 2:
            trend_score, trend_note = 4, f"大单连续{positive_streak}天为正"
        elif positive_streak == 1:
            trend_score, trend_note = 2, "大单走平"
        else:
            trend_score, trend_note = 0, "大单方向转负"
    else:
        trend_score, trend_note = 2, "数据不足"

    # 3. MA5与MA10大单净量比较 (3分)
    if len(net_vols) >= 10:
        ma5 = np.mean(net_vols[-5:])
        ma10 = np.mean(net_vols[-10:])
        if ma5 > ma10:
            ma_score, ma_note = 3, "MA5 > MA10，资金趋势向好"
        else:
            ma_score, ma_note = 0, "MA5 <= MA10，资金趋势偏弱"
    elif len(net_vols) >= 5:
        ma_score, ma_note = 0, "数据不足(需10日)"
    else:
        ma_score, ma_note = 0, "数据不足"

    total = daily_score + trend_score + ma_score
    return SubDimension(
        score=round(total, 1),
        max=15,
        items={
            "daily_net": ScoreItem(score=daily_score, max=8, note=daily_note),
            "trend": ScoreItem(score=trend_score, max=4, note=trend_note),
            "ma_compare": ScoreItem(score=ma_score, max=3, note=ma_note),
        },
    )
