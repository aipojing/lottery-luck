# 福彩3D留存闭环首发版 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在保留电影感预测首页作为引流入口的前提下，交付一个可上线验证的福彩3D留存版本：数据可信、后台受保护、个人信息不直传第三方 AI，用户可以保存本期方案、进入双层工作台筛选、开奖后复盘，并一键沿用到下一期。

**Architecture:** FastAPI 继续作为单体入口，但把新业务拆成独立领域模块和 APIRouter；SQLite 以惰性建表方式新增方案、复盘和事件表，所有用户数据通过 X-Lottery-Client-Id 隔离。前端继续使用原生 HTML/CSS/JavaScript，新增共享 API 客户端和独立的福彩3D工作台脚本，首页、工作台、详情页只通过稳定 API 契约协作。

**Tech Stack:** Python 3.14、FastAPI、Pydantic v2、SQLite、原生 HTML/CSS/JavaScript、pytest、FastAPI TestClient、Playwright、Node --check。

---

## 交付边界

本计划实现已批准规格的 P0、P1、P2，形成第一个可以真实验证留存的产品版本。

包含：

- 数据自动更新、数据新鲜度契约和过期降级。
- 后台 API 鉴权、公开导航移除后台入口。
- AI 数据最小化、隐私说明、理性娱乐边界。
- 产品事件采集。
- 福彩3D方案保存、列表、详情、删除。
- 开奖后复盘和沿用到下一期。
- 本期助手与专业模式共用一个福彩3D工作台。
- 号码查询、属性、定位统计、出次、遗漏、冷热、走势和快速筛选。

不包含：

- P3 的复式、胆拖、缩水、未出号码、遗漏预警和方案对比。
- P4 的遗漏 K 线、断组推荐、3星复盘和条件历史表现。
- 真实支付、账号登录、专家社区和多彩种复制。

P3 只有在阶段1至2埋点数据达到本文“发布门槛”后才单独写实施计划。P4 还必须先取得3星复盘内页截图、明确统计定义并建立随机基线。

## 文件地图

### 后端新文件

- Create: lottery_luck/admin_auth.py — 管理员令牌校验和 FastAPI dependency。
- Create: lottery_luck/auto_update.py — 可测试的定时数据更新循环和到期判断。
- Create: lottery_luck/product_events.py — product_events 建表、校验和写入。
- Create: lottery_luck/plans.py — 方案、号码、条件快照、复盘的 SQLite 领域函数。
- Create: lottery_luck/plan_routes.py — 方案 CRUD、复盘、沿用 API。
- Create: lottery_luck/workbench_3d.py — 福彩3D统计、号码属性、查询和筛选纯函数。
- Create: lottery_luck/workbench_routes.py — 福彩3D工作台 API。

### 后端修改

- Modify: lottery_luck/api.py — 注册 lifespan、管理员鉴权、方案和工作台 router、健康信息。
- Modify: lottery_luck/repository.py — 暴露单期查询及新领域模块所需的连接边界。
- Modify: lottery_luck/predictor.py — 第三方 AI 只接收派生特征。
- Modify: lottery_luck/scheduler.py — 复用统一自动更新入口。
- Modify: lottery_luck/settings.py — 读取自动更新和后台安全配置。
- Modify: .env.example — 增加管理员令牌、自动更新开关和间隔示例。

### 前端新文件

- Create: web/product-client.js — 匿名 client id、统一 fetch、方案 API 和事件上报。
- Create: web/workbench-3d.js — 福彩3D本期助手、专业模式、方案列表和筛选交互。
- Create: web/workbench-3d.css — 福彩3D工作台专属布局、状态和响应式样式。
- Create: web/privacy.html — 简明隐私、第三方 AI 数据边界和理性娱乐说明。

### 前端修改

- Modify: web/index.html — 加载共享客户端、增加预测后的保存和工作台 CTA、隐私入口。
- Modify: web/app.js — 只在真实福彩3D预测完成后开放保存，不自动跳转。
- Modify: web/analysis.html — 福彩3D时挂载本期助手与专业模式，其他彩种保持现状。
- Modify: web/analysis.js — 把福彩3D分发给独立工作台，保留其他彩种分析逻辑。
- Modify: web/result.html — 从“财运详情”升级为通用方案详情与复盘页。
- Modify: web/result.js — 优先读取服务端方案，支持复盘和沿用下一期，兼容旧本地记录。
- Modify: web/admin.html — 增加会话级令牌输入，不再出现在公开导航。
- Modify: web/admin.js — 管理 API 请求附带令牌，401 时进入锁定态。
- Modify: web/strategy.html — 福彩3D入口引导回工作台专业模式。
- Modify: web/styles.css — 只增加跨页面共享的小型状态样式。
- Modify: README.md — 更新运行、环境变量和首发闭环说明。
- Modify: docs/OPERATIONS.md — 自动更新、管理员令牌、健康检查和回滚步骤。

### 测试新文件

- Create: tests/test_admin_auth.py
- Create: tests/test_auto_update.py
- Create: tests/test_product_events.py
- Create: tests/test_plans.py
- Create: tests/test_plan_routes.py
- Create: tests/test_workbench_3d.py
- Create: tests/test_workbench_routes.py
- Create: tests/test_retention_flow.py
- Create: tests/capture_retention_qa.py

### 测试修改

- Modify: tests/test_api.py — 健康接口、静态资源、后台鉴权和 router 注册契约。
- Modify: tests/test_predictor.py — 验证第三方 AI 不收到原始个人信息。
- Modify: tests/test_frontend_behavior.py — 首页保存 CTA、双层工作台、错误态和旧数据兼容。
- Modify: design-qa.md — 增加福彩3D闭环的桌面、移动端和边界状态证据。

## 数据与接口契约

### 方案创建请求

~~~json
{
  "game_key": "3d",
  "target_issue": "2026195",
  "target_draw_date": "2026-07-13",
  "source_type": "fortune",
  "title": "偏财号 · 第2026195期",
  "entries": [
    {
      "position": 0,
      "main_numbers": [6, 6, 2],
      "special_numbers": [],
      "note": "首页偏财号"
    }
  ],
  "condition_snapshot": {
    "mode": "simple",
    "analysis_window": 30,
    "conditions": {},
    "metrics": {"sum": 14, "span": 4, "group_type": "组三"},
    "latest_data_issue": "2026194",
    "latest_data_date": "2026-07-12"
  }
}
~~~

### 方案详情响应

~~~json
{
  "plan": {
    "id": "plan_01J2C4Y7C9R4XB6JX8M0V5Q2ND",
    "game_key": "3d",
    "target_issue": "2026195",
    "target_draw_date": "2026-07-13",
    "source_type": "fortune",
    "status": "pending_review",
    "entries": [{"id": 1, "position": 0, "main_numbers": [6, 6, 2], "special_numbers": [], "note": "首页偏财号"}],
    "condition_snapshot": {"mode": "simple", "analysis_window": 30, "conditions": {}, "metrics": {"sum": 14, "span": 4}},
    "review": null
  }
}
~~~

### 数据新鲜度

所有会给用户“本期”结论的接口都返回：

~~~json
{
  "freshness": {
    "status": "fresh",
    "latest_issue": "2026194",
    "latest_date": "2026-07-12",
    "staleness_days": 0,
    "can_claim_current": true,
    "message": "数据已更新至第2026194期",
    "last_successful_update": "2026-07-12T01:30:00+00:00",
    "sync_error": ""
  }
}
~~~

status 只允许 fresh、attention、stale、empty。只有 fresh 和 attention 可以生成“本期”统计；stale 和 empty 必须返回 can_claim_current=false，前端禁用保存为本期方案和专业筛选提交。最近一次同步失败时仍展示最后成功期号，并在 sync_error 返回经过清洗的失败摘要，不静默掩盖。

## Task 1: 固化数据新鲜度契约与健康接口

**Files:**
- Modify: tests/test_data_health.py
- Modify: tests/test_api.py
- Modify: lottery_luck/data_health.py
- Modify: lottery_luck/api.py

- [ ] **Step 1: 写入失败的 freshness 测试**

在 tests/test_data_health.py 增加：

~~~python
def test_public_freshness_disables_current_claims_when_data_is_stale():
    report = build_public_freshness(
        {
            "game_key": "3d",
            "latest_issue": "2026182",
            "latest_date": "2026-06-29",
            "draw_count": 100,
        },
        today="2026-07-12",
    )

    assert report == {
        "status": "stale",
        "latest_issue": "2026182",
        "latest_date": "2026-06-29",
        "staleness_days": 13,
        "can_claim_current": False,
        "message": "数据停留在第2026182期，暂不提供本期结论",
        "last_successful_update": "",
        "sync_error": "",
    }
