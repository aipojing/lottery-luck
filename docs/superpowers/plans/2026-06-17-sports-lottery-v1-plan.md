# 体彩数字彩 V1 实施计划

## 1. 红灯测试

- 更新规则测试，要求 `dlt/pl3/pl5` 进入 `GAME_RULES`，并校验范围、数量、开奖日和 provider。
- 新增体彩爬虫测试，覆盖官方字段标准化、开奖接口参数、常见 payload 结构和入库。
- 更新 API 测试，覆盖七个游戏列表、体彩预测 smoke、体彩分析空样本、体彩策略生成。
- 更新前端静态测试，确认首页、分析页、策略页包含体彩标签和排序入口。

## 2. 规则与仓储

- 把 `RESERVED_GAME_RULES` 中的三种体彩移入正式 `GAME_RULES`。
- 保留 `RESERVED_GAME_RULES` 为空字典作为未来扩展占位。
- 调整 `LotteryRepository.list_games()`，把没有本地开奖数据的正式玩法也返回给前端。

## 3. 体彩爬虫

- 新增 `lottery_luck/sports_crawler.py`。
- 提供 `normalize_sports_row()`、`fetch_game_rows()`、`main()`。
- 提供 `fetch_game_rows_auto()` 和 `fetch_game_rows_browser()`，官方 API 直连被 WAF 403 时切到官方页面浏览器态。
- 复用 `crawler.upsert_draw()`，避免重复维护入库 SQL。
- 默认官方 base URL 为 `https://webapi.sporttery.cn`，支持 `SPORTS_LOTTERY_API_BASE_URL` 覆盖。

## 4. API 与前端

- API 依赖规则表自然开放体彩玩法。
- 首页 `web/app.js` 增加体彩 demo 数据和标签排序。
- 分析页 `web/analysis.js` 增加体彩 tabs。
- 策略实验室 `web/strategy.js` 增加体彩 tabs。

## 5. 验证

- `PYTHONPATH=. .venv/bin/pytest -q`
- `node --check web/app.js && node --check web/analysis.js && node --check web/strategy.js`
- 启动本分支服务检查 `/api/games`、`/api/analysis/dlt`、`/api/predict`、`/api/strategy/dlt/generate`。
