# 运行与运维

## 本地运行

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
playwright install chromium
python -m uvicorn lottery_luck.api:app --host 127.0.0.1 --port 8017
```

另开一个终端启动 Next.js Web。Web 只保存公开的 API 地址，不保存 DeepSeek、Turso 或后台令牌：

```bash
cd frontend
npm install
API_BASE_URL=http://127.0.0.1:8017 npm run dev -- --hostname 127.0.0.1 --port 3001
```

浏览器打开 `http://127.0.0.1:3001/`。生产构建使用 `npm run build`；Vercel Web 项目的
Root Directory 设置为 `frontend`。

健康检查：

```bash
curl -s http://127.0.0.1:8017/api/health
```

## 环境变量

### 后台管理员令牌

`LOTTERY_LUCK_ADMIN_TOKEN` 是生产必填项。代码在每个后台请求读取当前进程环境变量，并要求请求头 `X-Lottery-Admin-Token` 与其匹配。

- 未配置 `LOTTERY_LUCK_ADMIN_TOKEN`：`/api/admin/*` 全部返回 401。
- 请求未带 token 或 token 不匹配：`/api/admin/*` 返回 401，响应 `WWW-Authenticate: LotteryAdmin`。
- 后台页面 `/admin.html` 仍可打开，但默认锁定，不预填 token，前端只把 token 放在 sessionStorage 或内存中。

生成 token 时不要把密文写进 shell history、URL、CI 日志或仓库文件。示例：

```bash
umask 077
python - <<'PY' > /tmp/lottery_luck_admin_token
import secrets
print(secrets.token_urlsafe(48))
PY
```

把 `/tmp/lottery_luck_admin_token` 的内容录入部署平台 secret 或密码管理器后删除临时文件：

```bash
rm -f /tmp/lottery_luck_admin_token
```

验证时用静默输入，避免 token 出现在命令历史：

```bash
read -r -s ADMIN_TOKEN
printf '\n'
curl -i http://127.0.0.1:8017/api/admin/settings \
  -H "X-Lottery-Admin-Token: ${ADMIN_TOKEN}"
unset ADMIN_TOKEN
```

轮换步骤：

1. 在密码管理器或部署平台 secret 中生成并保存新 token。
2. 如果平台支持把 secret 注入到已运行进程环境，更新后直接用新 token 验证；代码会逐请求读取 `LOTTERY_LUCK_ADMIN_TOKEN`。
3. 如果平台只在启动时注入环境变量，做滚动重启或蓝绿切换，先让新实例带新 token 通过 `/api/admin/settings`，再摘除旧实例。
4. 验证旧 token 返回 401，新 token 返回 200。
5. 删除旧 token，清理本地临时文件和工单备注里的密文。

### DeepSeek

```bash
DEEPSEEK_MODEL=deepseek-v4-flash
LOTTERY_LUCK_AI_ENABLED=true
```

说明：

- `LOTTERY_LUCK_AI_ENABLED=false` 会强制使用 `NullAiProvider`，用于紧急关闭第三方 AI。
- DeepSeek API Key 由用户在首页自行配置，保存在浏览器 Local Storage，并仅随 `/api/predict` 请求发送；API 不落库、不记录该密钥。
- 用户没有配置 API Key 时使用 `NullAiProvider`。
- 启用 AI 时，第三方只接收 `game_key`、`fortune_mode`、`best_draw_date` 和 `personal_features` 派生特征。不会发送原始姓名、精确出生日期、出生时辰地支、出生地或当前城市。
- AI 返回 payload 只允许 `element_bias`、`digit_bias`、`lucky_themes`、`explanation`、`confidence`，包含具体号码、承诺词或未知字段时降级为中性特征。
- Vercel API 项目只配置 `DEEPSEEK_MODEL` 和 `LOTTERY_LUCK_AI_ENABLED=true`；不再配置共享的 `DEEPSEEK_API_KEY`。

### Turso

生产数据库由 API 项目通过 Turso/libSQL 访问。本地开发保持 `TURSO_DATABASE_URL=` 和 `TURSO_AUTH_TOKEN=` 为空，继续使用 `cwl_history/cwl_history.sqlite`；生产 API 项目必须同时配置二者。

