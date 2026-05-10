import os

# 必须在导入akshare/requests之前清除代理
for k in ("http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY"):
    os.environ.pop(k, None)
os.environ["no_proxy"] = "*"
os.environ["NO_PROXY"] = "*"

from fastapi import FastAPI, HTTPException, Request, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.templating import Jinja2Templates
from app.scoring.engine import ScoringEngine
from app.models.schemas import (
    ApiResponse, Strategy, StrategyCreate, StrategyUpdate,
)
from app.data.akshare_client import AkshareClient
from app.ai.strategy_store import StrategyStore

app = FastAPI(
    title="股票技术面评分系统",
    description="基于Akshare数据的股票技术面自动评分API，支持DeepSeek AI自定义策略",
    version="2.0.0",
)

templates = Jinja2Templates(directory="app/templates")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

engine = ScoringEngine()
strategy_store = StrategyStore()


@app.get("/api/v1/rating/{stock_code}", response_model=ApiResponse)
async def get_rating(stock_code: str, strategy_id: str = Query(None)):
    """获取股票技术面评分，可选传入 strategy_id 走 AI 评分通道"""
    try:
        strategy_name = None
        strategy_prompt = None
        if strategy_id:
            st = strategy_store.get(strategy_id)
            if not st:
                raise HTTPException(status_code=404, detail=f"策略不存在: {strategy_id}")
            strategy_name = st["name"]
            strategy_prompt = st["prompt"]

        result = engine.rate(
            stock_code,
            strategy_id=strategy_id,
            strategy_name=strategy_name,
            strategy_prompt=strategy_prompt,
        )
        return ApiResponse(code=0, message="success", data=result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"评分服务异常: {str(e)}")


@app.get("/")
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/api/v1/search")
async def search_stock(keyword: str = Query(..., min_length=1)):
    stocks = AkshareClient._get_stock_list()
    keyword_lower = keyword.lower()
    results = [
        s for s in stocks
        if keyword_lower in s["code"].lower() or keyword_lower in s["name"].lower()
    ][:10]
    return {"code": 0, "data": results}


@app.get("/api/v1/health")
async def health():
    return {"status": "ok"}


# ========== v2.0 策略管理 API ==========

@app.get("/api/v1/strategies")
async def list_strategies():
    """获取所有自定义策略"""
    strategies = strategy_store.list_all()
    return {"code": 0, "data": strategies}


@app.post("/api/v1/strategies", status_code=201)
async def create_strategy(body: StrategyCreate):
    """创建新的AI评分策略"""
    try:
        strategy = strategy_store.create(name=body.name, prompt=body.prompt)
        return {"code": 0, "message": "策略创建成功", "data": strategy}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"创建策略失败: {str(e)}")


@app.put("/api/v1/strategies/{strategy_id}")
async def update_strategy(strategy_id: str, body: StrategyUpdate):
    """更新已有策略"""
    if strategy_store.get(strategy_id) is None:
        raise HTTPException(status_code=404, detail=f"策略不存在: {strategy_id}")
    try:
        updated = strategy_store.update(
            strategy_id,
            name=body.name,
            prompt=body.prompt,
        )
        return {"code": 0, "message": "策略更新成功", "data": updated}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"更新策略失败: {str(e)}")


@app.delete("/api/v1/strategies/{strategy_id}")
async def delete_strategy(strategy_id: str):
    """删除策略"""
    if not strategy_store.delete(strategy_id):
        raise HTTPException(status_code=404, detail=f"策略不存在: {strategy_id}")
    return {"code": 0, "message": "策略已删除"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
