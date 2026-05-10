"""策略 JSON 持久化存储"""
import json
import os
import uuid
from datetime import datetime
from typing import Optional
import logging

logger = logging.getLogger(__name__)

DEFAULT_STORE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "data", "strategies.json"
)


class StrategyStore:
    """策略管理存储，JSON文件持久化"""

    def __init__(self, filepath: str = DEFAULT_STORE_PATH):
        self.filepath = filepath
        self._ensure_file()

    def _ensure_file(self):
        os.makedirs(os.path.dirname(self.filepath), exist_ok=True)
        if not os.path.exists(self.filepath):
            self._write([])

    def _read(self) -> list[dict]:
        try:
            with open(self.filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data if isinstance(data, list) else []
        except (json.JSONDecodeError, FileNotFoundError):
            return []

    def _write(self, strategies: list[dict]):
        with open(self.filepath, "w", encoding="utf-8") as f:
            json.dump(strategies, f, ensure_ascii=False, indent=2)

    def list_all(self) -> list[dict]:
        """获取所有策略"""
        return self._read()

    def get(self, strategy_id: str) -> Optional[dict]:
        """根据ID获取单个策略"""
        for s in self._read():
            if s["id"] == strategy_id:
                return s
        return None

    def create(self, name: str, prompt: str) -> dict:
        """创建新策略"""
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        strategy = {
            "id": uuid.uuid4().hex[:12],
            "name": name.strip(),
            "prompt": prompt.strip(),
            "created_at": now,
            "updated_at": now,
        }
        strategies = self._read()
        strategies.append(strategy)
        self._write(strategies)
        logger.info("已创建策略: %s", strategy["id"])
        return strategy

    def update(self, strategy_id: str, name: Optional[str] = None,
               prompt: Optional[str] = None) -> Optional[dict]:
        """更新策略"""
        strategies = self._read()
        for s in strategies:
            if s["id"] == strategy_id:
                if name is not None:
                    s["name"] = name.strip()
                if prompt is not None:
                    s["prompt"] = prompt.strip()
                s["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                self._write(strategies)
                logger.info("已更新策略: %s", strategy_id)
                return s
        return None

    def delete(self, strategy_id: str) -> bool:
        """删除策略"""
        strategies = self._read()
        new_list = [s for s in strategies if s["id"] != strategy_id]
        if len(new_list) == len(strategies):
            return False
        self._write(new_list)
        logger.info("已删除策略: %s", strategy_id)
        return True
