# 数运合参

数运合参是一个彩票数据分析与玄学娱乐起盘工具。产品核心不是承诺预测未来开奖结果，而是把历史开奖数据、个人时空信息、命理叙事、号码筛选和开奖后复盘整合成一个可长期使用的参考工作台。

> 本项目仅供娱乐和数据分析参考，不构成投注建议，不销售彩票，不提供代购服务，不承诺中奖或收益。

## 当前能力

- 支持彩种：双色球、大乐透、福彩3D、排列3、快乐8。
- 首页起盘：姓名、历法、出生日期、时辰、出生地、当前城市、生成模式。
- 三种生成模式：稳财号、偏财号、守财号。
- 玄学解释链：本命财格、今日财签、避开号、大师起盘、逐号释义。
- 数据分析页：热号、冷号、遗漏、走势、和值、奇偶、区间、筛选器、回测、号码池、开奖日历。
- 福彩3D工具箱：走势图、遗漏统计、出次统计、冷热码、号码查询、号码属性、缩水选号、最近开奖 8 个工具，均可深链接。
- 策略实验室：策略候选、回测、对比。
- 后台：数据健康、任务队列、爬虫补采、玄学权重。
- 历史商业化代码已休眠：生产前端不展示支付、会员、次数包或额度行为，也不调用额度接口。
- 隐私边界：`/privacy.html` 说明第三方 AI 数据最小化、浏览器本地历史和保存方案处理。

## 技术栈

- 后端：FastAPI、Pydantic、SQLite / Turso libSQL。
- 前端：原生 HTML / CSS / JavaScript。
- 数据：本地 SQLite + 福彩 / 体彩历史开奖爬虫。
- AI：DeepSeek 特征提取与文案辅助，可关闭或缺省为中性特征。
- 测试：pytest、Playwright、node `--check`。

## 快速开始

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
playwright install chromium
python -m uvicorn lottery_luck.api:app --host 127.0.0.1 --port 8017
```

访问：

- 首页：`http://127.0.0.1:8017/`
- 分析中心：`http://127.0.0.1:8017/analysis.html?game=ssq&window=30`
- 福彩3D工具箱：`http://127.0.0.1:8017/analysis.html?game=3d`
- 策略实验室：`http://127.0.0.1:8017/strategy.html?game=ssq`
- 数据后台：`http://127.0.0.1:8017/admin.html`

### 福彩3D工具箱 URL

`analysis.html?game=3d` 默认进入工具箱首页。8 个工具用 `tool=` 深链接。除 `recent` 外的 7 个工具
都会带统计窗口请求数据，因此都接受并回写 `window=30|60|120`（默认 30）：链接怎么打开，刷新和分享
后就还是同一个窗口。其中只有 `trend`、`omission`、`frequency`、`heat` 在工具内提供窗口切换按钮，
`number`、`attributes`、`reduction` 沿用链接带来的窗口。`recent` 展示固定的最近 10 期，不带 `window`。

| 工具 | URL |
| --- | --- |
| 工具箱首页 | `/analysis.html?game=3d` |
| 走势图 | `/analysis.html?game=3d&tool=trend&window=30` |
| 遗漏统计 | `/analysis.html?game=3d&tool=omission&window=30` |
| 出次统计 | `/analysis.html?game=3d&tool=frequency&window=60` |
| 冷热码 | `/analysis.html?game=3d&tool=heat&window=120` |
| 号码查询 | `/analysis.html?game=3d&tool=number&window=30` |
| 号码属性 | `/analysis.html?game=3d&tool=attributes&window=30` |
| 缩水选号 | `/analysis.html?game=3d&tool=reduction&window=30` |
| 最近开奖 | `/analysis.html?game=3d&tool=recent` |

未知 `tool=` 值回落到工具箱首页；旧链接 `mode=pro` 会重定向到 `tool=frequency`，`mode=simple`
回到工具箱首页。工具深链接会在下方补一条工具箱首页历史记录，浏览器返回键回到工具箱而不是离开页面。

工具箱依赖的接口：`GET /api/workbench/3d/summary`（冷热、出次、遗漏、最近开奖、数据新鲜度、
本期方案）、`GET /api/3d/trends`（走势图）、`POST /api/3d/number-query`（号码查询和号码属性）、
`POST /api/3d/filter`（缩水选号）。数据 `stale` 或 `empty` 时，历史统计与查询工具照常可用，只有
本期候选生成和方案保存按 `can_claim_current` 关闭。

## 环境变量

复制 `.env.example` 后按需设置：

```bash
DEEPSEEK_MODEL=deepseek-v4-flash
LOTTERY_LUCK_AI_ENABLED=true
LOTTERY_LUCK_ADMIN_TOKEN=
LOTTERY_LUCK_AUTO_UPDATE_ENABLED=false
LOTTERY_LUCK_AUTO_UPDATE_INTERVAL_SECONDS=21600
TURSO_DATABASE_URL=
TURSO_AUTH_TOKEN=
```

可选配置：