导入前先生成 source snapshot：

```bash
python scripts/check_turso_source.py cwl_history/cwl_history.sqlite --output artifacts/turso-source.json
```

该命令会输出：

- 文件大小。
- `PRAGMA integrity_check`。
- page size。
- encoding。
- auto-vacuum。
- 总开奖数。
- `ssq`、`dlt`、`3d`、`pl3`、`kl8` 的 count 和 latest issue。

命令会在 `integrity_check != ok`、page size 不是 `4096`、encoding 不是 `UTF-8` 或 auto-vacuum 不是 `0` 时非零退出。任何失败都先修复源库，不要导入 Turso。

完整导入和远端核对顺序：

```bash
python scripts/check_turso_source.py cwl_history/cwl_history.sqlite --output artifacts/turso-source.json
sqlite3 cwl_history/cwl_history.sqlite "PRAGMA journal_mode=WAL; PRAGMA wal_checkpoint(TRUNCATE);"
turso db create lottery-luck --from-file cwl_history/cwl_history.sqlite
turso db show lottery-luck --url
turso db tokens create lottery-luck
TURSO_DATABASE_URL='libsql://...' TURSO_AUTH_TOKEN='...' \
  python scripts/verify_remote_database.py --source-snapshot artifacts/turso-source.json
```

远端核对脚本通过 `lottery_luck.database.connect_database()` 连接数据库。设置 `TURSO_DATABASE_URL` 后它会走 libSQL/Turso；未设置时只会读取本地默认数据库，不可作为生产核对结果。

### Vercel 双项目

生产部署拆成两个 Vercel 项目：

| 项目 | Root Directory | 环境变量 |
| --- | --- | --- |
| API | 仓库根目录 | `TURSO_DATABASE_URL`, `TURSO_AUTH_TOKEN`, `DEEPSEEK_MODEL`, `LOTTERY_LUCK_AI_ENABLED=true`, `LOTTERY_LUCK_ADMIN_TOKEN`, `CRON_SECRET`, `ALLOWED_ORIGINS`, `LOTTERY_LUCK_QUOTA_ENABLED=false` |
| Web | `frontend` | `API_BASE_URL=https://<api-project>.vercel.app` |

边界：

- DeepSeek、Turso token、管理员 token 和 cron secret 只存在于 API 项目。
- Web 项目只知道 API base URL，不直接连接 Turso，不保存 DeepSeek key，不暴露管理口令。
- API 的 `ALLOWED_ORIGINS` 只放 Web 正式域名和必要的 Vercel preview 域名。
- `LOTTERY_LUCK_QUOTA_ENABLED=false` 是生产默认值；历史商业化代码保持休眠，当前前端不调用额度、支付、会员、次数包或模拟购买接口。

### 自动更新

自动更新默认关闭：

```bash
LOTTERY_LUCK_AUTO_UPDATE_ENABLED=false
LOTTERY_LUCK_AUTO_UPDATE_INTERVAL_SECONDS=21600
```

生产启用时，交互式 shell 必须先 `export`，确保子进程能读取变量；systemd 或容器应在服务的 `Environment=`、env 配置中设置同名变量：

```bash
export LOTTERY_LUCK_AUTO_UPDATE_ENABLED=true
export LOTTERY_LUCK_AUTO_UPDATE_INTERVAL_SECONDS=21600
python -m uvicorn lottery_luck.api:app --host 127.0.0.1 --port 8017
```

真实行为：

- FastAPI lifespan 启动 `auto_update.update_loop`。
- 每轮调用 `auto_update.run_repository_updates`，provider 顺序为 `cwl` 后 `sports`。
- 默认彩种为 `cwl`: `ssq,3d,kl8`，`sports`: `dlt,pl3,pl5`。
- 最近成功任务未超过 interval 时跳过；没有成功记录、时间戳异常或上次失败时，下一轮会继续尝试。
- interval 下限是 900 秒；建议 21600 秒，即 6 小时。
- 同一进程有单飞锁，自动更新和后台手动补采不会重叠；冲突时手动调度会看到 `crawl already in progress`。
- 循环异常会记录 `automatic data update failed` 日志并在下一轮重试。

