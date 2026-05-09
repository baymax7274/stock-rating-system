import os
from dotenv import load_dotenv

load_dotenv()

TUSHARE_TOKEN = os.getenv("TUSHARE_TOKEN", "")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")

# 均线计算所需的最少交易日数量
MA_MIN_DAYS = 60
# MACD默认参数
MACD_FAST = 12
MACD_SLOW = 26
MACD_SIGNAL = 9