```bash
LOTTERY_LUCK_SETTINGS_PATH=/absolute/path/settings.json
SPORTS_LOTTERY_API_BASE_URL=https://webapi.sporttery.cn
```

DeepSeek API Key 由用户在首页“AI 设置”中填写，只保存在当前浏览器的 Local Storage，并在预测请求中临时发送给 API。API 不保存用户密钥。`LOTTERY_LUCK_AI_ENABLED=false` 可作为服务端总开关强制关闭第三方 AI；用户未配置密钥时自动降级为中性特征。

`LOTTERY_LUCK_ADMIN_TOKEN` 是生产必填项，用于 `X-Lottery-Admin-Token` 后台鉴权。未配置或请求未带匹配 token 时，`/api/admin/*` 全部返回 401，后台页面只保留锁定壳，不会预填 token。生产 token 请用密码管理器或部署平台 secret 配置，不要写进 shell history、URL、日志或仓库文件。生成、验证和轮换步骤见 [docs/OPERATIONS.md](docs/OPERATIONS.md)。

自动数据更新默认关闭。生产启用时设置 `LOTTERY_LUCK_AUTO_UPDATE_ENABLED=true`，建议保留 `LOTTERY_LUCK_AUTO_UPDATE_INTERVAL_SECONDS=21600`，由 FastAPI lifespan 周期性调用真实调度链路。停用或临时回退时，关闭该变量后使用 `python -m lottery_luck.scheduler --once ...` 手动补采。

`LOTTERY_LUCK_SETTINGS_PATH` 可覆盖玄学权重、AI 文案风格、预测额度配置。示例见 [docs/OPERATIONS.md](docs/OPERATIONS.md)。

## Vercel 与 Turso 部署

生产部署使用两个 Vercel 项目：

- API 项目：Root Directory 设为仓库根目录。只在该项目配置 `TURSO_DATABASE_URL`、`TURSO_AUTH_TOKEN`、`DEEPSEEK_MODEL`、`LOTTERY_LUCK_AI_ENABLED=true`、`LOTTERY_LUCK_ADMIN_TOKEN`、`CRON_SECRET`、`ALLOWED_ORIGINS`、`LOTTERY_LUCK_QUOTA_ENABLED=false`。
- Web 项目：Root Directory 设为 `frontend`。只配置 `API_BASE_URL=https://<api-project>.vercel.app`，不要配置 DeepSeek、Turso 或管理口令。

Turso 导入和核对顺序：

```bash
python scripts/check_turso_source.py cwl_history/cwl_history.sqlite --output artifacts/turso-source.json
sqlite3 cwl_history/cwl_history.sqlite "PRAGMA journal_mode=WAL; PRAGMA wal_checkpoint(TRUNCATE);"
turso db create lottery-luck --from-file cwl_history/cwl_history.sqlite
turso db show lottery-luck --url
turso db tokens create lottery-luck
TURSO_DATABASE_URL='libsql://...' TURSO_AUTH_TOKEN='...' \
  python scripts/verify_remote_database.py --source-snapshot artifacts/turso-source.json
```

`check_turso_source.py` 会记录 SQLite 文件大小、`integrity_check`、page size、encoding、auto-vacuum、总开奖数和五个前台彩种的 count/latest issue；pragma 不符合预期会以非零退出。`verify_remote_database.py` 通过 `connect_database()` 读取 Turso，并要求 `ssq`、`dlt`、`3d`、`pl3`、`kl8` 的 count 和 latest issue 与 source snapshot 完全一致。

## 隐私与第三方 AI 边界

首页会收集姓名、历法、出生日期、时辰、出生地、当前城市和生成模式，用于服务器端预测、个人时空分数、开奖日选择、号码解释和历史记录摘要。不要把本项目理解为“全部个人处理都在浏览器”；预测由服务器端完成。

启用 DeepSeek 等第三方 AI 时，provider 上下文只包含 `game_key`、`fortune_mode`、`best_draw_date` 和 `personal_features`。`personal_features` 精确包含：

- `birth_vector`：由 `birth_vector(personal)` 派生的五行归一化向量。birth_vector 是由出生日期和已知出生时辰粗略派生的五行分布，不是原始出生日期或原始出生时辰。
- `birth_hour_known`：只表示出生时辰是否已知。
- `calendar_type`：`solar` 或 `lunar`。
- `location_relation`：`same`、`different` 或 `incomplete`。location_relation 只按去除首尾空白、压缩空白和大小写归一后的文本精确相等判断，不会做行政区划后缀等价。

第三方 AI 不直接接收原始姓名、精确出生日期、出生时辰地支、出生地或当前城市。浏览器本地历史可能保存精简摘要，可在首页清空。首页财运历史只写入当前浏览器的 Local Storage，不会上传为云端财运记录；清理站点数据也会移除这些本机记录。福彩3D工具箱的结构化方案使用独立方案接口，方案详情页提供删除能力。