停用自动更新并回退手动补采时，先停止或滚动替换旧服务进程，因为运行中的进程不会继承后续 shell 变更。systemd 或容器应删除启用变量或将其设为 `false`；交互式 shell 可显式设为 `false`，并清除不再需要的周期变量。未设置启用变量时默认也是关闭：

```bash
export LOTTERY_LUCK_AUTO_UPDATE_ENABLED=false
unset LOTTERY_LUCK_AUTO_UPDATE_INTERVAL_SECONDS
python -m uvicorn lottery_luck.api:app --host 127.0.0.1 --port 8017
python -m lottery_luck.scheduler --once --provider cwl --games ssq,3d,kl8 --page-size 100
python -m lottery_luck.scheduler --once --provider sports --games dlt,pl3,pl5 --source auto --pages 3 --page-size 100
```

服务停止后，如果当前 shell 不再用于启动它，也可执行 `unset LOTTERY_LUCK_AUTO_UPDATE_ENABLED LOTTERY_LUCK_AUTO_UPDATE_INTERVAL_SECONDS` 清理两项设置。

监测建议：

- 定时请求 `/api/health`，区分 `service` 和 `data`。
- 告警 `service=error` 或 HTTP 非 200。
- 告警 `data["3d"].status` 连续为 `stale` 或 `empty`。
- 观察后台 `/api/admin/tasks` 的失败任务和 `/api/admin/data-health` 的 `failure_summary`。

### 设置覆盖

```bash
LOTTERY_LUCK_SETTINGS_PATH=/absolute/path/settings.json
```

示例：

```json
{
  "metaphysics_weights": {
    "steady": {
      "personal_space": 40,
      "ai_fortune": 25,
      "draw_day_luck": 20,
      "history_guardrail": 15
    }
  },
  "prediction_quota": {
    "free_daily": 1,
    "new_user_bonus": 3,
    "member_daily": 20,
    "package_units": [6, 18, 66],
    "mode_costs": {
      "steady": 1,
      "windfall": 1,
      "guard": 1
    },
    "enabled_games": ["ssq", "dlt", "3d", "pl3", "kl8"],
    "allow_demo_after_exhausted": true
  }
}
```

## `/api/health` 判读

示例：

```json
{
  "status": "degraded",
  "service": "ok",
  "data": {
    "3d": {
      "status": "stale",
      "latest_issue": "2026182",
      "latest_date": "2026-07-01",
      "staleness_days": 12,
      "can_claim_current": false,
      "message": "数据停留在第2026182期，暂不提供本期结论",
      "last_successful_update": "2026-07-12T03:00:00+00:00",
      "sync_error": ""
    }
  }
}
```

- `service=ok`：API 进程能访问 repository。即使 `status=degraded`，服务本身仍可响应。
- `service=error`：repository 不可用，响应包含 `error: data repository unavailable`，应按服务故障处理。
- `data`：按前端彩种返回 freshness。`fresh` 和 `attention` 允许 `can_claim_current=true`；`stale` 和 `empty` 会让首页和福彩3D工具箱主动只读降级，禁用本期候选生成与本期保存 CTA，历史统计工具仍然可读。
- `attention` 表示数据接近过期或需关注，不等于进程故障；建议观察并补采。
- `stale`、`empty` 或 `attention` 的处置重点是数据补采，不要直接判为服务宕机。

## 数据补采

福彩：

```bash
python -m lottery_luck.crawler --games ssq,3d,kl8 --page-size 100
```

体彩：

```bash
python -m lottery_luck.sports_crawler --games dlt,pl3 --source auto --page-size 100 --pages 3
```

调度入口：

```bash
python -m lottery_luck.scheduler --once --provider cwl --games ssq,3d,kl8 --page-size 100
python -m lottery_luck.scheduler --once --provider sports --games dlt,pl3,pl5 --source auto --pages 3 --page-size 100
```

## 后台页面和管理 API

地址：

```text
http://127.0.0.1:8017/admin.html
```

后台 API 都在 `/api/admin/*`，由 `LOTTERY_LUCK_ADMIN_TOKEN` 和 `X-Lottery-Admin-Token` 保护。包括：

