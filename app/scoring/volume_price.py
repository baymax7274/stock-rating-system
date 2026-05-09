import pandas as pd
from app.models.schemas import SubDimension, ScoreItem


def score_volume_price(daily: pd.DataFrame, daily_basic) -> SubDimension:
    """量价关系评分 (满分20分)"""
    latest = daily.iloc[-1]
    pct_chg = float(latest["pct_chg"])

    # 1. 量比 (8分)
    volume_ratio = _safe_get(daily_basic, "volume_ratio")
    if volume_ratio is not None:
        if 1.5 <= volume_ratio <= 4:
            vr_score, vr_note = 8, f"量比{volume_ratio:.1f}，温和放量"
        elif volume_ratio < 1.5:
            vr_score, vr_note = 4, f"量比{volume_ratio:.1f}，缩量"
        elif volume_ratio > 4:
            vr_score, vr_note = 2, f"量比{volume_ratio:.1f}，异常放量"
        else:
            vr_score, vr_note = 4, "量比数据异常"
    else:
        vr_score, vr_note = 4, "量比数据缺失"

    # 2. 换手率 (6分)
    turnover = _safe_get(daily_basic, "turnover_rate")
    if turnover is not None:
        if 3 <= turnover <= 8:
            to_score, to_note = 6, f"换手率{turnover:.1f}%，健康"
        elif turnover < 3:
            to_score, to_note = 1, f"换手率{turnover:.1f}%，冷清"
        elif turnover > 12:
            to_score, to_note = 1, f"换手率{turnover:.1f}%，巨量分歧"
        else:
            to_score, to_note = 1, f"换手率{turnover:.1f}%，偏高"
    else:
        to_score, to_note = 1, "换手率数据缺失"

    # 3. 涨跌幅与量匹配度 (6分)
    is_up = pct_chg > 0.5
    is_down = pct_chg < -0.5
    is_volume_up = volume_ratio > 1.0 if volume_ratio is not None else False
    is_volume_down = volume_ratio < 1.0 if volume_ratio is not None else False

    if (is_up and is_volume_up) or (is_down and is_volume_down):
        match_score, match_note = 6, (
            "价涨量增，匹配良好" if is_up else "价跌量缩，匹配良好"
        )
    elif (not is_up and not is_down and is_volume_up):
        match_score, match_note = 1, "滞涨放量，量价背离"
    elif is_down and is_volume_up:
        match_score, match_note = 1, "下跌放量，量价背离"
    else:
        match_score, match_note = 3, f"量价关系一般(pct:{pct_chg:.1f}%)"

    total = vr_score + to_score + match_score
    return SubDimension(
        score=round(total, 1),
        max=20,
        items={
            "volume_ratio": ScoreItem(score=vr_score, max=8, note=vr_note),
            "turnover": ScoreItem(score=to_score, max=6, note=to_note),
            "price_volume_match": ScoreItem(score=match_score, max=6, note=match_note),
        },
    )


def _safe_get(df: pd.DataFrame, col: str):
    """安全获取DataFrame中最后一行的列值"""
    if df is None or df.empty or col not in df.columns:
        return None
    val = df.iloc[-1][col]
    try:
        return float(val)
    except (ValueError, TypeError):
        return None