`product_events` 只接受事件名和属性白名单。允许事件名为 `prediction_completed`、`plan_saved`、`workbench_opened`、`plan_edited`、`review_viewed`、`plan_carried_forward`、`tool_opened`、`tool_result_generated`；允许属性为 `game_key`、`source_type`、`mode`、`window`、`entry_count`、`candidate_count`、`freshness_status`、`review_status`、`tool_key`、`result_count`。`tool_key` 只接受 8 个工具的固定枚举，`result_count` 只接受整数条数。事件不会采集姓名、生日、出生地、当前城市、原始号码（含查询号码）、方案标题、自由文本或 `plan_id`。代码当前未定义事件保留期，生产查询和导出需按部署方隐私策略另行控制。

## 常用命令

运行服务：

```bash
python -m uvicorn lottery_luck.api:app --host 127.0.0.1 --port 8017
```

执行测试：

```bash
PYTHONPATH=. .venv/bin/pytest -q
for file in \
  web/app.js \
  web/product-client.js \
  web/workbench-3d.js \
  web/three-d-toolbox.js \
  web/analysis.js \
  web/result.js \
  web/strategy.js \
  web/admin.js \
  web/motion.js
do
  node --check "$file" || exit 1
done
git diff --check
```

只验证福彩3D工具箱：

```bash
# 工具箱路由、8 个工具、stale 降级、事件与移动端布局的前端行为测试
PYTHONPATH=. .venv/bin/pytest tests/test_frontend_behavior.py -k "3d" -q
# 工具箱后端：走势、号码查询、缩水、summary
PYTHONPATH=. .venv/bin/pytest tests/test_three_d_tools.py tests/test_workbench_3d.py tests/test_workbench_routes.py -q
# 视觉证据：临时 SQLite、固定 today=2026-07-13、关闭自动更新、禁用外部网络，重复两次并要求截图 SHA-256 一致
PYTHONPATH=. .venv/bin/python tests/capture_retention_qa.py
```

`tests/capture_retention_qa.py` 会重写 `artifacts/fc3d-toolbox-*.png` 四张截图，并输出移动端首屏
测量值；结论和未修复项记录在 [design-qa.md](design-qa.md)。

补采福彩：

```bash
python -m lottery_luck.crawler --games ssq,3d,kl8 --page-size 100
```

补采体彩：

```bash
python -m lottery_luck.sports_crawler --games dlt,pl3 --source auto --page-size 100 --pages 3
```

执行一次调度任务：

```bash
python -m lottery_luck.scheduler --once --provider cwl --games ssq,3d,kl8
python -m lottery_luck.scheduler --once --provider sports --games dlt,pl3 --source auto --pages 3
```

查看服务与数据健康：

```bash
curl -s http://127.0.0.1:8017/api/health
```

`service` 表示 API 和 SQLite 访问是否可用；`data` 按彩种返回 `fresh`、`attention`、`stale` 或 `empty`。`stale`、`empty` 或 `attention` 是数据状态，前端会按 `can_claim_current` 主动只读降级，不等于服务进程故障。发布前需要在部署环境确认福彩3D最新期与官方源一致，本地隔离测试只能证明代码行为。

## 项目结构

```text
lottery_luck/
  api.py             FastAPI 路由与静态站点入口
  predictor.py       号码生成、玄学解释、大师起盘 payload
  analysis.py        分析中心、筛选器、回测、号码池
  strategy.py        策略实验室
  quota.py           预测额度、模拟解锁、云端记录
  crawler.py         福彩官方数据补采
  sports_crawler.py  体彩官方数据补采
  data_health.py     数据健康报告
  repository.py      SQLite 数据访问
  settings.py        权重、文案、商业化额度配置
web/
  index.html/app.js  首页起盘体验
  analysis.html/js   分析中心与福彩3D工具箱
  three-d-toolbox.js 3D 工具箱路由、工具目录与工具事件
  workbench-3d.js    3D 工具数据加载、渲染与方案保存
  strategy.html/js   策略实验室
  result.html/js     历史财运号详情
  admin.html/js      数据后台
cwl_history/
  cwl_history.sqlite 本地开奖库与运行时表
tests/
  test_*.py          API、算法、爬虫、前端行为测试
docs/
  ARCHITECTURE.md
  OPERATIONS.md
  COMMERCIALIZATION.md
```

## 文档索引

- [架构说明](docs/ARCHITECTURE.md)
- [运行与运维](docs/OPERATIONS.md)
- [商业化与支付边界](docs/COMMERCIALIZATION.md)
- [设计 QA](design-qa.md)

## 已知边界

- 历史付费额度代码仅作归档兼容，生产前端不展示支付、会员、次数包、模拟购买或额度行为，也不调用相关接口。
- 历史额度与云端财运记录接口仅作归档兼容，默认由 `LOTTERY_LUCK_QUOTA_ENABLED=false` 关闭并返回 404；生产环境不得启用。
- 方案保存、查看、复盘、沿用都依赖 `X-Lottery-Client-Id` 做客户端隔离，不是正式账号授权模型。
- DeepSeek 只做特征提取与文案辅助，不直接决定号码。
- 彩票开奖具有随机性，历史数据和玄学解释都不能推断真实未来结果。