- `GET /api/admin/data-health`
- `GET /api/admin/settings`
- `GET /api/admin/tasks`
- `POST /api/admin/tasks/run`
- `POST /api/admin/crawl/sports`
- `POST /api/admin/crawl/cwl`

后台能力：

- 数据健康：样本数、覆盖范围、最新期、缺口、状态。
- 后台任务队列：执行一次补采，展示最近任务。
- 玄学算法配置：展示三种模式权重。
- 历史商业化配置：仅用于归档兼容；生产前端不展示或调用额度、会员、次数包和模拟购买流程。

## SQLite 发布备份与回滚

运行时数据库路径来自代码常量 `lottery_luck.config.DB_PATH`，当前默认是 `cwl_history/cwl_history.sqlite`。不要暂存或提交运行时数据库变动，除非明确更新种子数据。

发布 schema 变更前：

1. 关闭自动更新或切走流量，避免爬虫、后台任务、方案写入同时进行。
2. 阻止后台手动补采和管理写操作。
3. 使用 SQLite backup API 做一致性备份。

安全备份命令：

```bash
DB_PATH="$(PYTHONPATH=. .venv/bin/python - <<'PY'
from lottery_luck.config import DB_PATH
print(DB_PATH)
PY
)"
mkdir -p backups
BACKUP="backups/cwl_history.sqlite.$(date -u +%Y%m%dT%H%M%SZ)"
sqlite3 "$DB_PATH" ".timeout 10000" ".backup '$BACKUP'"
sqlite3 "$BACKUP" "PRAGMA integrity_check;"
```

发布前校验：

```bash
sqlite3 "$DB_PATH" "PRAGMA integrity_check;"
PYTHONPATH=. .venv/bin/pytest tests/test_plans.py tests/test_product_events.py tests/test_api.py -q
```

启动服务时会初始化 `product_events` 与 3D 方案 schema；方案迁移使用事务和临时表，失败会回滚。若发布后需要恢复：

```bash
DB_PATH="$(PYTHONPATH=. .venv/bin/python - <<'PY'
from lottery_luck.config import DB_PATH
print(DB_PATH)
PY
)"
sqlite3 "$BACKUP" "PRAGMA integrity_check;"
cp -p "$DB_PATH" "${DB_PATH}.failed.$(date -u +%Y%m%dT%H%M%SZ)"
cp -p "$BACKUP" "$DB_PATH"
sqlite3 "$DB_PATH" "PRAGMA integrity_check;"
```

恢复后重启服务，重新检查 `/api/health`、后台 401、方案查询和一次只读页面访问。

## product_events 隐私边界

`POST /api/events` 要求 `X-Lottery-Client-Id`，请求体最大 8192 字节，事件名和属性都使用白名单。

允许事件名：

- `prediction_completed`
- `plan_saved`
- `workbench_opened`
- `plan_edited`
- `review_viewed`
- `plan_carried_forward`
- `tool_opened`（3D 工具箱打开某个工具，每个工具每次页面加载最多记一次）
- `tool_result_generated`（工具真正产出结果，例如号码查询命中或缩水生成候选）

允许属性：

- `game_key`
- `source_type`
- `mode`
- `window`
- `entry_count`
- `candidate_count`
- `freshness_status`
- `review_status`
- `tool_key`（固定枚举：`trend`、`omission`、`frequency`、`heat`、`number`、`attributes`、`reduction`、`recent`）
- `result_count`（整数条数，0 到 10000）

`tool_key` 是闭合白名单：未知工具名直接拒绝，不会作为自由文本落库。`result_count` 只记录条数，不记录
号码本身。工具箱事件不携带用户查询的号码、候选号码明细或任何自由文本。

不得采集或写入姓名、生日、出生地、当前城市、原始号码、方案标题、`plan_id` 或任意嵌套对象。代码没有定义保留期，也没有公开查询接口；生产分析查询、导出和清理需要部署方按隐私策略单独控制。

## 福彩3D工具箱

