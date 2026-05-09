from pydantic import BaseModel
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


class ApiResponse(BaseModel):
    code: int
    message: str
    data: Optional[RatingResult] = None


class ErrorResponse(BaseModel):
    code: int
    message: str
    data: None = None
