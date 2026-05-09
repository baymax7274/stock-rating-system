import pandas as pd
import numpy as np
from app.models.schemas import SubDimension, ScoreItem


def score_ma_system(daily: pd.DataFrame) -> SubDimension:
    """均线结构评分 (满分25分)"""
    closes = daily["close"].values
    m5 = pd.Series(closes).rolling(5).mean().values
    m10 = pd.Series(closes).rolling(10).mean().values
    m20 = pd.Series(closes).rolling(20).mean().values
    m30 = pd.Series(closes).rolling(30).mean().values

    latest_close = closes[-1]
    latest_m5, latest_m10 = m5[-1], m10[-1]
    latest_m20, latest_m30 = m20[-1], m30[-1]

    # 1. 多头排列: M5 > M10 > M20 > M30 (10分)
    ma_order = [latest_m5, latest_m10, latest_m20, latest_m30]
    misplacements = sum(1 for i in range(len(ma_order) - 1) if ma_order[i] <= ma_order[i + 1])
    alignment_score = max(0, 10 - misplacements * 2.5)
    alignment_note = (
        "完美多头排列" if misplacements == 0
        else f"{misplacements}条均线错位"
    )

    # 2. 股价站上均线 (8分)
    mas = {"M5": latest_m5, "M10": latest_m10, "M20": latest_m20, "M30": latest_m30}
    below_count = sum(1 for v in mas.values() if latest_close < v)
    price_pos_score = max(0, 8 - below_count * 2)
    below_names = [k for k, v in mas.items() if latest_close < v]
    price_pos_note = (
        "站上所有均线" if below_count == 0
        else f"跌破{', '.join(below_names)}"
    )

    # 3. M20斜率 (4分)
    if len(m20) >= 6:
        m20_slope = (m20[-1] - m20[-6]) / 6
        m20_threshold = latest_m20 * 0.001
        if m20_slope > m20_threshold:
            slope_score, slope_note = 4, "M20斜率向上"
        elif m20_slope > -m20_threshold:
            slope_score, slope_note = 2, "M20平移"
        else:
            slope_score, slope_note = 0, "M20下弯"
    else:
        slope_score, slope_note = 2, "数据不足，默认平移"

    # 4. M5与M10正开口 (3分)
    if not np.isnan(latest_m5) and not np.isnan(latest_m10):
        gap = (latest_m5 - latest_m10) / latest_m10
        # 正开口：M5 > M10 且差距>0.5% (非黏合)
        if gap > 0.005:
            opening_score, opening_note = 3, "M5与M10正开口"
        elif gap > -0.005:
            opening_score, opening_note = 0, "M5与M10黏合"
        else:
            opening_score, opening_note = 0, "M5与M10死叉"
    else:
        opening_score, opening_note = 0, "数据不足"

    total = alignment_score + price_pos_score + slope_score + opening_score
    return SubDimension(
        score=round(total, 1),
        max=25,
        items={
            "alignment": ScoreItem(score=round(alignment_score, 1), max=10, note=alignment_note),
            "price_position": ScoreItem(score=round(price_pos_score, 1), max=8, note=price_pos_note),
            "slope": ScoreItem(score=slope_score, max=4, note=slope_note),
            "opening": ScoreItem(score=opening_score, max=3, note=opening_note),
        },
    )