工具箱在 `/analysis.html?game=3d`，8 个工具通过 `tool=` 深链接：`trend`、`omission`、`frequency`、
`heat`、`number`、`attributes`、`reduction`、`recent`。前四个额外接受 `window=30|60|120`（默认 30）。

### 统计定义

- 走势图（`GET /api/3d/trends`）：按所选窗口取最近 N 期真实开奖，按时间正序输出每期的百十个位数字。
  服务器在窗口内从最早一期起累计每个位置每个数字的遗漏（未出现 +1，出现归 0），完整矩阵在
  `rows[].omissions[position][digit]`。表格每格显示的是 `rows[].hit_omissions[position]`：该期该位
  **落号在归零之前**已连续遗漏的期数（即它结束的那段遗漏）。`omissions[position][落号]` 在该期必然是
  0，所以它不能作为单元格数值——那会让整列恒为 0。窗口第一期的所有落号遗漏为 0（窗口内没有更早的数据）。
  它只描述所选窗口内的历史序列，不外推，也不是概率。窗口外的历史不参与计算，`sample_size` 会如实
  给出真实样本期数（历史不足时小于窗口值）。
- 遗漏统计 / 出次统计 / 冷热码（`GET /api/workbench/3d/summary`）：同样只在所选窗口内统计；冷热分层
  由窗口内出次与当前遗漏合成。
- 号码查询 / 号码属性（`POST /api/3d/number-query`）：查询基于真实历史开奖；号码属性（和值、跨度、
  组态、奇偶）由服务器按输入的三位数字直接算出，不依赖历史。
- 所有工具的文案都必须给出样本窗口、最新数据日期和“历史统计不代表未来概率”，不得出现推荐或必中类
  表述。

### stale 行为

`data["3d"].status` 为 `stale` 或 `empty` 时（`can_claim_current=false`）：

- 仍然可用：走势图、遗漏统计、出次统计、冷热码、号码查询、号码属性、最近开奖，以及缩水条件的编辑。
  历史数据不会因为数据过期而变得不可读。
- 关闭：本期候选生成（缩水“生成候选”）、手动/随机保存、筛选保存。禁用原因就写在被禁用动作旁边，
  并给出当前最新数据的期号与日期，例如
  `数据待更新（最新数据 2026193 / 2026-07-05），暂不能保存本期方案。`
- 顶部数据状态条同时显示 `数据待更新` 与最新期号/日期。
- 处置动作是补采数据（见“数据补采”），不是重启服务。

### 发布前数据新鲜度检查

上线或发布工具箱变更前，在部署环境执行：

```bash
python -m lottery_luck.scheduler --once --provider cwl --games 3d --page-size 100
curl -s 'http://127.0.0.1:8017/api/health' | python -m json.tool
curl -s 'http://127.0.0.1:8017/api/workbench/3d/summary?window=30' \
  -H 'X-Lottery-Client-Id: release-check' | python -m json.tool
curl -s 'http://127.0.0.1:8017/api/3d/trends?window=30' | python -m json.tool
```

人工核对：

- `/api/health` 的 `data["3d"].latest_issue`、`latest_date` 与福彩官方源一致。
- `summary.freshness.status` 与 `can_claim_current` 自洽：`fresh`/`attention` 才允许本期保存。
- `summary.current_target` 的目标期号是官方源最新期的下一期。
- `/api/3d/trends` 的 `sample_size` 等于请求窗口（历史足够时），`latest_issue` 与 health 一致。
- 打开 `/analysis.html?game=3d`，确认工具箱首页显示的最新期号和上面一致。

任一项不一致就先补采，不要带着过期数据发布。本地隔离测试只能证明代码行为，不能替代部署环境的官方源核对。

## 方案与 client 隔离

方案 API 使用 `X-Lottery-Client-Id`：

- `POST /api/plans`
- `GET /api/plans`
- `GET /api/plans/{plan_id}`
- `PATCH /api/plans/{plan_id}`
- `DELETE /api/plans/{plan_id}`
- `POST /api/plans/{plan_id}/review`
- `POST /api/plans/{plan_id}/carry-forward`

仓储查询都带 `client_id` 条件，`carried_from_plan_id` 还有同 client 触发器保护。上线前必须用两个不同 client 验证：A 保存的方案，B 读取、修改、删除、复盘和沿用都不能成功。

