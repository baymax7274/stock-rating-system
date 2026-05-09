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
from app.models.schemas import ApiResponse
from app.data.akshare_client import AkshareClient

app = FastAPI(
    title="股票技术面评分系统",
    description="基于Akshare数据的股票技术面自动评分API",
    version="1.0.0",
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


@app.get("/api/v1/rating/{stock_code}", response_model=ApiResponse)
async def get_rating(stock_code: str):
    """获取股票技术面评分"""
    try:
        result = engine.rate(stock_code)
        return ApiResponse(code=0, message="success", data=result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
