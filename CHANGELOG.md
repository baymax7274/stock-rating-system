# 更新日志

## v2.0.0 (2026-05-10)

### 新增
- **DeepSeek AI 自定义评分策略** — 用户可用自然语言定义评分标准，DeepSeek 读取个股技术数据后按自定义策略打分
- **策略管理面板** — Web 界面支持创建、编辑、删除评分策略，查询股票时可切换不同策略进行评分
- **策略 CRUD API** (`GET/POST/PUT/DELETE /api/v1/strategies`)
- **AI 分析报告** — AI 评分结果额外附带 100-200 字综合分析
- 评分 API 新增 `strategy_id` 可选参数，传入则走 DeepSeek 评分通道
- 新增 `app/ai/` 模块：`deepseek_client.py`（DeepSeek API 客户端）、`strategy_store.py`（策略 JSON 持久化）

### 变更
- `RatingResult` 新增 `ai_analysis`、`strategy_name` 可选字段
- `ScoringEngine.rate()` 重构为双通道（规则引擎 / AI 评分），原有调用无影响
- 前端重构为 v2.0 界面，新增策略选择器和策略管理弹窗
- 配置 DeepSeek API Key，验证 AI 评分链路正常：自定义策略评分成功，返回综合分析和策略名称

---

## v1.1.0 (2026-05-09)

### 新增
- **Web 评分查询界面** — 深色主题单页应用，输入股票名称或代码即可获取评分，无需查看代码或 JSON
- **股票模糊搜索接口** (`GET /api/v1/search`) — 输入名称或代码实时匹配，支持键盘上下键选择
- **评分可视化卡片** — 总分进度条、A-E 等级徽章、五维度得分条、形态描述，一目了然

### 修复
- 消除 `_get_stock_list` 与 `get_stock_name` 对 `stock_info_a_code_name()` 的重复 API 调用，共享 `_name_cache`
- 获取股票列表失败时不再永久缓存空列表，允许后续请求重试
- 搜索接口的懒加载导入移至模块顶层

---

## v1.1.1 (2026-05-09)

### 修复
- **大单净量数据源切换** — 东方财富 `push2his.eastmoney.com` 接口已被屏蔽（TCP拒绝连接），改用新浪财经 MoneyFlow API 获取真实资金流向数据；量价估算降级为兜底方案

---

## v1.0.0 (2026-05-09)

### 新增
- **五大技术面评分维度**：均线结构、MACD 动能、量价关系、大单净量、筹码分布
- **FastAPI REST API** (`GET /api/v1/rating/{stock_code}`)
- **Akshare 数据源** — 主用新浪财经，东方财富备选
- 综合评分等级（A-E）及形态描述输出
