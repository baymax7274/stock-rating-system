from pydantic import BaseModel, Field
from typing import Optional


class ScoreItem(BaseModel):
    score: float
    max: int
    note: str


class SubDimension(BaseModel):
    score: float
    max: int
    items: dict[str, ScoreItem]


class RatingDetails(BaseModel):
    ma_structure: SubDimension
    macd: SubDimension
    volume_price: SubDimension
    capital_flow: SubDimension
    chip_distribution: SubDimension


class RatingResult(BaseModel):
    stock_code: str
    stock_name: str
    trade_date: str
    total_score: float
    max_score: int
    grade: str
    morphology: str
    details: RatingDetails
    ai_analysis: Optional[str] = None
    strategy_name: Optional[str] = None


class ApiResponse(BaseModel):
    code: int
    message: str
    data: Optional[RatingResult] = None


class ErrorResponse(BaseModel):
    code: int
    message: str
    data: None = None


# ========== v2.0 AI 策略模型 ==========

class Strategy(BaseModel):
    id: str
    name: str = Field(..., min_length=1, max_length=50, description="策略名称")
    prompt: str = Field(..., min_length=1, max_length=2000, description="自然语言评分标准")
    created_at: str
    updated_at: str


class StrategyCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=50)
    prompt: str = Field(..., min_length=1, max_length=2000)


class StrategyUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=50)
    prompt: Optional[str] = Field(None, min_length=1, max_length=2000)


class AIBatchResponse(BaseModel):
    code: int
    message: str
    data: Optional[dict] = None