## 生产前最小验收

没有 production 或 staging 凭据时，不能声称“官方源最新期已核对”。本地只能证明隔离行为、降级行为和鉴权行为。部署环境必须执行：

```bash
python -m lottery_luck.scheduler --once --provider cwl --games 3d --page-size 100
curl -s http://127.0.0.1:8017/api/health
```

人工核对：

- 福彩3D `latest_issue` 和 `latest_date` 与官方源一致。
- `/api/health` 中 `data["3d"].can_claim_current` 与当前数据状态一致。
- 无 token 和错误 token 访问 `/api/admin/settings` 都是 401，正确 token 是 200。
- 第三方 AI 请求日志不含姓名、生日、出生地、当前城市或原始号码。
- 保存、复盘、沿用三条 API 均按 client 隔离。
- stale 演练能禁用首页保存 CTA、工具箱本期保存 CTA 和本期候选生成，历史工具仍可读。

本地隔离回归建议：

```bash
PYTHONPATH=. .venv/bin/pytest \
  tests/test_data_health.py \
  tests/test_admin_auth.py \
  tests/test_ai_features.py \
  tests/test_predictor.py::test_ai_provider_context_uses_only_minimized_personal_features \
  tests/test_plan_routes.py \
  tests/test_workbench_routes.py \
  tests/test_retention_flow.py::test_stale_home_and_workbench_disable_current_saves \
  -q
```

## 2026-08-08 Vercel 迁移验收记录

本次本地验收针对提交 `b9a00b2` 及其后的 Next 开发脚本补充，覆盖 FastAPI、Next.js Web、
Local Storage 历史记录、无 DeepSeek key 降级和前端敏感信息边界：

- 全量 Python 回归：`847 passed, 1 warning in 224.80s`。
- Next 单测：`2 files passed / 4 tests passed`。
- Next 生产构建：Next.js `16.3.0` 编译、类型检查和静态页面生成成功。
- 浏览器验收：桌面 `1440x1000`、移动 `390x844` 均打开预测首页和福彩3D工具箱；预测表单提交后成功落盘，并在本机历史中出现；`mode=pro` 旧深链接迁移到工具路由；走势图、出次统计、策略兼容页、历史详情页和锁定态后台均可访问。
- 无 AI key 验收：浏览器未配置用户 DeepSeek Key 时预测仍成功，并使用服务端本地解释兜底。
- 浏览器产物扫描：`frontend/.next/static`、`frontend/public`、`web` 中未发现 `DEEPSEEK_API_KEY`、`TURSO_AUTH_TOKEN`、`LOTTERY_LUCK_ADMIN_TOKEN`、`CRON_SECRET`，也未发现会员、次数包、模拟购买或解锁文案。
- 商业代码休眠：额度和云端财运记录接口在 `LOTTERY_LUCK_QUOTA_ENABLED=false` 时统一返回 404；Turso 远端核验缺少 URL 或 token 时拒绝回退到本地库。
- 已知非阻断项：浏览器仅报告缺少 `/favicon.ico`；本地种子数据停留在 2026-06-14，因此福彩3D本期保存保持只读降级，这不代表生产数据状态。

本地验收不能替代线上资源验证。Turso 和 Vercel 凭据就绪后仍必须完成：远端数据库数量/最新期核对、
Web/API 两项目环境变量核对、Cron 鉴权触发、正式域名 CORS、后台 token 401/200 和官方源最新期对照。

## 历史发布候选验证记录

以下内容是 2026-07-13 的本地隔离证据快照。`60933aa` 是可执行/测试树验证锚点；后续提交仅为发布文档或示例修正。用以下命令验证从证据锚点到当前 HEAD 的运行时代码与测试没有变化，预期无输出；若有输出，必须针对变化后的可执行树重新运行相应门槛：

```bash
git diff --name-only 60933aa..HEAD -- lottery_luck web tests
```

这份快照只说明当前可执行与测试树和证据锚点一致，并且该锚点在当时的本地环境中通过了所列检查；它不是后续代码提交、部署环境或长期运行状态的保证。

