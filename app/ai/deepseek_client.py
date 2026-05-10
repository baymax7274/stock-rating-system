"""DeepSeek API 客户端 — 使用 OpenAI 兼容接口"""
import json
import logging
import re
from openai import OpenAI
from app.config import DEEPSEEK_API_KEY

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """你是一位A股技术面分析师。用户会提供一只股票的技术数据和自定义评分标准，你需要根据用户的评分标准对股票进行打分。

评分框架包含五个维度（你可以根据用户策略调整权重侧重）：

1. **均线结构（默认25分）**：均线多头/空头排列、股价与均线关系、均线斜率、均线开口
2. **MACD动能（默认20分）**：DIFF与DEA位置、MACD柱颜色、金叉死叉位置
3. **量价关系（默认20分）**：量比、换手率、涨跌幅与量的匹配度
4. **大单净量与资金（默认15分）**：当日大单净量方向、5日大单趋势
5. **筹码分布（默认20分）**：获利比例、成本与现价差距、筹码集中度

你必须严格按照以下JSON格式返回，不要输出任何其他内容：

```json
{
  "total_score": <0-100的整数>,
  "grade": "<A/B/C/D/E>",
  "morphology": "<一句话形态判断，20字以内>",
  "details": {
    "ma_structure": {"score": <数字>, "max": <数字>, "note": "<评分说明>"},
    "macd": {"score": <数字>, "max": <数字>, "note": "<评分说明>"},
    "volume_price": {"score": <数字>, "max": <数字>, "note": "<评分说明>"},
    "capital_flow": {"score": <数字>, "max": <数字>, "note": "<评分说明>"},
    "chip_distribution": {"score": <数字>, "max": <数字>, "note": "<评分说明>"}
  },
  "ai_analysis": "<100-200字的综合分析，说明评分逻辑和关键发现>"
}
```

评分等级：A(85-100)强势 B(70-84)偏多 C(50-69)中性 D(30-49)偏弱 E(0-29)弱势"""


class DeepSeekClient:
    """DeepSeek API 客户端"""

    def __init__(self):
        if not DEEPSEEK_API_KEY:
            raise ValueError("请在 .env 中配置 DEEPSEEK_API_KEY")
        self.client = OpenAI(
            api_key=DEEPSEEK_API_KEY,
            base_url="https://api.deepseek.com",
        )

    def rate_stock(self, stock_data: dict, strategy_prompt: str) -> dict:
        """使用自定义策略对股票打分

        Args:
            stock_data: 个股技术数据字典
            strategy_prompt: 用户自定义的评分标准（自然语言）

        Returns:
            解析后的评分结果字典
        """
        # 将技术数据格式化为可读文本
        data_text = self._format_stock_data(stock_data)

        user_message = f"""请按照以下自定义评分标准对这只股票进行评分：

=== 自定义评分标准 ===
{strategy_prompt}

=== 个股技术数据 ===
{data_text}

请严格按照JSON格式返回评分结果。"""

        try:
            response = self.client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_message},
                ],
                temperature=0.3,
                max_tokens=2048,
            )

            content = response.choices[0].message.content.strip()
            return self._parse_response(content)

        except Exception as e:
            logger.error("DeepSeek API 调用失败: %s", e)
            raise RuntimeError(f"AI评分服务异常: {str(e)}")

    def _format_stock_data(self, data: dict) -> str:
        """将技术数据字典格式化为文本"""
        lines = []

        # 基本信息
        lines.append(f"股票名称: {data.get('stock_name', '')}")
        lines.append(f"股票代码: {data.get('stock_code', '')}")
        lines.append(f"交易日期: {data.get('trade_date', '')}")
        lines.append(f"最新收盘价: {data.get('close', '')}")
        lines.append(f"今日涨跌幅: {data.get('pct_chg', '')}%")

        # 均线数据
        ma = data.get("ma_data", {})
        if ma:
            lines.append(f"\n【均线数据】")
            for key in ["MA5", "MA10", "MA20", "MA30", "MA60"]:
                val = ma.get(key)
                if val is not None:
                    relation = "上方" if ma.get("close", 0) > val else "下方"
                    lines.append(f"  {key}: {val:.2f} (股价{relation})")

        # MACD数据
        macd = data.get("macd_data", {})
        if macd:
            lines.append(f"\n【MACD数据】")
            lines.append(f"  DIFF: {macd.get('diff', 0):.4f}")
            lines.append(f"  DEA: {macd.get('dea', 0):.4f}")
            lines.append(f"  MACD柱: {macd.get('macd', 0):.4f}")
            lines.append(f"  金叉/死叉: {macd.get('crossover', '无')}")

        # 量价数据
        vp = data.get("volume_price_data", {})
        if vp:
            lines.append(f"\n【量价数据】")
            lines.append(f"  量比: {vp.get('volume_ratio', 0):.2f}")
            lines.append(f"  换手率: {vp.get('turnover_rate', 0):.2f}%")
            lines.append(f"  成交量: {vp.get('vol', 0)}")

        # 资金数据
        cf = data.get("capital_flow_data", {})
        if cf:
            lines.append(f"\n【资金流向数据】")
            lines.append(f"  当日大单净量: {cf.get('net_mf_vol', 0):.2f}万元")
            lines.append(f"  5日大单趋势: {cf.get('trend', '无数据')}")

        # 筹码数据
        cd = data.get("chip_data", {})
        if cd:
            lines.append(f"\n【筹码分布数据】")
            lines.append(f"  获利比例: {cd.get('winner_pct', 0):.1f}%")
            lines.append(f"  平均成本: {cd.get('cost_avg', 0):.2f}")
            lines.append(f"  筹码集中度(90%): {cd.get('concentration', 0):.1f}%")

        return "\n".join(lines)

    def _parse_response(self, content: str) -> dict:
        """解析 DeepSeek 返回的 JSON，处理可能的 markdown 包裹"""
        # 尝试直接解析
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            pass

        # 尝试提取 ```json ... ``` 代码块
        match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', content)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass

        # 尝试提取 { ... } 最外层对象
        match = re.search(r'\{[\s\S]*\}', content)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass

        raise ValueError(f"无法解析 DeepSeek 返回内容: {content[:500]}")
