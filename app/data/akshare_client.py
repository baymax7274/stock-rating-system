import os
import datetime
import logging
import numpy as np
import pandas as pd

# ---- 必须在 import akshare 之前完成代理绕过 ----
for k in ("http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY"):
    os.environ.pop(k, None)
os.environ["no_proxy"] = "*"
os.environ["NO_PROXY"] = "*"

import requests as _requests

_original_get = _requests.get
_original_post = _requests.post


def _patched_get(url, **kwargs):
    kwargs.setdefault("timeout", 15)
    kwargs.setdefault("proxies", {"http": None, "https": None})
    return _original_get(url, **kwargs)


def _patched_post(url, **kwargs):
    kwargs.setdefault("timeout", 15)
    kwargs.setdefault("proxies", {"http": None, "https": None})
    return _original_post(url, **kwargs)


_requests.get = _patched_get
_requests.post = _patched_post
# -------------------------------------------------

import akshare as ak

logger = logging.getLogger(__name__)


class AkshareClient:
    """Akshare数据获取客户端，主用新浪财经，东方财富备选"""

    _name_cache = {}

    @staticmethod
    def _code_to_sina(code: str) -> str:
        """转为新浪格式 sz000001 / sh600519"""
        code = code.strip()
        if code.startswith("sz") or code.startswith("sh"):
            return code
        if "." in code:
            parts = code.split(".")
            symbol = parts[0]
            market = "sz" if parts[1].upper() == "SZ" else "sh"
        elif code.startswith(("0", "3")):
            symbol, market = code, "sz"
        elif code.startswith(("6", "9")):
            symbol, market = code, "sh"
        else:
            symbol, market = code, "sz"
        return f"{market}{symbol}"

    @staticmethod
    def _code_to_ak(code: str) -> tuple:
        """转为(symbol, market)格式"""
        code = code.strip()
        if code.startswith("sz") or code.startswith("sh"):
            symbol = code[2:]
            market = code[:2]
        elif "." in code:
            parts = code.split(".")
            symbol = parts[0]
            market = "sz" if parts[1].upper() == "SZ" else "sh"
        elif code.startswith(("0", "3")):
            symbol, market = code, "sz"
        elif code.startswith(("6", "9")):
            symbol, market = code, "sh"
        else:
            symbol, market = code, "sz"
        return symbol, market

    def get_daily(self, code: str, days: int = 60) -> pd.DataFrame:
        """获取日线行情（新浪财经）"""
        sina_code = self._code_to_sina(code)
        end = datetime.date.today().strftime("%Y%m%d")
        start = (datetime.date.today() - datetime.timedelta(days=days * 2)).strftime("%Y%m%d")

        df = ak.stock_zh_a_daily(
            symbol=sina_code, start_date=start, end_date=end, adjust="qfq"
        )
        if df is None or df.empty:
            raise ValueError(f"未获取到 {code} 的日线数据")

        df = df.rename(columns={
            "date": "trade_date", "open": "open", "close": "close",
            "high": "high", "low": "low", "volume": "vol", "amount": "amount",
            "turnover": "turnover_rate",
        })

        # 计算涨跌幅
        if "close" in df.columns:
            df["pct_chg"] = df["close"].pct_change() * 100

        df = df.tail(days).reset_index(drop=True)
        df["trade_date"] = df["trade_date"].astype(str)
        for col in ["open", "high", "low", "close", "pct_chg", "vol", "turnover_rate"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
        # 新浪换手率是小数(0.006=0.6%)，转为百分比
        if "turnover_rate" in df.columns:
            df["turnover_rate"] = df["turnover_rate"] * 100
        return df

    def get_daily_basic(self, code: str, days: int = 60) -> pd.DataFrame:
        """获取每日指标"""
        daily = self.get_daily(code, days=days)
        # 量比 ≈ 当日成交量 / 前5日均量
        if "vol" in daily.columns and len(daily) >= 10:
            ma5_vol = daily["vol"].rolling(5).mean()
            daily["volume_ratio"] = daily["vol"] / ma5_vol.shift(1)
        else:
            daily["volume_ratio"] = 1.0
        return daily

    def get_moneyflow(self, code: str, days: int = 10) -> pd.DataFrame:
        """获取/推算资金流向"""
        symbol, market = self._code_to_ak(code)

        # 尝试东方财富接口
        try:
            df = ak.stock_individual_fund_flow(stock=symbol, market=market)
            if df is not None and not df.empty:
                rename_map = {
                    "日期": "trade_date", "主力净流入-净额": "net_mf_amount",
                    "大单流入": "buy_lg_vol", "大单流出": "sell_lg_vol",
                }
                existing = {k: v for k, v in rename_map.items() if k in df.columns}
                df = df.rename(columns=existing)
                if "buy_lg_vol" in df.columns and "sell_lg_vol" in df.columns:
                    df["net_mf_vol"] = pd.to_numeric(df["buy_lg_vol"], errors="coerce") - pd.to_numeric(df["sell_lg_vol"], errors="coerce")
                elif "net_mf_amount" in df.columns:
                    df["net_mf_vol"] = pd.to_numeric(df["net_mf_amount"], errors="coerce")
                else:
                    df["net_mf_vol"] = 0
                df = df.sort_values("trade_date").tail(days).reset_index(drop=True)
                df["trade_date"] = df["trade_date"].astype(str)
                return df
        except Exception:
            pass

        # 备选：从日线量价推算大单方向
        daily = self.get_daily(code, days=days)
        if daily.empty:
            raise ValueError(f"未获取到 {code} 的资金流向数据")
        df = pd.DataFrame()
        df["trade_date"] = daily["trade_date"]
        # 价格涨+放量 → 资金流入；价格跌+放量 → 资金流出
        df["pct_chg"] = daily["pct_chg"]
        df["vol"] = daily["vol"]
        avg_vol = df["vol"].rolling(5).mean()
        df["net_mf_vol"] = np.where(
            daily["pct_chg"] > 0,
            (df["vol"] - avg_vol) * daily["close"] / 10000,
            -(df["vol"] - avg_vol) * daily["close"] / 10000,
        )
        return df.tail(days).reset_index(drop=True)

    def get_cyq_perf(self, code: str, days: int = 5) -> pd.DataFrame:
        """获取/推算筹码分布"""
        symbol, _ = self._code_to_ak(code)

        # 尝试东方财富接口
        try:
            df = ak.stock_cyq_em(symbol=symbol, adjust="")
            if df is not None and not df.empty:
                rename_map = {
                    "日期": "trade_date", "获利比例": "winner_pct",
                    "平均成本": "cost_avg",
                    "集中度90": "concentration_90", "集中度70": "concentration_70",
                }
                existing = {k: v for k, v in rename_map.items() if k in df.columns}
                df = df.rename(columns=existing)
                df = df.sort_values("trade_date").tail(days).reset_index(drop=True)
                df["trade_date"] = df["trade_date"].astype(str)
                return df
        except Exception:
            pass

        # 备选：从日线数据估算筹码分布
        daily = self.get_daily(code, days=60)
        if daily.empty:
            raise ValueError(f"未获取到 {code} 的筹码分布数据")

        close = daily["close"].values
        high = daily["high"].values
        low = daily["low"].values

        latest_close = close[-1]
        # 估算获利比例：近60日收盘价低于现价的比例
        winner_pct = np.sum(close < latest_close) / len(close) * 100
        # 估算平均成本：近60日均价
        cost_avg = np.mean(close)
        # 估算集中度：基于价格波动范围
        price_range = (np.max(high[-20:]) - np.min(low[-20:])) / latest_close * 100
        concentration = max(5, price_range * 0.6)

        df = pd.DataFrame([{
            "trade_date": daily["trade_date"].iloc[-1],
            "winner_pct": round(winner_pct, 2),
            "cost_avg": round(cost_avg, 2),
            "concentration_90": round(concentration, 2),
        }])
        return df

    def get_chip_concentration(self, code: str) -> float:
        try:
            df = self.get_cyq_perf(code, days=1)
            if df.empty:
                return 20.0
            if "concentration_90" in df.columns:
                latest = float(df.iloc[-1]["concentration_90"])
                if 0 < latest < 30:
                    return latest
            return 20.0
        except Exception:
            return 20.0

    def get_stock_name(self, code: str) -> str:
        symbol, _ = self._code_to_ak(code)
        if symbol in self._name_cache:
            return self._name_cache[symbol]
        try:
            df = ak.stock_info_a_code_name()
            for _, row in df.iterrows():
                self._name_cache[str(row["code"])] = str(row["name"])
        except Exception:
            pass
        return self._name_cache.get(symbol, code)

    def format_code(self, code: str) -> str:
        symbol, _ = self._code_to_ak(code)
        return symbol


_stock_list_cache = None


def _get_stock_list() -> list[dict]:
    """获取A股股票列表（带缓存），用于搜索建议"""
    global _stock_list_cache
    if _stock_list_cache is not None:
        return _stock_list_cache
    try:
        df = ak.stock_info_a_code_name()
        if df is not None and not df.empty:
            _stock_list_cache = [
                {"code": str(row["code"]), "name": str(row["name"])}
                for _, row in df.iterrows()
            ]
            return _stock_list_cache
    except Exception as e:
        logger.warning("获取股票列表失败: %s", e)
    _stock_list_cache = []
    return _stock_list_cache
