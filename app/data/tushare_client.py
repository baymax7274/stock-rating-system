import os
import tushare as ts
import pandas as pd
from app.config import TUSHARE_TOKEN, MA_MIN_DAYS


class TushareClient:
    def __init__(self):
        ts.set_token(TUSHARE_TOKEN)
        # 如果代理不可用，跳过代理直连
        if os.environ.get("TUSHARE_NO_PROXY"):
            os.environ["no_proxy"] = "*"
            os.environ["NO_PROXY"] = "*"
        self.pro = ts.pro_api()

    def _code_to_ts(self, code: str) -> str:
        """将简写代码转为tushare格式 000001 -> 000001.SZ"""
        code = code.strip()
        if "." in code:
            return code
        if code.startswith(("0", "3")):
            return f"{code}.SZ"
        if code.startswith(("6", "9")):
            return f"{code}.SH"
        return code

    def get_daily(self, ts_code: str, days: int = MA_MIN_DAYS) -> pd.DataFrame:
        """获取日线行情，返回最近N个交易日数据"""
        df = self.pro.daily(ts_code=ts_code, limit=days)
        if df is None or df.empty:
            raise ValueError(f"未获取到 {ts_code} 的日线数据")
        df = df.sort_values("trade_date").reset_index(drop=True)
        # 确保数值类型
        for col in ["open", "high", "low", "close", "pre_close", "pct_chg", "vol"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
        return df

    def get_daily_basic(self, ts_code: str, days: int = MA_MIN_DAYS) -> pd.DataFrame:
        """获取每日指标：换手率、量比等"""
        df = self.pro.daily_basic(ts_code=ts_code, limit=days)
        if df is None or df.empty:
            raise ValueError(f"未获取到 {ts_code} 的每日指标数据")
        df = df.sort_values("trade_date").reset_index(drop=True)
        for col in ["turnover_rate", "turnover_rate_f", "volume_ratio"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
        return df

    def get_moneyflow(self, ts_code: str, days: int = 10) -> pd.DataFrame:
        """获取个股资金流向（大单净量）"""
        df = self.pro.moneyflow(ts_code=ts_code, limit=days)
        if df is None or df.empty:
            raise ValueError(f"未获取到 {ts_code} 的资金流向数据，可能需要更高权限")
        df = df.sort_values("trade_date").reset_index(drop=True)
        for col in ["buy_lg_vol", "sell_lg_vol", "net_mf_vol"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
        return df

    def get_cyq_perf(self, ts_code: str, days: int = 5) -> pd.DataFrame:
        """获取每日筹码表现：获利比例、平均成本等"""
        df = self.pro.cyq_perf(ts_code=ts_code, limit=days)
        if df is None or df.empty:
            raise ValueError(f"未获取到 {ts_code} 的筹码分布数据，可能需要更高权限")
        df = df.sort_values("trade_date").reset_index(drop=True)
        for col in ["winner_pct", "cost_avg"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
        return df

    def get_chip_concentration(self, ts_code: str) -> float:
        """估算筹码集中度，基于获利比例的变化幅度"""
        try:
            df = self.get_cyq_perf(ts_code, days=30)
            if df.empty or len(df) < 2:
                return 20.0  # 数据不足，返回默认高值
            recent = df["winner_pct"].tail(10)
            # 获利比例变化幅度越小，筹码越集中
            volatility = recent.std()
            # 映射到集中度百分比：std <5 -> ~5%, std <10 -> ~10%, etc
            concentration = volatility * 2 + 3
            return min(concentration, 25.0)
        except Exception:
            return 20.0  # 获取失败返回默认值

    def get_stock_name(self, ts_code: str) -> str:
        """获取股票名称"""
        try:
            df = self.pro.stock_basic(ts_code=ts_code, fields="name")
            if df is not None and not df.empty:
                return df.iloc[0]["name"]
        except Exception:
            pass
        return ts_code

    def format_code(self, code: str) -> str:
        return self._code_to_ts(code)
