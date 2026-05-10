import logging
from typing import Optional
import numpy as np
from app.data.akshare_client import AkshareClient
from app.scoring.ma_system import score_ma_system
from app.scoring.macd import score_macd
from app.scoring.volume_price import score_volume_price
from app.scoring.capital_flow import score_capital_flow
from app.scoring.chip_distribution import score_chip_distribution
from app.models.schemas import RatingResult, RatingDetails, SubDimension, ScoreItem

logger = logging.getLogger(__name__)


class ScoringEngine:
    def __init__(self):
        self.client = AkshareClient()

    def rate(self, code: str, strategy_id: Optional[str] = None,
             strategy_name: Optional[str] = None,
             strategy_prompt: Optional[str] = None) -> RatingResult:
        """获取股票评分，支持可选 AI 策略

        Args:
            code: 股票代码
            strategy_id: AI 策略ID，传入则走 DeepSeek 评分通道
            strategy_name: AI 策略名称
            strategy_prompt: AI 策略的自然语言描述
        """
        if strategy_id and strategy_prompt:
            return self._ai_rate(code, strategy_id, strategy_name or "", strategy_prompt)
        return self._rule_rate(code)

    def _rule_rate(self, code: str) -> RatingResult:
        stock_name = self.client.get_stock_name(code)

        # 获取日线数据（均线和MACD共用）
        try:
            daily = self.client.get_daily(code)
            trade_date = str(daily.iloc[-1]["trade_date"])
        except Exception as e:
            raise ValueError(f"获取日线数据失败: {e}")

        # 均线结构
        ma_result = score_ma_system(daily)

        # MACD动能
        macd_result = score_macd(daily)

        # 量价关系
        try:
            daily_basic = self.client.get_daily_basic(code)
        except Exception as e:
            logger.warning(f"获取每日指标失败: {e}")
            daily_basic = None
        vp_result = score_volume_price(daily, daily_basic)

        # 大单净量
        try:
            moneyflow = self.client.get_moneyflow(code)
        except Exception as e:
            logger.warning(f"获取资金流向失败: {e}")
            moneyflow = None
        cf_result = score_capital_flow(moneyflow)

        # 筹码分布
        try:
            cyq_perf = self.client.get_cyq_perf(code)
            concentration = self.client.get_chip_concentration(code)
        except Exception as e:
            logger.warning(f"获取筹码数据失败: {e}")
            cyq_perf = None
            concentration = 20.0
        close_price = float(daily.iloc[-1]["close"])
        cd_result = score_chip_distribution(cyq_perf, close_price, concentration)

        # 汇总
        details = RatingDetails(
            ma_structure=ma_result,
            macd=macd_result,
            volume_price=vp_result,
            capital_flow=cf_result,
            chip_distribution=cd_result,
        )

        total_score = sum([
            ma_result.score,
            macd_result.score,
            vp_result.score,
            cf_result.score,
            cd_result.score,
        ])

        grade = self._grade(total_score)
        morphology = self._describe_morphology(details, total_score, grade)

        display_code = self.client.format_code(code)

        return RatingResult(
            stock_code=display_code,
            stock_name=stock_name,
            trade_date=trade_date,
            total_score=round(total_score, 1),
            max_score=100,
            grade=grade,
            morphology=morphology,
            details=details,
        )

    def _ai_rate(self, code: str, strategy_id: str,
                 strategy_name: str, strategy_prompt: str) -> RatingResult:
        """DeepSeek AI 评分通道"""
        from app.ai.deepseek_client import DeepSeekClient

        stock_name = self.client.get_stock_name(code)
        display_code = self.client.format_code(code)

        # 获取原始数据
        raw = self._gather_raw_data(code, stock_name, display_code)

        # 调用 DeepSeek
        ai_client = DeepSeekClient()
        ai_result = ai_client.rate_stock(raw, strategy_prompt)

        # 构建 RatingResult
        return self._build_ai_result(ai_result, display_code, stock_name,
                                     raw["trade_date"], strategy_name)

    def _gather_raw_data(self, code: str, stock_name: str,
                         display_code: str) -> dict:
        """收集个股原始技术数据，供 DeepSeek 分析"""
        daily = self.client.get_daily(code)
        trade_date = str(daily.iloc[-1]["trade_date"])
        latest_close = float(daily.iloc[-1]["close"])
        pct_chg_val = float(daily.iloc[-1].get("pct_chg", 0)) if "pct_chg" in daily.columns else 0

        closes = daily["close"].values.astype(float)

        # 均线数据
        ma_data = {}
        for p in [5, 10, 20, 30, 60]:
            if len(closes) >= p:
                ma_data[f"MA{p}"] = round(float(np.mean(closes[-p:])), 2)
        ma_data["close"] = round(latest_close, 2)

        # MACD 原始数据
        from app.scoring.macd import _calc_ema
        from app.config import MACD_FAST, MACD_SLOW, MACD_SIGNAL
        ema_fast = _calc_ema(closes, MACD_FAST)
        ema_slow = _calc_ema(closes, MACD_SLOW)
        diff_arr = ema_fast - ema_slow
        dea_arr = _calc_ema(diff_arr, MACD_SIGNAL)
        macd_bar = 2 * (diff_arr - dea_arr)
        cross_note = "无"
        # 检测最近交叉
        for i in range(len(diff_arr) - 1, max(0, len(diff_arr) - 20), -1):
            if np.isnan(diff_arr[i]) or np.isnan(dea_arr[i]):
                continue
            if i > 0 and not np.isnan(diff_arr[i-1]) and not np.isnan(dea_arr[i-1]):
                if diff_arr[i-1] <= dea_arr[i-1] and diff_arr[i] > dea_arr[i]:
                    cross_note = "近期金叉"
                    break
                elif diff_arr[i-1] >= dea_arr[i-1] and diff_arr[i] < dea_arr[i]:
                    cross_note = "近期死叉"
                    break

        macd_data = {
            "diff": round(float(diff_arr[-1]), 4) if not np.isnan(diff_arr[-1]) else 0,
            "dea": round(float(dea_arr[-1]), 4) if not np.isnan(dea_arr[-1]) else 0,
            "macd": round(float(macd_bar[-1]), 4) if not np.isnan(macd_bar[-1]) else 0,
            "crossover": cross_note,
        }

        # 量价数据
        vp_data = {}
        try:
            daily_basic = self.client.get_daily_basic(code)
            if daily_basic is not None and len(daily_basic) > 0:
                last = daily_basic.iloc[-1]
                vr = last.get("volume_ratio", 1.0)
                tr = last.get("turnover_rate", 0)
                vol_val = last.get("vol", 0)
                vp_data = {
                    "volume_ratio": round(float(vr), 2) if not (isinstance(vr, float) and np.isnan(vr)) else 1.0,
                    "turnover_rate": round(float(tr), 2) if not (isinstance(tr, float) and np.isnan(tr)) else 0,
                    "vol": int(float(vol_val)) if not (isinstance(vol_val, float) and np.isnan(vol_val)) else 0,
                }
        except Exception:
            vp_data = {"volume_ratio": 1.0, "turnover_rate": 0, "vol": 0}

        # 资金流向数据
        cf_data = {}
        try:
            moneyflow = self.client.get_moneyflow(code)
            if moneyflow is not None and len(moneyflow) > 0:
                net_vals = moneyflow["net_mf_vol"].values
                latest_net = float(net_vals[-1])
                # 判断5日趋势
                if len(net_vals) >= 5:
                    recent = net_vals[-5:]
                    positive_days = sum(1 for v in recent if v > 0)
                    trend = f"近5日{positive_days}天净流入" if positive_days >= 3 else (
                        f"近5日{5-positive_days}天净流出")
                else:
                    trend = "数据不足"
                cf_data = {
                    "net_mf_vol": round(latest_net, 2),
                    "trend": trend,
                }
        except Exception:
            cf_data = {"net_mf_vol": 0, "trend": "无数据"}

        # 筹码数据
        chip_data = {}
        try:
            cyq_perf = self.client.get_cyq_perf(code)
            concentration = self.client.get_chip_concentration(code)
            if cyq_perf is not None and len(cyq_perf) > 0:
                last = cyq_perf.iloc[-1]
                chip_data = {
                    "winner_pct": round(float(last.get("winner_pct", 50)), 1),
                    "cost_avg": round(float(last.get("cost_avg", latest_close)), 2),
                    "concentration": round(float(concentration), 1),
                }
        except Exception:
            chip_data = {"winner_pct": 50, "cost_avg": round(latest_close, 2), "concentration": 20}

        return {
            "stock_name": stock_name,
            "stock_code": display_code,
            "trade_date": trade_date,
            "close": round(latest_close, 2),
            "pct_chg": round(pct_chg_val, 2),
            "ma_data": ma_data,
            "macd_data": macd_data,
            "volume_price_data": vp_data,
            "capital_flow_data": cf_data,
            "chip_data": chip_data,
        }

    def _build_ai_result(self, ai_result: dict, display_code: str,
                         stock_name: str, trade_date: str,
                         strategy_name: str) -> RatingResult:
        """将 DeepSeek 返回的 JSON 构建为 RatingResult"""
        details_raw = ai_result.get("details", {})

        def _make_sub(key: str, default_max: int) -> SubDimension:
            d = details_raw.get(key, {})
            items = {}
            for item_key in (d if isinstance(d, dict) else {}):
                if item_key in ("score", "max"):
                    continue
                item_val = d[item_key]
                if isinstance(item_val, dict):
                    items[item_key] = ScoreItem(
                        score=float(item_val.get("score", 0)),
                        max=int(item_val.get("max", default_max)),
                        note=str(item_val.get("note", "")),
                    )
            # 如果DeepSeek没返回详细items，构造一个默认的
            if not items:
                items["score"] = ScoreItem(
                    score=float(d.get("score", 0)) if isinstance(d, dict) else 0,
                    max=int(d.get("max", default_max)) if isinstance(d, dict) else default_max,
                    note=str(d.get("note", "")) if isinstance(d, dict) else "",
                )
            return SubDimension(
                score=float(d.get("score", 0)) if isinstance(d, dict) else 0,
                max=int(d.get("max", default_max)) if isinstance(d, dict) else default_max,
                items=items,
            )

        details = RatingDetails(
            ma_structure=_make_sub("ma_structure", 25),
            macd=_make_sub("macd", 20),
            volume_price=_make_sub("volume_price", 20),
            capital_flow=_make_sub("capital_flow", 15),
            chip_distribution=_make_sub("chip_distribution", 20),
        )

        total = float(ai_result.get("total_score", 0))
        grade = str(ai_result.get("grade", self._grade(total)))
        morphology = str(ai_result.get("morphology", ""))
        ai_analysis = str(ai_result.get("ai_analysis", ""))

        return RatingResult(
            stock_code=display_code,
            stock_name=stock_name,
            trade_date=trade_date,
            total_score=round(total, 1),
            max_score=100,
            grade=grade,
            morphology=morphology,
            details=details,
            ai_analysis=ai_analysis,
            strategy_name=strategy_name if strategy_name else None,
        )

    def _grade(self, score: float) -> str:
        if score >= 85:
            return "A"
        elif score >= 70:
            return "B"
        elif score >= 50:
            return "C"
        elif score >= 30:
            return "D"
        else:
            return "E"

    def _describe_morphology(self, d: RatingDetails, total: float, grade: str) -> str:
        """基于评分结果生成形态特征描述"""
        parts = []

        # 均线结构判断
        ma = d.ma_structure
        if ma.items["alignment"].score >= 7.5:
            parts.append("均线多头排列")
        elif ma.items["alignment"].score <= 2.5:
            parts.append("均线空头排列")

        if ma.items["price_position"].score >= 6:
            parts.append("股价站稳均线上方")
        elif ma.items["price_position"].score <= 2:
            parts.append("股价疲弱")

        # MACD判断
        macd = d.macd
        cross_note = macd.items["crossover"].note
        if "金叉" in cross_note:
            parts.append("MACD金叉信号")
        elif "死叉" in cross_note:
            parts.append("MACD死叉信号")

        if macd.items["bar_color"].score == 6:
            parts.append("红柱动能持续")

        # 量价判断
        vp = d.volume_price
        if "背离" in vp.items["price_volume_match"].note:
            parts.append("量价背离需警惕")
        elif "匹配良好" in vp.items["price_volume_match"].note:
            parts.append("量价配合良好")

        if "异常放量" in vp.items["volume_ratio"].note:
            parts.append("异常放量有出货嫌疑")
        elif "缩量" in vp.items["volume_ratio"].note:
            parts.append("缩量观望")

        # 资金判断
        cf = d.capital_flow
        if cf.items["daily_net"].score == 8:
            parts.append("主力资金净流入")
        elif cf.items["daily_net"].score == 0 and "为负" in cf.items["daily_net"].note:
            parts.append("主力资金流出")

        # 筹码判断
        cd = d.chip_distribution
        if cd.items["winner_pct"].score >= 7:
            parts.append("筹码结构优良")
        elif cd.items["winner_pct"].score <= 1 and cd.items["winner_pct"].max == 7:
            parts.append("上方抛压沉重")
        if "套牢" in cd.items["cost_gap"].note:
            parts.append("平均成本高于现价")

        # 综合判断
        if not parts:
            parts.append("技术面信号不明确")

        if total >= 85:
            parts.append("动能充沛，强势格局")
        elif total >= 70:
            parts.append("动能积蓄期，可关注")
        elif total >= 50:
            parts.append("方向不明，观望为主")
        elif total >= 30:
            parts.append("弱势特征明显，注意风险")
        else:
            parts.append("明显弱势，回避为宜")

        return "；".join(parts[:5])  # 最多5句，避免过长