- 全量回归：审查采用的最新一次 `PYTHONPATH=. .venv/bin/pytest -q` 返回 `725 passed, 4 warnings in 217.96s (0:03:37)`；先前同一结果耗时 `205.03s`，运行耗时有波动，测试通过数和 warning 数一致。
- 前端语法：对 `web/app.js`、`web/product-client.js`、`web/workbench-3d.js`、`web/analysis.js`、`web/result.js`、`web/strategy.js`、`web/admin.js` 执行的 7 个 `node --check` 均以退出码 0 完成。
- 仓库检查：`git diff --check` 无输出并以退出码 0 完成。每次执行门槛都必须同时运行 `git status --short`；2026-07-13 复核时工作树只有未暂存的 `cwl_history/cwl_history.sqlite`，该文件未进入提交。
- hygiene 扫描：20 条是 HTML 输入提示属性，其中 `web/analysis.html` 14 条、`web/strategy.html` 6 条；4 条是 SQL 参数占位标识及其插值，其中 `lottery_luck/crawler.py` 2 条、`lottery_luck/data_health.py` 2 条；1 条是 `docs/OPERATIONS.md` 对扫描命令本身的记录。没有无法归类的命中，也没有真实未完成项。
- 本地隔离 preflight：执行本节上方的完整命令返回 `191 passed, 1 warning in 5.88s`，覆盖 health fresh/data 判读、后台未授权 401、AI 请求与异常日志的数据最小化、方案 client 隔离、复盘与沿用隔离，以及 stale 状态下本期 CTA 的只读降级。
- 本地 SQLite：`PRAGMA integrity_check;` 返回 `ok`；本地 `3d` 最新记录为期号 `2026182`、日期 `2026-07-11`。这只是本地数据库状态，不代表 staging、production 或官方源结果。

**BLOCKING external gate（未完成）**：福彩3D `latest_issue`、`latest_date` 与官方源一致仍未在部署环境证明。发布前必须在 staging 或 production 执行本节上方的 `scheduler --once` 和 `/api/health` 命令，人工对照官方源，并由执行人与复核人签字后才能放行。

```text
部署环境：
执行时间：
执行人：
复核人：
官方源核对结果：
放行结论：
```

## 测试与验证

全量验证：

```bash
PYTHONPATH=. .venv/bin/pytest -q
node --check web/app.js
node --check web/product-client.js
node --check web/workbench-3d.js
node --check web/analysis.js
node --check web/result.js
node --check web/strategy.js
node --check web/admin.js
git diff --check
```

hygiene 扫描：

```bash
git status --short
rg -n 'TODO|TBD|FIXME|placeholder|coming soon' lottery_luck web tests README.md docs/OPERATIONS.md
```

## 故障排查

### 页面显示娱乐参考或中性特征

可能原因：

- API 未启动。
- `LOTTERY_LUCK_AI_ENABLED=false`。
- 当前浏览器未在首页“AI 设置”中保存 DeepSeek API Key。
- 本地数据库缺失或路径不正确。

处理：

```bash
curl -s http://127.0.0.1:8017/api/health
PYTHONPATH=. .venv/bin/pytest tests/test_api.py tests/test_data_health.py -q
```

### 数据后台显示缺口

先看后台“最近失败原因”，再按 provider 补采：

```bash
python -m lottery_luck.scheduler --once --provider cwl --games ssq,3d,kl8 --page-size 100
python -m lottery_luck.scheduler --once --provider sports --games dlt,pl3,pl5 --source auto --pages 3 --page-size 100
```

### stale 演练

在 staging 或本地隔离 DB 中准备过期 3D 数据，打开首页和 `/analysis.html?game=3d`，确认：

- 首页“保存为本期方案”禁用。
- 缩水选号（`?game=3d&tool=reduction`）的“生成候选”、“保存手动”、“随机一组”、“保存筛选”全部禁用，
  且禁用原因带最新数据期号与日期，就写在被禁用按钮旁边。
- 走势图、遗漏、出次、冷热、号码查询、号码属性、最近开奖仍可正常读取历史。
- `/api/health` 仍返回 HTTP 200 且 `service=ok`，`data["3d"].status=stale`。
