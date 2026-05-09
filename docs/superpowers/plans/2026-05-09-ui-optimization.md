# UI优化 — 实现计划

> **Goal:** 为评分系统添加简洁的 Web 首页，输入股票名称/代码即可看到评分，无代码展示。

**Architecture:** FastAPI 新增 Jinja2 模板渲染首页 + 搜索接口，前端纯 HTML/CSS/JS 无框架。

**Tech Stack:** FastAPI, Jinja2, akshare (股票列表), 原生 JS

---

### Task 1: 添加依赖并配置模板引擎

**Files:**
- Modify: `requirements.txt`
- Modify: `app/main.py`

- [ ] **Step 1: 添加 jinja2 依赖**

`requirements.txt` 末尾追加一行：
```
jinja2==3.1.4
```

- [ ] **Step 2: 安装依赖**

```bash
pip install jinja2==3.1.4
```

- [ ] **Step 3: 配置模板目录**

在 `app/main.py` 中，FastAPI app 创建后添加 Jinja2Templates：

```python
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles

templates = Jinja2Templates(directory="app/templates")
```

### Task 2: 创建首页 HTML 模板

**Files:**
- Create: `app/templates/index.html`

模板包含三个区域：
- **搜索输入框**：实时触发下拉建议
- **建议下拉列表**：显示匹配的股票名称和代码
- **评分结果卡片**：总分、等级、五维度得分条、形态描述

所有样式内联在 `<style>` 中，交互逻辑用 `<script>` 实现。

设计要点：
- 深色主题，卡片式布局
- 输入框居中放大，带搜索图标
- 下拉建议列表绝对定位在输入框下方
- 评分卡片包含总分大号显示 + 等级徽章 + 五个维度进度条 + 形态文字

### Task 3: 新增搜索接口 + 首页路由

**Files:**
- Modify: `app/main.py`

- [ ] **Step 1: 添加股票列表缓存和搜索接口**

在 `main.py` 中添加：

```python
import akshare as ak
from fastapi import Request, Query

# 股票名称列表缓存
_stock_list: list[dict] = []

def get_stock_list() -> list[dict]:
    global _stock_list
    if not _stock_list:
        try:
            df = ak.stock_info_a_code_name()
            _stock_list = [
                {"code": row["code"], "name": row["name"]}
                for _, row in df.iterrows()
            ]
        except Exception:
            pass
    return _stock_list

@app.get("/")
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/api/v1/search")
async def search_stock(keyword: str = Query(..., min_length=1)):
    stocks = get_stock_list()
    keyword_lower = keyword.lower()
    results = [
        s for s in stocks
        if keyword_lower in s["code"].lower() or keyword_lower in s["name"].lower()
    ][:10]
    return {"code": 0, "data": results}
```

### Task 4: 编写 HTML 页面

创建完整的 `app/templates/index.html`，包含：
- 深色主题 CSS 变量
- 搜索输入框 + 下拉建议 UI
- 评分结果卡片模板
- JS: 输入监听 → 调用搜索 API → 渲染建议列表
- JS: 点击建议 → 调用评分 API → 渲染结果卡片

### Task 5: 启动验证

```bash
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

打开浏览器访问 `http://localhost:8000`，输入股票代码验证流程。
