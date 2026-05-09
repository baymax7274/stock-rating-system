import logging
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

    def rate(self, code: str) -> RatingResult:
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