~~~

在 tests/test_api.py 把 health 断言改为：

~~~python
def test_health_reports_service_and_data_readiness():
    response = client.get("/api/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] in {"ok", "degraded"}
    assert payload["service"] == "ok"
    assert "data" in payload
    assert "3d" in payload["data"]
    assert "can_claim_current" in payload["data"]["3d"]
~~~

- [ ] **Step 2: 运行并确认失败**

Run: PYTHONPATH=. .venv/bin/pytest tests/test_data_health.py::test_public_freshness_disables_current_claims_when_data_is_stale tests/test_api.py::test_health_reports_service_and_data_readiness -q

Expected: FAIL，build_public_freshness 尚不存在，health 仍只有 status。

- [ ] **Step 3: 实现公开 freshness 纯函数**

在 lottery_luck/data_health.py 增加：

~~~python
def build_public_freshness(
    game: dict[str, Any],
    *,
    today: str | None = None,
    logs: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    current = date.fromisoformat(today or date.today().isoformat())
    latest_text = str(game.get("latest_date") or "")
    latest_issue = str(game.get("latest_issue") or "")
    if not latest_text:
        return {
            "status": "empty",
            "latest_issue": latest_issue,
            "latest_date": "",
            "staleness_days": None,
            "can_claim_current": False,
            "message": "暂无可用开奖数据",
            "last_successful_update": "",
            "sync_error": _public_sync_error(logs or []),
        }

    staleness_days = max(0, (current - date.fromisoformat(latest_text)).days)
    if staleness_days <= 2:
        status = "fresh"
    elif staleness_days <= 4:
        status = "attention"
    else:
        status = "stale"
    can_claim_current = status in {"fresh", "attention"}
    message = (
        f"数据已更新至第{latest_issue}期"
        if can_claim_current
        else f"数据停留在第{latest_issue}期，暂不提供本期结论"
    )
    return {
        "status": status,
        "latest_issue": latest_issue,
        "latest_date": latest_text,
        "staleness_days": staleness_days,
        "can_claim_current": can_claim_current,
        "message": message,
        "last_successful_update": _last_successful_update(logs or []),
        "sync_error": _public_sync_error(logs or []),
    }


def _last_successful_update(logs: list[dict[str, Any]]) -> str:
    for log in sorted(logs, key=lambda item: str(item.get("finished_at") or ""), reverse=True):
        if log.get("status") == "success":
            return str(log.get("finished_at") or "")
    return ""


def _public_sync_error(logs: list[dict[str, Any]]) -> str:
    ordered = sorted(logs, key=lambda item: str(item.get("finished_at") or ""), reverse=True)
    if not ordered or ordered[0].get("status") == "success":
        return ""
    raw = str(ordered[0].get("error") or "最近一次数据同步失败")
    return raw.replace("\n", " ")[:160]
~~~

调用方先按 game_key 过滤日志再传入。api.py 的 health 通过 repo.list_games() 为 FRONTEND_GAME_KEYS 构建 freshness map；任一彩种 stale 或 empty 时服务 status 为 degraded，但 HTTP 仍返回 200，便于运维探针区分“服务宕机”和“数据退化”。

- [ ] **Step 4: 运行目标测试**

Run: PYTHONPATH=. .venv/bin/pytest tests/test_data_health.py tests/test_api.py -q

Expected: PASS。

- [ ] **Step 5: 提交**

~~~bash
git add lottery_luck/data_health.py lottery_luck/api.py tests/test_data_health.py tests/test_api.py
git commit -m "feat: expose public data freshness"
~~~

## Task 2: 实现可关闭、可测试的自动数据更新

**Files:**
- Create: lottery_luck/auto_update.py
- Modify: lottery_luck/api.py
- Modify: lottery_luck/scheduler.py
- Modify: lottery_luck/settings.py
- Modify: .env.example
- Test: tests/test_auto_update.py

- [ ] **Step 1: 写入到期判断和单飞测试**

~~~python
def test_run_due_updates_skips_recent_success_and_runs_stale_provider():
    calls = []
    state = {
        "cwl": {"finished_at": "2026-07-12T01:30:00+00:00", "status": "success"},
        "sports": {"finished_at": "2026-07-11T20:00:00+00:00", "status": "success"},
    }

    result = run_due_updates(
        now=datetime(2026, 7, 12, 2, 0, tzinfo=timezone.utc),
        interval_seconds=21600,
        latest_runs=state,
        runner=lambda provider: calls.append(provider) or {"provider": provider, "status": "success"},
    )

    assert calls == ["sports"]
    assert result["skipped"] == ["cwl"]
    assert result["ran"][0]["provider"] == "sports"
~~~

- [ ] **Step 2: 运行并确认失败**

Run: PYTHONPATH=. .venv/bin/pytest tests/test_auto_update.py -q

Expected: FAIL，auto_update 模块不存在。

- [ ] **Step 3: 实现自动更新控制器**

auto_update.py 提供：

~~~python
@dataclass(frozen=True)
class AutoUpdateConfig:
    enabled: bool
    interval_seconds: int


def config_from_env() -> AutoUpdateConfig:
    enabled = os.getenv("LOTTERY_LUCK_AUTO_UPDATE_ENABLED", "false").lower() in {
        "1", "true", "yes", "on"
    }
    interval = max(900, int(os.getenv("LOTTERY_LUCK_AUTO_UPDATE_INTERVAL_SECONDS", "21600")))
    return AutoUpdateConfig(enabled=enabled, interval_seconds=interval)


def run_due_updates(
    *,
    now: datetime,
    interval_seconds: int,
    latest_runs: dict[str, dict[str, Any]],
    runner: Callable[[str], dict[str, Any]],
) -> dict[str, Any]:
    ran: list[dict[str, Any]] = []
    skipped: list[str] = []
    for provider in ("cwl", "sports"):
        finished = str((latest_runs.get(provider) or {}).get("finished_at") or "")
        last_time = datetime.fromisoformat(finished) if finished else None
        if last_time and (now - last_time).total_seconds() < interval_seconds:
            skipped.append(provider)
            continue
        ran.append(runner(provider))
    return {"ran": ran, "skipped": skipped}


async def update_loop(config: AutoUpdateConfig, stop: asyncio.Event) -> None:
    while not stop.is_set():
        await asyncio.to_thread(run_repository_updates, config.interval_seconds)
        try:
            await asyncio.wait_for(stop.wait(), timeout=config.interval_seconds)
        except TimeoutError:
            continue
~~~

run_repository_updates 复用 scheduler.run_once，并用进程级 asyncio.Lock 防止同一进程重复运行。api.py 使用 FastAPI lifespan 启停循环；开关默认 false，生产环境显式启用。scheduler.py 的 CLI 继续可单次执行，但调用同一 runner。

- [ ] **Step 4: 更新环境示例**

~~~dotenv
LOTTERY_LUCK_ADMIN_TOKEN=replace-with-a-long-random-token
LOTTERY_LUCK_AUTO_UPDATE_ENABLED=false
LOTTERY_LUCK_AUTO_UPDATE_INTERVAL_SECONDS=21600
~~~

- [ ] **Step 5: 运行测试**

Run: PYTHONPATH=. .venv/bin/pytest tests/test_auto_update.py tests/test_tasks.py tests/test_crawler.py tests/test_sports_crawler.py -q

Expected: PASS，测试不得发真实网络请求。

- [ ] **Step 6: 提交**

~~~bash
git add lottery_luck/auto_update.py lottery_luck/api.py lottery_luck/scheduler.py lottery_luck/settings.py .env.example tests/test_auto_update.py
git commit -m "feat: add controlled data auto updates"
~~~

## Task 3: 保护所有后台 API 并移除公开入口

**Files:**
- Create: lottery_luck/admin_auth.py
- Create: tests/test_admin_auth.py
- Modify: lottery_luck/api.py
- Modify: web/admin.html
- Modify: web/admin.js
- Modify: web/index.html
- Modify: web/analysis.html
- Modify: web/result.html
- Modify: web/strategy.html
- Modify: tests/test_api.py

- [ ] **Step 1: 写入后台鉴权失败测试**

~~~python
def test_admin_dependency_rejects_missing_and_wrong_tokens(monkeypatch):
    monkeypatch.setenv("LOTTERY_LUCK_ADMIN_TOKEN", "test-admin-secret")

    assert client.get("/api/admin/settings").status_code == 401
    assert client.get(
        "/api/admin/settings",
        headers={"X-Lottery-Admin-Token": "wrong"},
    ).status_code == 401
    assert client.get(
        "/api/admin/settings",
        headers={"X-Lottery-Admin-Token": "test-admin-secret"},
    ).status_code == 200
~~~

再参数化覆盖六个 /api/admin/* GET/POST 路由，确保没有漏网的写接口。

- [ ] **Step 2: 运行并确认失败**

Run: PYTHONPATH=. .venv/bin/pytest tests/test_admin_auth.py -q

Expected: FAIL，现有后台接口无需令牌。

- [ ] **Step 3: 实现常量时间令牌校验**

~~~python
def require_admin(
    x_lottery_admin_token: Annotated[
        str | None,
        Header(alias="X-Lottery-Admin-Token"),
    ] = None,
) -> None:
    expected = os.getenv("LOTTERY_LUCK_ADMIN_TOKEN", "").strip()
    supplied = str(x_lottery_admin_token or "").strip()
    if not expected or not supplied or not secrets.compare_digest(expected, supplied):
        raise HTTPException(
            status_code=401,
            detail="admin authorization required",
            headers={"WWW-Authenticate": "LotteryAdmin"},
        )
~~~

api.py 中每个 /api/admin/* 路由增加 Depends(require_admin)。测试环境不能通过“未配置令牌”自动放行。

- [ ] **Step 4: 管理页增加会话令牌输入**

admin.js 只把令牌保存在 sessionStorage，统一 fetchJson 附加 X-Lottery-Admin-Token；不写 localStorage，不输出到 DOM，不出现在 URL。401 时清空业务面板并显示令牌输入，不继续重试。

- [ ] **Step 5: 从公开导航移除后台链接**

首页、分析、策略、详情页均不展示“数据后台”。admin.html 保持可直接访问，但未授权时只显示锁定态。

- [ ] **Step 6: 运行测试与语法检查**

Run: PYTHONPATH=. .venv/bin/pytest tests/test_admin_auth.py tests/test_api.py -q

Run: node --check web/admin.js

Expected: 全部 PASS。

- [ ] **Step 7: 提交**

~~~bash
git add lottery_luck/admin_auth.py lottery_luck/api.py web/admin.html web/admin.js web/index.html web/analysis.html web/result.html web/strategy.html tests/test_admin_auth.py tests/test_api.py
git commit -m "fix: require authorization for admin APIs"
~~~

## Task 4: 第三方 AI 数据最小化与公开隐私边界

**Files:**
- Modify: lottery_luck/predictor.py
- Modify: tests/test_predictor.py
- Create: web/privacy.html
- Modify: web/index.html
- Modify: web/result.html
- Modify: README.md
- Modify: tests/test_api.py

- [ ] **Step 1: 写入原始个人信息泄露测试**

使用捕获 provider：

~~~python
class CapturingProvider:
    def __init__(self):
        self.context = None

    def extract_features(self, context):
        self.context = context
        return {"overall_luck": 50, "preferred_elements": []}


def test_ai_context_contains_only_derived_personal_features(repo):
    provider = CapturingProvider()
    engine = PredictionEngine(repo, provider)
    personal = PersonalInput(
        name="测试姓名",
        birth_date="1990-02-03",
        birth_hour="子",
        birth_place="敏感出生地",
        current_city="敏感当前城市",
    )

    engine.predict("3d", personal, today="2026-07-12")

    serialized = json.dumps(provider.context, ensure_ascii=False)
    assert "测试姓名" not in serialized
    assert "1990-02-03" not in serialized
    assert "敏感出生地" not in serialized
    assert "敏感当前城市" not in serialized
    assert set(provider.context["personal_features"]) == {
        "birth_vector", "birth_hour_known", "calendar_type", "location_relation"
    }
~~~

- [ ] **Step 2: 运行并确认失败**

Run: PYTHONPATH=. .venv/bin/pytest tests/test_predictor.py::test_ai_context_contains_only_derived_personal_features -q

Expected: FAIL，现有 _extract_ai_feature 仍向 provider 传原始字段。

- [ ] **Step 3: 建立派生上下文**

predictor.py 中 _extract_ai_feature 只构建：

~~~python
personal_features = {
    "birth_vector": birth_vector(personal),
    "birth_hour_known": personal.birth_hour != "unknown",
    "calendar_type": personal.calendar_type,
    "location_relation": (
        "same"
        if personal.birth_place and personal.birth_place == personal.current_city
        else "different"
        if personal.birth_place and personal.current_city
        else "incomplete"
    ),
}
~~~

本地 deterministic 算法仍可使用 PersonalInput；只有第三方 provider 边界必须最小化。日志和异常消息不得包含 request body。

- [ ] **Step 4: 增加隐私与责任页面**

privacy.html 明确：

- 姓名、生日、出生地和当前城市仅用于本次本地计算，不直接发送给第三方 AI。
- 第三方 AI 仅接收派生、不可直接识别身份的特征。
- 本产品仅限成年人娱乐和数据分析，不构成投注、收益或中奖承诺。
- 用户可删除已保存方案；删除后关联号码、条件快照和复盘一并删除。

首页表单附近增加简短说明和隐私入口；详情页保留理性娱乐提示。

- [ ] **Step 5: 运行测试**

Run: PYTHONPATH=. .venv/bin/pytest tests/test_predictor.py tests/test_api.py -q

Expected: PASS。

- [ ] **Step 6: 提交**

~~~bash
git add lottery_luck/predictor.py tests/test_predictor.py web/privacy.html web/index.html web/result.html README.md tests/test_api.py
git commit -m "fix: minimize personal data sent to AI"
~~~

## Task 5: 建立最小产品事件管道

**Files:**
- Create: lottery_luck/product_events.py
- Create: tests/test_product_events.py
- Modify: lottery_luck/repository.py
- Modify: lottery_luck/api.py
- Modify: tests/test_api.py

- [ ] **Step 1: 写入事件白名单和脱敏测试**

~~~python
def test_record_event_accepts_whitelisted_event_and_rejects_pii():
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row

    event = record_event(
        connection,
        client_id="client-1",
        event_name="plan_saved",
        properties={"game_key": "3d", "source_type": "fortune", "entry_count": 1},
    )
    assert event["event_name"] == "plan_saved"

    with pytest.raises(ValueError, match="unsupported property"):
        record_event(
            connection,
            client_id="client-1",
            event_name="plan_saved",
            properties={"name": "不应采集"},
        )
~~~

事件名白名单严格沿用批准规格：

prediction_completed、plan_saved、workbench_opened、plan_edited、review_viewed、plan_carried_forward。

属性白名单固定为：

game_key、source_type、mode、window、entry_count、candidate_count、freshness_status、review_status。

- [ ] **Step 2: 运行并确认失败**

Run: PYTHONPATH=. .venv/bin/pytest tests/test_product_events.py -q

Expected: FAIL，product_events 模块不存在。

- [ ] **Step 3: 实现表和写入函数**

~~~sql
CREATE TABLE IF NOT EXISTS product_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  client_id TEXT NOT NULL,
  event_name TEXT NOT NULL,
  properties TEXT NOT NULL DEFAULT '{}',
  occurred_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_product_events_client_time
ON product_events (client_id, occurred_at DESC);
~~~

record_event 先校验 event_name、属性 key、JSON 编码后长度不超过 2048 字节，再写入并 commit。

核心写入函数：

~~~python
def record_event(
    connection: sqlite3.Connection,
    *,
    client_id: str,
    event_name: str,
    properties: dict[str, Any],
) -> dict[str, Any]:
    normalized_client = str(client_id or "").strip()[:96]
    if not normalized_client:
        raise ValueError("client_id is required")
    if event_name not in ALLOWED_EVENT_NAMES:
        raise ValueError("unsupported event name")
    unsupported = set(properties) - ALLOWED_PROPERTY_NAMES
    if unsupported:
        raise ValueError(f"unsupported property: {sorted(unsupported)[0]}")
    encoded = json.dumps(properties, ensure_ascii=False, separators=(",", ":"))
    if len(encoded.encode("utf-8")) > 2048:
        raise ValueError("event properties are too large")
    ensure_product_events_table(connection)
    cursor = connection.execute(
        "INSERT INTO product_events (client_id, event_name, properties) VALUES (?, ?, ?)",
        (normalized_client, event_name, encoded),
    )
    connection.commit()
    return {
        "id": int(cursor.lastrowid),
        "client_id": normalized_client,
        "event_name": event_name,
        "properties": properties,
    }
~~~

- [ ] **Step 4: 增加 POST /api/events**

请求：

~~~python
class ProductEventRequest(BaseModel):
    event_name: str = Field(min_length=1, max_length=64)
    properties: dict[str, Any] = Field(default_factory=dict)
~~~

缺少 X-Lottery-Client-Id 返回 400；合法事件返回 202 和 {"accepted": True}；非法事件/属性返回 422；不提供公开事件列表接口。

- [ ] **Step 5: 运行测试**

Run: PYTHONPATH=. .venv/bin/pytest tests/test_product_events.py tests/test_api.py -q

Expected: PASS。

- [ ] **Step 6: 提交**

~~~bash
git add lottery_luck/product_events.py lottery_luck/repository.py lottery_luck/api.py tests/test_product_events.py tests/test_api.py
git commit -m "feat: record privacy-safe product events"
~~~

## Task 6: 实现福彩3D方案持久化领域

**Files:**
- Create: lottery_luck/plans.py
- Create: tests/test_plans.py
- Modify: lottery_luck/repository.py

- [ ] **Step 1: 写入 CRUD、隔离和级联删除测试**

至少覆盖：

~~~python
def test_plan_crud_is_scoped_by_client_and_delete_cascades(db_connection):
    created = create_plan(
        db_connection,
        client_id="client-a",
        payload=sample_plan_payload(),
    )

    assert get_plan(db_connection, "client-a", created["id"])["entries"][0]["main_numbers"] == [6, 6, 2]
    assert get_plan(db_connection, "client-b", created["id"]) is None

    assert delete_plan(db_connection, "client-a", created["id"]) is True
    assert get_plan(db_connection, "client-a", created["id"]) is None
    assert db_connection.execute(
        "SELECT COUNT(*) FROM lottery_plan_entries WHERE plan_id = ?",
        (created["id"],),
    ).fetchone()[0] == 0
~~~

另测：只允许 game_key=3d；每个主号必须是长度3且0至9；最多50组；标题最大80字；client id 最大96字；request_id 非空时同一 client 幂等；request_id 为空时允许用户为同一期保存多个方案；相同来源和相同号码返回 duplicate_warning 但不强制阻止。

- [ ] **Step 2: 运行并确认失败**

Run: PYTHONPATH=. .venv/bin/pytest tests/test_plans.py -q

Expected: FAIL，plans 模块不存在。

- [ ] **Step 3: 建立四张表**

~~~sql
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS lottery_plans (
  id TEXT PRIMARY KEY,
  client_id TEXT NOT NULL,
  game_key TEXT NOT NULL CHECK (game_key = '3d'),
  target_issue TEXT NOT NULL,
  target_draw_date TEXT NOT NULL,
  source_type TEXT NOT NULL CHECK (source_type IN ('fortune', 'manual', 'filter', 'random', 'carried')),
  request_id TEXT NOT NULL DEFAULT '',
  title TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'saved' CHECK (status IN ('draft', 'saved', 'pending_review', 'reviewed', 'expired')),
  carried_from_plan_id TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_lottery_plans_idempotency
ON lottery_plans (client_id, request_id)
WHERE request_id != '';

CREATE TABLE IF NOT EXISTS lottery_plan_entries (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  plan_id TEXT NOT NULL REFERENCES lottery_plans(id) ON DELETE CASCADE,
  position INTEGER NOT NULL DEFAULT 0,
  main_numbers TEXT NOT NULL,
  special_numbers TEXT NOT NULL DEFAULT '[]',
  note TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS plan_condition_snapshots (
  plan_id TEXT PRIMARY KEY REFERENCES lottery_plans(id) ON DELETE CASCADE,
  mode TEXT NOT NULL,
  analysis_window INTEGER NOT NULL,
  conditions_json TEXT NOT NULL DEFAULT '{}',
  metrics_json TEXT NOT NULL DEFAULT '{}',
  latest_data_issue TEXT NOT NULL,
  latest_data_date TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS plan_reviews (
  plan_id TEXT PRIMARY KEY REFERENCES lottery_plans(id) ON DELETE CASCADE,
  draw_issue TEXT NOT NULL,
  draw_numbers TEXT NOT NULL,
  review_status TEXT NOT NULL,
  direct_hit INTEGER NOT NULL DEFAULT 0,
  group_type TEXT NOT NULL,
  matched_positions TEXT NOT NULL DEFAULT '[]',
  matched_conditions TEXT NOT NULL DEFAULT '[]',
  missed_conditions TEXT NOT NULL DEFAULT '[]',
  result_json TEXT NOT NULL DEFAULT '{}',
  reviewed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
~~~

SQLite 连接必须执行 PRAGMA foreign_keys=ON。JSON 统一 ensure_ascii=False、紧凑分隔符编码；读出时统一解码为 list/dict。

状态转换固定为：编辑中的本地草稿为 draft；服务端保存成功为 saved；目标日期到达但开奖尚未同步为 pending_review；真实开奖复盘完成为 reviewed；目标期异常跳过且无法再补齐时才由运维标记 expired。读取方案时可以根据日期把 saved 推进为 pending_review，但不能在 GET 中伪造 reviewed。

- [ ] **Step 4: 实现领域 API**

plans.py 导出：

~~~python
create_plan(connection, client_id, payload) -> dict
list_plans(connection, client_id, game_key="3d", limit=50) -> list[dict]
get_plan(connection, client_id, plan_id) -> dict | None
update_plan(connection, client_id, plan_id, changes) -> dict | None
delete_plan(connection, client_id, plan_id) -> bool
review_plan(connection, client_id, plan_id, draw) -> dict
carry_forward_plan(connection, client_id, plan_id, latest_draw) -> dict
~~~

同时提供唯一的目标期推导函数，方案沿用和预测首页共用，不能各自拼期号：

~~~python
def resolve_3d_target(
    latest_issue: str,
    latest_draw_date: str,
    target_draw_date: str | None = None,
) -> dict[str, str]:
    latest_date = date.fromisoformat(latest_draw_date)
    target_date = date.fromisoformat(target_draw_date) if target_draw_date else latest_date + timedelta(days=1)
    if target_date <= latest_date:
        raise ValueError("target draw date must be after latest draw")
    current_year = str(target_date.year)
    if target_date.year == latest_date.year:
        sequence = int(str(latest_issue)[-3:]) + (target_date - latest_date).days
    else:
        sequence = (target_date - date(target_date.year, 1, 1)).days + 1
    return {
        "target_issue": f"{current_year}{sequence:03d}",
        "target_draw_date": target_date.isoformat(),
    }
~~~

tests/test_plans.py 必须覆盖普通递增、把预测的 best_draw_date 映射到对应期号，以及跨年重置到001期。若官方数据出现停开，后续由抓取到的真实期号校正，已开奖目标期不会被重复保存。

review_plan 对每一组号码同时计算 direct_hit、matched_positions 和 any_position_hits，并把保存时 metrics_json/conditions_json 与开奖结果对照为 matched_conditions、missed_conditions；组三/豹子重复数字使用 Counter 交集计算 any_position_hits，不能用 set。复盘只读方案快照，不用开奖后的最新指标回算“当时依据”。

- [ ] **Step 5: 运行测试**

Run: PYTHONPATH=. .venv/bin/pytest tests/test_plans.py tests/test_repository.py -q

Expected: PASS。

- [ ] **Step 6: 提交**

~~~bash
git add lottery_luck/plans.py lottery_luck/repository.py tests/test_plans.py
git commit -m "feat: persist scoped 3d plans"
~~~

## Task 7: 暴露方案 CRUD、复盘和沿用 API

**Files:**
- Create: lottery_luck/plan_routes.py
- Create: tests/test_plan_routes.py
- Modify: lottery_luck/api.py
- Modify: lottery_luck/repository.py

- [ ] **Step 1: 写入 API 契约测试**

覆盖：

- POST /api/plans 无 client id 返回400。
- POST /api/plans 创建返回201。
- 相同 request_id 重试返回同一 plan id。
- GET /api/plans 只能看到当前 client 的方案。
- GET/PATCH/DELETE /api/plans/{id} 对其他 client 返回404。
- POST /api/plans/{id}/review 在目标期开奖数据不存在时返回409且不写假复盘。
- POST /api/plans/{id}/carry-forward 创建新方案并保留 carried_from_plan_id。

示例：

~~~python
def test_plan_review_uses_target_issue_draw(client_with_plan_repo):
    response = client_with_plan_repo.post(
        "/api/plans/plan-test/review",
        headers={"X-Lottery-Client-Id": "client-a"},
    )

    assert response.status_code == 200
    review = response.json()["plan"]["review"]
    assert review["draw_issue"] == "2026195"
    assert review["entries"][0]["matched_positions"] == [0, 1, 2]
    assert review["direct_hit"] is True
~~~

- [ ] **Step 2: 运行并确认失败**

Run: PYTHONPATH=. .venv/bin/pytest tests/test_plan_routes.py -q

Expected: FAIL，router 尚不存在。

- [ ] **Step 3: 实现 Pydantic schema 和 router**

plan_routes.py 使用 APIRouter(prefix="/api")。create request 严格使用：

~~~python
class PlanEntryInput(BaseModel):
    position: int = Field(default=0, ge=0, le=49)
    main_numbers: list[int] = Field(min_length=3, max_length=3)
    special_numbers: list[int] = Field(default_factory=list, max_length=0)
    note: str = Field(default="", max_length=120)


class PlanConditionInput(BaseModel):
    mode: Literal["simple", "pro"]
    analysis_window: Literal[30, 60, 120]
    conditions: dict[str, Any] = Field(default_factory=dict)
    metrics: dict[str, Any] = Field(default_factory=dict)
    latest_data_issue: str = Field(min_length=1, max_length=32)
    latest_data_date: date


class PlanCreateRequest(BaseModel):
    game_key: Literal["3d"]
    target_issue: str = Field(min_length=1, max_length=32)
    target_draw_date: date
    source_type: Literal["fortune", "manual", "filter", "random", "carried"]
    request_id: str = Field(default="", max_length=96)
    title: str = Field(min_length=1, max_length=80)
    entries: list[PlanEntryInput] = Field(min_length=1, max_length=50)
    condition_snapshot: PlanConditionInput
~~~

router 只接收 client id，业务函数仍二次校验。review route 从 repo 按 plan.target_issue 查询真实 3D draw；不存在时保持 pending_review 并返回409 detail="draw is not available"。创建方案时若目标期已开奖，返回409 detail="target issue is already drawn"，前端改为查看复盘或创建下一期。carry-forward 的目标期号与日期由服务端根据最新一期和开奖日历推导，客户端不能任意回填已开奖期；新方案 source_type 固定为 carried，carried_from_plan_id 指向旧方案，并复制 entries 和条件快照但清空 review。增加跨年测试，确保年末最后一期之后进入新年001期。

- [ ] **Step 4: 注册 router**

api.py 在 app.mount 之前 include_router(plan_router)。保持静态站点挂载最后执行。

- [ ] **Step 5: 运行测试**

Run: PYTHONPATH=. .venv/bin/pytest tests/test_plan_routes.py tests/test_api.py -q

Expected: PASS。

- [ ] **Step 6: 提交**

~~~bash
git add lottery_luck/plan_routes.py lottery_luck/api.py lottery_luck/repository.py tests/test_plan_routes.py
git commit -m "feat: expose 3d plan lifecycle APIs"
~~~

## Task 8: 实现福彩3D统计与筛选纯函数

**Files:**
- Create: lottery_luck/workbench_3d.py
- Create: tests/test_workbench_3d.py

- [ ] **Step 1: 写入号码属性测试**

~~~python
@pytest.mark.parametrize(
    ("numbers", "expected"),
    [
        ([6, 6, 2], {"sum": 14, "sum_tail": 4, "span": 4, "group_type": "组三", "odd_even": "0:3", "big_small": "2:1", "mod3": "3:0:0", "repeat_count": 1}),
        ([1, 1, 1], {"sum": 3, "sum_tail": 3, "span": 0, "group_type": "豹子", "odd_even": "3:0", "big_small": "0:3", "mod3": "0:3:0", "repeat_count": 2}),
        ([0, 4, 9], {"sum": 13, "sum_tail": 3, "span": 9, "group_type": "组六", "odd_even": "1:2", "big_small": "1:2", "mod3": "2:1:0", "repeat_count": 0}),
    ],
)
def test_number_attributes(numbers, expected):
    attributes = number_attributes(numbers)
    assert attributes | expected == attributes
    assert "prime_composite" in attributes
    assert "consecutive_pairs" in attributes
    assert "adjacent_pairs" in attributes
~~~

- [ ] **Step 2: 写入位置出次和遗漏测试**

用按时间倒序的固定 draws 验证：

- 百位数字6出现次数与十位数字6分别统计。
- 当前遗漏从最新一期开始数，最新命中为0。
- 每个位置和数字同时返回当前遗漏、平均遗漏、最大遗漏和历史分位。
- 冷热分层同时使用固定窗口频次和当前遗漏，响应带 definition，不能只按单一频次贴标签。
- 重复数字不跨位置串算。
- window 只允许30、60、120。
- 空数据返回零矩阵和 empty freshness，不抛 IndexError。

- [ ] **Step 3: 写入筛选边界测试**

filter_candidates 从000至999稳定枚举，支持：

sum_min/sum_max、span_min/span_max、types、odd_counts、big_counts、position_include、position_exclude、max_results。

测试顺序固定，max_results 最大200，冲突条件返回空列表和 total=0。

- [ ] **Step 4: 运行并确认失败**

Run: PYTHONPATH=. .venv/bin/pytest tests/test_workbench_3d.py -q

Expected: FAIL，workbench_3d 模块不存在。

- [ ] **Step 5: 实现纯函数**

模块导出：

~~~python
number_attributes(numbers: list[int]) -> dict[str, Any]
query_number(number_text: str, draws: list[dict[str, Any]]) -> dict[str, Any]
build_position_stats(draws: list[dict[str, Any]], window: int) -> dict[str, Any]
build_workbench_summary(draws: list[dict[str, Any]], window: int) -> dict[str, Any]
filter_candidates(filters: dict[str, Any]) -> dict[str, Any]
~~~

组三/豹子判断：

~~~python
unique_count = len(set(numbers))
digit_type = "豹子" if unique_count == 1 else "组三" if unique_count == 2 else "组六"
~~~

大小定义固定为0至4小、5至9大；012路按 digit % 3；质数固定为2、3、5、7；奇偶和大小结果都用“命中数:其余数”。和值、和尾、跨度、质合、豹子/组三/组六、重号、连号和相邻关系必须一次返回，避免不同页面重复定义。

- [ ] **Step 6: 运行测试**

Run: PYTHONPATH=. .venv/bin/pytest tests/test_workbench_3d.py -q

Expected: PASS。

- [ ] **Step 7: 提交**

~~~bash
git add lottery_luck/workbench_3d.py tests/test_workbench_3d.py
git commit -m "feat: add deterministic 3d workbench stats"
~~~

## Task 9: 暴露福彩3D工作台 API 并强制新鲜度降级

**Files:**
- Create: lottery_luck/workbench_routes.py
- Create: tests/test_workbench_routes.py
- Modify: lottery_luck/api.py
- Modify: lottery_luck/repository.py

- [ ] **Step 1: 写入 API 测试**

覆盖：

~~~python
def test_stale_workbench_summary_is_read_only(stale_repo):
    app.dependency_overrides[get_repository] = lambda: stale_repo
    try:
        response = client.get("/api/workbench/3d/summary?window=30&today=2026-07-12")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["freshness"]["status"] == "stale"
    assert payload["freshness"]["can_claim_current"] is False
    assert payload["actions"]["can_filter_current"] is False
~~~

另测：

- POST /api/3d/number-query 接受 "662" 和 [6,6,2]，非法长度返回422。
- POST /api/3d/filter 新鲜数据返回 candidates 和 total。
- POST /api/3d/filter 过期数据返回409，不把历史结果包装成本期候选。
- summary 返回 active plan count、latest plan 和 position stats。

- [ ] **Step 2: 运行并确认失败**

Run: PYTHONPATH=. .venv/bin/pytest tests/test_workbench_routes.py -q

Expected: FAIL，workbench router 不存在。

- [ ] **Step 3: 实现 router**

workbench_routes.py 提供：

~~~text
GET  /api/workbench/3d/summary
POST /api/3d/number-query
POST /api/3d/filter
~~~

所有响应都包含 freshness。summary 和 number-query 可在 stale 状态阅读历史统计，但 actions 明确禁用“本期”动作；filter 在 stale/empty 状态返回409。

- [ ] **Step 4: 注册 router 并运行测试**

Run: PYTHONPATH=. .venv/bin/pytest tests/test_workbench_routes.py tests/test_analysis.py tests/test_api.py -q

Expected: PASS，现有 /api/analysis/3d 契约不回归。

- [ ] **Step 5: 提交**

~~~bash
git add lottery_luck/workbench_routes.py lottery_luck/api.py lottery_luck/repository.py tests/test_workbench_routes.py
git commit -m "feat: expose freshness-aware 3d workbench APIs"
~~~

## Task 10: 建立共享浏览器客户端与事件上报

**Files:**
- Create: web/product-client.js
- Modify: web/index.html
- Modify: web/analysis.html
- Modify: web/result.html
- Modify: tests/test_api.py
- Modify: tests/test_frontend_behavior.py

- [ ] **Step 1: 写入静态资源和身份稳定测试**

~~~python
def test_product_client_is_loaded_before_page_scripts():
    for path, page_script in [
        ("/", "./app.js"),
        ("/analysis.html?game=3d", "./analysis.js"),
        ("/result.html", "./result.js"),
    ]:
        html = client.get(path).text
        assert "./product-client.js?v=" in html
        assert html.index("./product-client.js?v=") < html.index(page_script)
~~~

Playwright 再验证同一浏览器三个页面发送相同 X-Lottery-Client-Id。

- [ ] **Step 2: 运行并确认失败**

Run: PYTHONPATH=. .venv/bin/pytest tests/test_api.py::test_product_client_is_loaded_before_page_scripts -q

Expected: FAIL，资源尚不存在。

- [ ] **Step 3: 实现 window.LotteryProduct**

product-client.js 负责：

~~~javascript
let memoryClientId = "";

function clientId() {
  const key = "lotteryLuck.clientId.v1";
  try {
    let value = localStorage.getItem(key);
    if (!value) {
      value = crypto.randomUUID();
      localStorage.setItem(key, value);
    }
    return value;
  } catch (error) {
    if (!memoryClientId) memoryClientId = crypto.randomUUID();
    return memoryClientId;
  }
}

async function request(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      "X-Lottery-Client-Id": clientId(),
      ...(options.headers || {}),
    },
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    const error = new Error(payload.detail || "请求失败");
    error.status = response.status;
    throw error;
  }
  return payload;
}
~~~

暴露 request、track、createPlan、listPlans、getPlan、reviewPlan、carryForward。track 使用 navigator.sendBeacon 不可附自定义 header，因此这里统一用 fetch keepalive=true，并吞掉埋点失败，不阻断主流程。

createPlan 遇到网络错误时把不含个人资料的请求写入 lotteryLuck.pendingPlans.v1，并保持原 request_id；浏览器 online 事件和下次打开工作台时重试。localStorage 不可用时只保留当前内存草稿，并明确显示“尚未保存”，不能宣称已经落盘。增加测试验证待同步重试不会重复创建。

- [ ] **Step 4: 运行测试与语法检查**

Run: PYTHONPATH=. .venv/bin/pytest tests/test_api.py tests/test_frontend_behavior.py -q

Run: node --check web/product-client.js

Expected: PASS。

- [ ] **Step 5: 提交**

~~~bash
git add web/product-client.js web/index.html web/analysis.html web/result.html tests/test_api.py tests/test_frontend_behavior.py
git commit -m "feat: add shared product API client"
~~~

## Task 11: 首页预测后提供显式保存与工作台入口

**Files:**
- Modify: lottery_luck/api.py
- Modify: web/index.html
- Modify: web/app.js
- Modify: web/motion.css
- Modify: tests/test_api.py
- Modify: tests/test_frontend_behavior.py

- [ ] **Step 1: 写入首页闭环测试**

Playwright 拦截 /api/predict 返回合法3D payload，断言：

- 起盘前 savePlanButton 和 openWorkbenchLink 不可见。
- 真实响应和落号动效完成后两者出现。
- 不自动跳转。
- 点击保存只发一次 POST /api/plans。
- 成功后按钮变为“已保存”，详情链接指向 /result.html?id={plan_id}。
- 双击或网络重试使用相同 request_id，不产生第二个方案。
- 切换到双色球时不展示福彩3D保存 CTA。
- freshness stale 时展示数据过期信息，保存按钮禁用。

- [ ] **Step 2: 运行并确认失败**

Run: PYTHONPATH=. .venv/bin/pytest tests/test_frontend_behavior.py -k "save_plan or workbench_cta" -q

Expected: FAIL，首页尚无 CTA。

- [ ] **Step 3: 增加结果动作区**

index.html 在真实结果区域后增加：

~~~html
<div class="prediction-actions" id="predictionActions" hidden>
  <button class="primary-action" id="savePlanButton" type="button">保存为本期方案</button>
  <a class="secondary-action" id="openWorkbenchLink" href="./analysis.html?game=3d">去3D工作台继续筛选</a>
  <a class="text-action" id="savedPlanLink" href="./result.html" hidden>查看已保存方案</a>
</div>
~~~

- [ ] **Step 4: 接入真实预测生命周期**

app.js 在 validatePredictionPayload 成功、motion.resolve 完成且 gameKey==="3d" 后缓存一个不含原始个人信息的 draft：

~~~javascript
state.planDraft = {
  game_key: "3d",
  target_issue: payload.target_issue,
  target_draw_date: payload.target_draw_date,
  source_type: "fortune",
  request_id: "prediction:" + requestContext.requestId,
  title: (payload.mode_profile?.label || "财运号") + " · 本期方案",
  entries: [{
    position: 0,
    main_numbers: payload.numbers.main,
    special_numbers: [],
    note: payload.mode_profile?.label || "首页财运号",
  }],
  condition_snapshot: {
    mode: "simple",
    analysis_window: 30,
    conditions: {},
    metrics: payload.number_metrics || {},
    latest_data_issue: payload.data_freshness.latest_issue,
    latest_data_date: payload.data_freshness.latest_date,
  },
};
~~~

在 /api/predict 响应中由服务端补齐 target_issue、target_draw_date、data_freshness 和 number_metrics；禁止前端根据字符串自行猜期号。3D 的目标期必须与 PredictionEngine 返回的 best_draw_date 对应：

~~~python
if request.game_key == "3d":
    game = next(item for item in repo.list_games() if item["game_key"] == "3d")
    game_logs = [
        item for item in repo.recent_crawl_logs(limit=20)
        if item.get("game_key") == "3d"
    ]
    freshness = build_public_freshness(game, logs=game_logs)
    target = resolve_3d_target(
        game["latest_issue"],
        game["latest_date"],
        payload["best_draw_date"],
    )
    payload.update(target)
    payload["data_freshness"] = freshness
    payload["number_metrics"] = number_attributes(payload["numbers"]["main"])
~~~

tests/test_api.py 固定 today 和历史最新期，断言 best_draw_date、target_draw_date、target_issue 三者映射一致，并断言 stale 时 can_claim_current=false。

- [ ] **Step 5: 保存状态和错误处理**

保存中禁用按钮；201 后 track plan_saved；409 stale 显示“数据已过期，请更新后重新起盘”；409 target issue is already drawn 改为“查看本期复盘 / 创建下一期”；重复方案显示服务端 duplicate_warning，但允许用户确认后另存。网络失败进入待同步并保留当前号码；本地存储不可用时明确“尚未保存”。不得因保存失败丢弃本地历史记录。

- [ ] **Step 6: 运行测试**

Run: PYTHONPATH=. .venv/bin/pytest tests/test_frontend_behavior.py tests/test_api.py -q

Run: node --check web/app.js

Expected: PASS。

- [ ] **Step 7: 提交**

~~~bash
git add lottery_luck/api.py web/index.html web/app.js web/motion.css tests/test_frontend_behavior.py tests/test_api.py
git commit -m "feat: save 3d predictions as plans"
~~~

## Task 12: 构建双层福彩3D工作台

**Files:**
- Create: web/workbench-3d.js
- Create: web/workbench-3d.css
- Modify: web/analysis.html
- Modify: web/analysis.js
- Modify: tests/test_api.py
- Modify: tests/test_frontend_behavior.py

- [ ] **Step 1: 写入工作台 DOM 和模式测试**

测试 /analysis.html?game=3d：

- 首屏标题为“福彩3D本期助手”。
- 默认 mode=simple，专业控件不进入 tab 顺序。
- 点击专业模式后 URL 变为 game=3d&mode=pro&window=30。
- 刷新保留模式。
- 简单模式包含数据新鲜度、本期方案、快速筛选、号码查询、最近开奖。
- 专业模式增加位置出次、位置遗漏、冷热、走势矩阵和条件明细。
- /analysis.html?game=ssq 保持旧分析中心，不挂载3D工作台。

- [ ] **Step 2: 运行并确认失败**

Run: PYTHONPATH=. .venv/bin/pytest tests/test_frontend_behavior.py -k "three_d_workbench" -q

Expected: FAIL，独立工作台尚不存在。

- [ ] **Step 3: 增加稳定结构**

analysis.html 新增：

~~~html
<section class="three-d-workbench" id="threeDWorkbench" hidden>
  <header class="workbench-head">
    <div>
      <p class="section-kicker">FC3D Workbench</p>
      <h1>福彩3D本期助手</h1>
      <p id="threeDFreshness" role="status">正在核对数据</p>
    </div>
    <div class="mode-segmented" aria-label="工作台模式">
      <button data-workbench-mode="simple" aria-pressed="true">本期助手</button>
      <button data-workbench-mode="pro" aria-pressed="false">专业模式</button>
    </div>
  </header>
  <section id="threeDPlanStrip" aria-label="我的本期方案"></section>
  <section id="threeDQuickTools" aria-label="快速工具"></section>
  <section id="threeDProfessional" aria-label="专业统计" hidden></section>
</section>
~~~

- [ ] **Step 4: 实现工作台状态与渲染**

workbench-3d.js 拥有独立 state：

~~~javascript
const state = {
  mode: "simple",
  window: 30,
  summary: null,
  plans: [],
  filterResult: null,
  loading: false,
};
~~~

渲染必须使用 createElement/textContent，不把 API 文本写入 innerHTML。统计矩阵采用固定 CSS grid，移动端横向滚动；按钮有稳定高度，加载文本不得撑开布局。

- [ ] **Step 5: 实现简单模式**

本期助手提供：

- freshness 状态条。
- 本期方案列表、历史方案入口和“继续编辑”。
- 三位数字手动录入与“随机一组”快捷动作，分别保存为 source_type=manual 和 source_type=random。
- 快速条件：和值范围、跨度范围、豹子/组三/组六、奇数个数。
- 候选结果最多先展示20组，可勾选加入当前方案。
- 号码查询输入“662”，展示历史出现、上次出现、当前遗漏和属性。
- 最近10期开奖。

用户点击“保存筛选结果”时 PATCH 当前方案或 POST 新方案，condition_snapshot.mode="simple"，source_type="filter"；每次编辑都更新 conditions 和 metrics 快照并发送 plan_edited。

- [ ] **Step 6: 实现专业模式**

专业模式增加：

- 百位/十位/个位出次表。
- 百位/十位/个位遗漏表，明确当前、平均、最大遗漏和历史分位。
- 每一位置冷热排序，并在界面展示“固定窗口频次 + 当前遗漏”的分层定义。
- 30/60/120期切换。
- 位置包含/排除条件。
- 完整候选计数与当前条件摘要。

模式切换不丢失已选条件和候选；只改变展示层级。

- [ ] **Step 7: 处理空、过期和失败状态**

- stale/empty：可查看历史，禁止“生成本期候选”和保存，提供“数据待更新”说明。
- 401/404：不显示伪数据。
- 网络失败：保留上次成功内容并显示可重试状态；待同步方案显示独立状态，不混入已保存列表。
- 无方案：明确“从首页起盘或直接新建方案”，不能显示空白卡片。

- [ ] **Step 8: 运行测试和语法检查**

Run: PYTHONPATH=. .venv/bin/pytest tests/test_frontend_behavior.py tests/test_api.py -q

Run: node --check web/analysis.js web/workbench-3d.js

Expected: PASS。

- [ ] **Step 9: 提交**

~~~bash
git add web/workbench-3d.js web/workbench-3d.css web/analysis.html web/analysis.js tests/test_api.py tests/test_frontend_behavior.py
git commit -m "feat: build dual-mode 3d workbench"
~~~

## Task 13: 将详情页升级为方案复盘和沿用入口

**Files:**
- Modify: web/result.html
- Modify: web/result.js
- Modify: web/styles.css
- Modify: tests/test_api.py
- Modify: tests/test_frontend_behavior.py

- [ ] **Step 1: 写入方案详情流程测试**

覆盖：

- 有 id 时先 GET /api/plans/{id}，不依赖 localStorage。
- 无权限/不存在显示404态，不回落展示其他人的本地记录。
- 旧本地 fortuneHistory id 仍可打开兼容详情。
- 未开奖时复盘按钮显示“开奖后可复盘”且禁用。
- 已开奖时页面自动尝试一次复盘，并展示每组 direct_hit、matched_positions、any_position_hits、matched_conditions 和 missed_conditions。
- 点击“沿用到下一期”创建新 plan，并跳到新详情。
- 重复沿用不会因双击创建两份。

- [ ] **Step 2: 运行并确认失败**

Run: PYTHONPATH=. .venv/bin/pytest tests/test_frontend_behavior.py -k "plan_detail or carry_forward" -q

Expected: FAIL，详情页只读取本地财运记录。

- [ ] **Step 3: 更新详情结构**

详情页显示：

- 方案标题、目标期号、创建来源和状态。
- 全部号码组，不只一组财运号。
- 保存时的数据窗口、模式、条件和数据版本。
- 开奖结果和逐组复盘。
- “去工作台继续筛选”“沿用到下一期”“删除方案”。

旧玄学解释只在 source_type=fortune 且兼容 payload 存在时展示；通用方案不能被迫显示“财眼”“大师起盘”等无数据模块。

- [ ] **Step 4: 实现服务端优先加载**

~~~javascript
async function loadRecord() {
  const id = new URLSearchParams(location.search).get("id");
  if (!id) return readLegacyRecord();
  try {
    return {kind: "plan", value: (await LotteryProduct.getPlan(id)).plan};
  } catch (error) {
    if (error.status !== 404) throw error;
    const legacy = readLegacyRecord(id);
    if (legacy) return {kind: "legacy", value: legacy};
    throw error;
  }
}
~~~

服务端404时只允许同 id 的旧本地记录兼容，不得回落到本地列表第一条。

- [ ] **Step 5: 复盘与沿用**

加载 pending_review 方案且服务端判断目标期开奖已存在时自动调用 review 一次；409 表示继续等待，不循环重试。复盘结果实际进入视口后 track review_viewed；carry-forward 成功后 track plan_carried_forward 并 location.assign 到新 id。删除方案使用确认对话框，成功后返回 /analysis.html?game=3d。

- [ ] **Step 6: 运行测试**

Run: PYTHONPATH=. .venv/bin/pytest tests/test_frontend_behavior.py tests/test_api.py -q

Run: node --check web/result.js

Expected: PASS。

- [ ] **Step 7: 提交**

~~~bash
git add web/result.html web/result.js web/styles.css tests/test_api.py tests/test_frontend_behavior.py
git commit -m "feat: add plan review and carry-forward flow"
~~~

## Task 14: 收口导航、策略页和产品事件

**Files:**
- Modify: web/index.html
- Modify: web/app.js
- Modify: web/analysis.html
- Modify: web/workbench-3d.js
- Modify: web/result.html
- Modify: web/result.js
- Modify: web/strategy.html
- Modify: web/strategy.js
- Modify: tests/test_frontend_behavior.py

- [ ] **Step 1: 写入导航与埋点测试**

断言：

- 预测首页仍是默认首页和首要入口。
- 福彩3D工作台没有复制首页的出生资料表单。
- strategy.html?game=3d 显示“专业能力已合并到3D工作台”，按钮进入 analysis.html?game=3d&mode=pro。
- 其他彩种策略页保持现状。
- prediction_completed、plan_saved、workbench_opened、plan_edited、review_viewed、plan_carried_forward 在正确动作后各上报一次。
- 页面初始化失败和演示预测不发送 plan_saved。

- [ ] **Step 2: 运行并确认失败**

Run: PYTHONPATH=. .venv/bin/pytest tests/test_frontend_behavior.py -k "retention_events or strategy_redirect" -q

Expected: FAIL，导航与事件尚未收口。

- [ ] **Step 3: 接入事件**

事件只在动作成功后发；workbench_opened 可在首个 summary 成功后发。properties 不允许包含号码、姓名、生日、城市、方案标题或 plan id。

- [ ] **Step 4: 收口策略页**

福彩3D策略页保留兼容提示一版，不做 HTTP 自动跳转，避免用户丢失上下文；下个大版本再删除旧入口。

- [ ] **Step 5: 运行测试**

Run: PYTHONPATH=. .venv/bin/pytest tests/test_frontend_behavior.py -q

Run: node --check web/app.js web/workbench-3d.js web/result.js web/strategy.js

Expected: PASS。

- [ ] **Step 6: 提交**

~~~bash
git add web/index.html web/app.js web/analysis.html web/workbench-3d.js web/result.html web/result.js web/strategy.html web/strategy.js tests/test_frontend_behavior.py
git commit -m "feat: close the 3d retention navigation loop"
~~~

## Task 15: 完成端到端流程和视觉验收

**Files:**
- Create: tests/test_retention_flow.py
- Create: tests/capture_retention_qa.py
- Modify: design-qa.md

- [ ] **Step 1: 建立隔离的 E2E 数据库 fixture**

fixture 创建最小 draws 表和至少120期确定性福彩3D数据，覆盖目标期已开奖和未开奖两种场景。E2E 不使用仓库真实 cwl_history.sqlite，避免测试污染用户数据。

- [ ] **Step 2: 写入完整主流程**

test_retention_flow.py 用 Playwright 执行：

1. 打开首页，选择福彩3D并填写资料。
2. 提交真实 mock 预测，等待电影感落号结束。
3. 保存为本期方案。
4. 打开福彩3D工作台。
5. 切换专业模式，应用和值/跨度条件。
6. 保存筛选结果到同一方案。
7. 打开详情，执行开奖复盘。
8. 沿用到下一期。
9. 验证新方案保留条件快照，review 为空，carried_from_plan_id 正确。

- [ ] **Step 3: 写入失败恢复流程**

至少覆盖：

- 数据 stale 时首页和工作台均禁止本期动作。
- 保存 API 500 后进入待同步，可重试且 prediction 不消失。
- 复盘 draw 缺失时维持 pending_review。
- 其他 client 无法读取方案。
- 管理 API 未授权为401。
- prefers-reduced-motion 下流程仍可完成。

- [ ] **Step 4: 运行 E2E**

Run: PYTHONPATH=. .venv/bin/pytest tests/test_retention_flow.py -q

Expected: PASS。

- [ ] **Step 5: 采集视觉证据**

capture_retention_qa.py 输出：

- artifacts/fc3d-home-save-desktop.png
- artifacts/fc3d-workbench-simple-desktop.png
- artifacts/fc3d-workbench-pro-desktop.png
- artifacts/fc3d-plan-review-desktop.png
- artifacts/fc3d-workbench-simple-mobile.png
- artifacts/fc3d-stale-state-mobile.png

视口至少1440x1000、390x844。检查无横向页面溢出、按钮文字不截断、模式切换不跳布局、矩阵只在自身容器横向滚动、sticky/overlay 不遮挡 CTA。

- [ ] **Step 6: 更新 design-qa.md**

记录每张截图的状态、视口、数据版本和人工结论。发现问题先修复再重新采集，不把已知重叠或空白画布记为通过。

- [ ] **Step 7: 提交**

~~~bash
git add tests/test_retention_flow.py tests/capture_retention_qa.py design-qa.md artifacts/fc3d-*.png
git commit -m "test: verify the 3d retention journey"
~~~

## Task 16: 运维、全量回归与发布门槛

**Files:**
- Modify: README.md
- Modify: docs/OPERATIONS.md
- Modify: .env.example

- [ ] **Step 1: 更新运行文档**

README 和 OPERATIONS 必须写明：

- LOTTERY_LUCK_ADMIN_TOKEN 是生产必填项。
- 自动更新默认关闭，生产启用方式和建议6小时周期。
- /api/health 中 service 与 data 的含义。
- 数据 stale 时前端会主动降级，不是服务故障。
- 如何轮换管理员令牌。
- 如何停用自动更新并回退到 scheduler --once。
- 如何备份 SQLite 后再发布 schema 变更。
- product_events 不采集原始个人信息或号码。

- [ ] **Step 2: 执行全量测试**

Run: PYTHONPATH=. .venv/bin/pytest -q

Expected: 全部 PASS；不得只报告新增测试。

- [ ] **Step 3: 执行前端语法检查**

Run:

~~~bash
node --check web/app.js
node --check web/product-client.js
node --check web/workbench-3d.js
node --check web/analysis.js
node --check web/result.js
node --check web/strategy.js
node --check web/admin.js
~~~

Expected: 全部退出码0。

- [ ] **Step 4: 执行仓库卫生检查**

Run:

~~~bash
git diff --check
git status --short
rg -n "TODO|TBD|FIXME|placeholder|coming soon" lottery_luck web tests README.md docs/OPERATIONS.md
~~~

Expected: git diff --check 无输出；状态只包含本次计划文件；扫描结果没有未处理占位符。

- [ ] **Step 5: 生产前最小验收**

在生产副本或 staging 上确认：

- 最新福彩3D期号与官方源一致。
- /api/health 的3d freshness 可声明本期。
- 未授权后台请求为401。
- 第三方 AI 捕获日志无姓名、生日、出生地和当前城市。
- 保存、复盘、沿用三条 API 均按 client 隔离。
- stale 演练能禁用本期 CTA。

- [ ] **Step 6: 提交文档**

~~~bash
git add README.md docs/OPERATIONS.md .env.example
git commit -m "docs: add 3d retention release operations"
~~~

## 发布与观测

### 灰度顺序

1. 先发布 P0：freshness、自动更新、后台鉴权、AI 最小化和事件管道。
2. 观察24小时，确认数据更新、错误率和401行为正常。
3. 对内部 client 开启保存/复盘 API。
4. 对10%流量展示首页保存 CTA 和福彩3D工作台。
5. 48小时无护栏异常后扩大到100%。

### 北极星

完成“保存方案 -> 开奖后复盘 -> 生成下一期方案”的用户数和转化率。

### 首发目标

- prediction_completed 到 plan_saved 转化率不低于30%。
- plan_saved 用户开奖后7日内 review_viewed 回访率不低于20%。
- review_viewed 到 plan_carried_forward 或新 plan_saved 转化率不低于30%。

### 护栏

- stale 数据下成功创建“本期方案”的次数必须为0。
- 越权读取或修改他人方案的次数必须为0。
- 未授权后台写入成功次数必须为0。
- 复盘目标期与真实开奖期不一致次数必须为0。
- 第三方 AI 接收原始个人信息次数必须为0。

### 进入 P3 的门槛

连续两个完整开奖周期满足：

- 至少100个独立 client 完成 plan_saved。
- 保存到复盘回访率达到20%。
- 至少30%的工作台用户主动切换专业模式。
- 至少25%的工作台用户产生 source_type=filter 的 plan_edited，且这些方案的 review_viewed 率不低于整体方案。

达到门槛后，单独编写“福彩3D专业工具 P3 Implementation Plan”，优先级为复式、胆拖、缩水、未出号码、遗漏预警、方案对比。未达到时先优化保存价值、复盘提醒和简单模式，不堆高级工具。

### 进入 P4 的门槛

除 P3 稳定外，还必须：

- 取得竞品3星复盘内页截图并书面确认统计定义。
- 为断组、3星、条件历史表现建立随机选择基线。
- 所有实验结果同时展示样本量、时间窗口和随机基线。
- 文案评审确认不使用“高命中”“必中”“稳中”等误导性承诺。

## 实施自检清单

- [ ] 每个新行为先有失败测试，再写实现。
- [ ] 每个任务只提交本任务列出的文件。
- [ ] 所有用户数据查询都带 client_id 条件。
- [ ] 所有“本期”动作都检查 can_claim_current。
- [ ] 所有复盘都按 plan.target_issue 读取真实开奖。
- [ ] 所有第三方 AI 上下文都通过派生特征边界。
- [ ] 所有产品事件都通过事件名和属性白名单。
- [ ] 所有前端 API 文本都用 textContent 渲染。
- [ ] 所有移动端固定格式控件有稳定尺寸和容器滚动。
- [ ] 全量 pytest、Node --check、git diff --check 均通过。
