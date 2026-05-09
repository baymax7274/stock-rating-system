import pandas as pd
from app.models.schemas import SubDimension, ScoreItem


def score_chip_distribution(
    cyq_perf, close_price: float, concentration: float
) -> SubDimension:
    """筹码分布评分 (满分20分)"""
    if cyq_perf is None or (hasattr(cyq_perf, 'empty') and cyq_perf.empty):
        return SubDimension(
            score=3, max=20,
            items={
                "winner_pct": ScoreItem(score=2, max=7, note="筹码数据缺失"),
                "cost_gap": ScoreItem(score=0, max=7, note="数据缺失"),
                "concentration": ScoreItem(score=1, max=6, note="数据缺失"),
            },
        )

    latest = cyq_perf.iloc[-1]

    # 1. 收盘获利比例 (7分)
    winner_pct = _safe_float(latest, "winner_pct")
    if winner_pct is not None:
        if winner_pct > 70:
            wp_score, wp_note = 7, f"获利比例{winner_pct:.0f}%，筹码结构好"
        elif winner_pct >= 40:
            wp_score, wp_note = 4, f"获利比例{winner_pct:.0f}%，结构一般"
        else:
            wp_score, wp_note = 1, f"获利比例{winner_pct:.0f}%，上方抛压重"
    else:
        wp_score, wp_note = 2, "获利比例数据缺失"

    # 2. 平均成本与现价差距 (7分)
    cost_avg = _safe_float(latest, "cost_avg")
    if cost_avg is not None and cost_avg > 0 and close_price > 0:
        cost_gap_pct = (close_price - cost_avg) / cost_avg * 100
        if cost_gap_pct > 8:
            cg_score, cg_note = 7, f"成本低于现价{cost_gap_pct:.0f}%，安全边际充足"
        elif cost_gap_pct >= 0:
            cg_score, cg_note = 3, f"成本低于现价{cost_gap_pct:.0f}%，安全边际一般"
        else:
            cg_score, cg_note = 0, f"平均成本高于现价{cost_gap_pct:.0f}%，套牢状态"
    else:
        cg_score, cg_note = 0, "平均成本数据缺失"

    # 3. 筹码集中度 (6分)
    if concentration < 10:
        conc_score, conc_note = 6, f"集中度{concentration:.1f}%，高度集中"
    elif concentration < 15:
        conc_score, conc_note = 3, f"集中度{concentration:.1f}%，中度集中"
    else:
        conc_score, conc_note = 1, f"集中度{concentration:.1f}%，分散"

    total = wp_score + cg_score + conc_score
    return SubDimension(
        score=round(total, 1),
        max=20,
        items={
            "winner_pct": ScoreItem(score=wp_score, max=7, note=wp_note),
            "cost_gap": ScoreItem(score=cg_score, max=7, note=cg_note),
            "concentration": ScoreItem(score=conc_score, max=6, note=conc_note),
        },
    )


def _safe_float(row, col: str):
    val = row.get(col)
    if val is None:
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None
