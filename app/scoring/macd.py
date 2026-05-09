import pandas as pd
import numpy as np
from app.models.schemas import SubDimension, ScoreItem
from app.config import MACD_FAST, MACD_SLOW, MACD_SIGNAL


def _calc_ema(data: np.ndarray, period: int) -> np.ndarray:
    """计算EMA，跳过前导NaN"""
    result = np.full_like(data, np.nan, dtype=float)
    # 找到第一个有效数据段
    valid_mask = ~np.isnan(data)
    valid_indices = np.where(valid_mask)[0]
    if len(valid_indices) < period:
        return result
    # 从第一个有效段中取period个值做初始SMA
    start = valid_indices[period - 1]
    result[start] = np.mean(data[start - period + 1: start + 1])
    multiplier = 2 / (period + 1)
    for i in range(start + 1, len(data)):
        if np.isnan(data[i]):
            result[i] = result[i - 1]
        else:
            result[i] = (data[i] - result[i - 1]) * multiplier + result[i - 1]
    return result


def score_macd(daily: pd.DataFrame) -> SubDimension:
    """MACD动能评分 (满分20分)"""
    closes = daily["close"].values
    ema_fast = _calc_ema(closes, MACD_FAST)
    ema_slow = _calc_ema(closes, MACD_SLOW)
    diff = ema_fast - ema_slow
    dea = _calc_ema(diff, MACD_SIGNAL)
    macd_bar = 2 * (diff - dea)  # MACD柱

    latest_diff = diff[-1]
    latest_dea = dea[-1]
    latest_bar = macd_bar[-1]

    if np.isnan(latest_diff) or np.isnan(latest_dea):
        return SubDimension(
            score=0, max=20,
            items={
                "diff_position": ScoreItem(score=0, max=8, note="数据不足"),
                "bar_color": ScoreItem(score=0, max=6, note="数据不足"),
                "crossover": ScoreItem(score=0, max=6, note="数据不足"),
            },
        )

    # 1. DIFF是否在DEA上方 (8分)
    diff_score = 8 if latest_diff > latest_dea else 0
    diff_note = "DIFF在DEA上方" if diff_score == 8 else "DIFF在DEA下方"

    # 2. MACD柱颜色 (6分)
    bar_score = 6 if latest_bar > 0 else 0
    bar_note = "红柱" if bar_score == 6 else "绿柱"

    # 3. 金叉/死叉判断 (6分)
    # 检测最近一次交叉
    cross_score, cross_note = _detect_crossover(diff, dea)

    total = diff_score + bar_score + cross_score
    return SubDimension(
        score=round(total, 1),
        max=20,
        items={
            "diff_position": ScoreItem(score=diff_score, max=8, note=diff_note),
            "bar_color": ScoreItem(score=bar_score, max=6, note=bar_note),
            "crossover": ScoreItem(score=cross_score, max=6, note=cross_note),
        },
    )


def _detect_crossover(diff: np.ndarray, dea: np.ndarray) -> tuple:
    """检测最近的金叉/死叉及其位置"""
    # 找最近10个交易日的交叉信号
    lookback = min(20, len(diff) - 1)
    for i in range(len(diff) - 1, len(diff) - lookback - 1, -1):
        if np.isnan(diff[i]) or np.isnan(dea[i]):
            continue
        prev_diff, prev_dea = diff[i - 1], dea[i - 1]
        curr_diff, curr_dea = diff[i], dea[i]
        if np.isnan(prev_diff) or np.isnan(prev_dea):
            continue

        # 金叉: DIFF从下方向上穿越DEA
        if prev_diff <= prev_dea and curr_diff > curr_dea:
            if curr_diff > 0:
                return 6, "零轴上方金叉"
            else:
                return 3, "零轴下方金叉"

        # 死叉: DIFF从上方向下穿越DEA
        if prev_diff >= prev_dea and curr_diff < curr_dea:
            if curr_diff > 0:
                return 1, "零轴上方死叉"
            else:
                return 0, "零轴下方死叉"

    # 未找到明确交叉，根据当前位置判断
    if diff[-1] > dea[-1]:
        return 3, "近期无交叉(DIFF在上)"
    else:
        return 1, "近期无交叉(DIFF在下)"
