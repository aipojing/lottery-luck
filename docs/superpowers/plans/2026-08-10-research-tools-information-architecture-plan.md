# 研究中心与选号工具重整 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将“数据分析、策略实验室、选号工具”重整为职责唯一的“研究中心 + 选号工具”，同时保留五彩种差异、旧链接和本地数据。

**Architecture:** `analysis.html` 成为研究中心外壳，由 `analysis.js` 统一管理彩种、数据窗口和 `data|strategy` 视图；新建 `research-strategy.js` 承载策略视图，避免继续维护独立策略页面。后端新增声明式页面能力配置和工具侧条件选号适配层；`tools.html/js` 仍是唯一号码执行面，并通过一次性 `sessionStorage` 接收研究策略。`web/` 是静态前端唯一源文件，完成后使用既有同步脚本生成 `frontend/public/`。

**Tech Stack:** Python 3.14、FastAPI、Pydantic、pytest、原生 HTML/CSS/JavaScript、Playwright、Next.js 16 静态兼容层、Vitest。

## Global Constraints

- 公开彩种固定为 `ssq`、`dlt`、`3d`、`pl3`、`kl8`。
- 顶级业务入口固定为 `预测首页`、`研究中心`、`选号工具`；不再显示独立“策略实验室”。
- 数据观察不得生成、复制、导出或保存最终号码；策略验证不得提供号码篮；选号工具不得复制走势图或回测报告。
- 研究交接键固定为 `lottery_research_handoff_v1`，`version: 1`，有效期30分钟，消费后删除。
- 旧号码池键 `lotteryLuck:numberPool:<game>` 只迁移、不删除；目标篮键保持 `lottery_tool_basket_v1`。
- 单次生成最多5,000注、总金额最多20,000元、号码篮每彩种最多500组。
- 数字彩保留位序、重复数字和 `play_type`；乐透型按分区无序集合归一化。
- 不新增前端框架或运行时依赖；继续使用现有黑金视觉变量和原生 JS。
- `web/` 是源文件；不得直接手改 `frontend/public/`，统一运行 `npm run sync:legacy` 生成。
- 每个页面继续显示“历史统计不代表未来概率”或“号码管理不提高中奖概率”。
- 不删除旧分析筛选、回测和3D过滤 API；新界面停止调用，兼容期继续保留。

---

## File Structure

### New files

- `lottery_luck/surface_config.py`：五彩种研究/策略/工具能力矩阵的唯一后端来源。
- `lottery_luck/surface_routes.py`：只暴露 `GET /api/surfaces/config`。
- `lottery_luck/conditional_tools.py`：把策略候选和数字彩条件过滤归一化为工具结果。
- `tests/test_surface_routes.py`：能力矩阵与 API 契约测试。
- `tests/test_conditional_tools.py`：条件选号领域测试。
- `web/research-strategy.js`：研究中心策略视图；不拥有顶级导航和彩种标签。
- `web/strategy-redirect.js`：旧策略页兼容跳转。

### Modified source files

- `lottery_luck/api.py`：注册 surface router，保留旧 API。
- `lottery_luck/number_tools.py`：提供候选结果标准化公共适配函数。
- `lottery_luck/tool_routes.py`：新增 `POST /api/tools/{game_key}/conditional`。
- `web/analysis.html`：研究中心二级页签、数据视图容器和策略视图 DOM。
- `web/analysis.js`：统一管理 `game/view/window`，移除筛选、回测和号码池执行逻辑。
- `web/strategy.html`：降为兼容跳转页。
- `web/strategy.js`：不再由页面加载；其可复用逻辑迁入 `research-strategy.js` 后删除。
- `web/tools.html`：增加条件选号卡片和策略来源状态。
- `web/tools.js`：能力矩阵、条件选号、策略交接、旧号码池迁移。
- `web/three-d-toolbox.js`：删除 `reduction` 目录项和路由状态。
- `web/workbench-3d.js`：删除3D缩水 UI 绑定和提交逻辑，保留走势/查询/属性/最近开奖。
- `web/styles.css`：研究中心页签、策略视图和响应式布局。
- `web/tools.css`：条件选号和策略来源样式。
- `web/index.html`、`web/result.html`、`web/privacy.html`、`web/admin.html`：统一导航。
- `web/app.js`：移除独立策略入口同步，只同步研究中心彩种链接。
- `tests/test_api.py`、`tests/test_frontend_behavior.py`、`tests/test_tool_routes.py`：更新契约和端到端覆盖。
- `frontend/tests/routes.test.ts`：继续验证 `/strategy` 兼容路由与 `/tools`、`/analysis` 稳定地址。
- `README.md`：更新产品入口、职责和兼容说明。

### Generated files

- `frontend/public/**`：由 `frontend/scripts/sync-legacy.mjs` 从所有已跟踪 `web/**` 文件生成。

---

### Task 1: 建立五彩种页面能力矩阵

**Files:**
- Create: `lottery_luck/surface_config.py`
- Create: `lottery_luck/surface_routes.py`
- Create: `tests/test_surface_routes.py`
- Modify: `lottery_luck/api.py:53-62,1004-1008`

**Interfaces:**
- Produces: `surface_config_payload() -> dict[str, Any]`
- Produces: `capabilities_for_game(game_key: str) -> dict[str, Any]`
- Produces: `GET /api/surfaces/config`
- Later tasks consume `games[game_key].research.data`, `games[game_key].research.strategy.features`, `games[game_key].research.strategy.condition_fields`, `games[game_key].tools` and `games[game_key].tool_labels`.

- [ ] **Step 1: Write the failing domain and route tests**

```python
# tests/test_surface_routes.py
from fastapi.testclient import TestClient

from lottery_luck.api import app
from lottery_luck.surface_config import capabilities_for_game

client = TestClient(app)


def test_surface_config_has_ordered_public_games_and_two_research_views():
    response = client.get("/api/surfaces/config")
    assert response.status_code == 200
    body = response.json()
    assert body["version"] == 1
    assert list(body["games"]) == ["ssq", "dlt", "3d", "pl3", "kl8"]
    assert body["views"] == ["data", "strategy"]


def test_digit_games_expose_position_research_and_group_tool_label():
    game = capabilities_for_game("3d")
    assert "position_omission" in game["research"]["data"]
    assert "digit_shape" in game["research"]["strategy"]["features"]
    assert game["research"]["strategy"]["condition_fields"] == [
        "exclude_recent", "min_hot", "odd_even", "sum_min", "sum_max",
        "max_consecutive_run", "prime_composite", "mod3", "tail_exclude",
        "tail_include", "min_omission",
    ]
    assert game["tool_labels"]["dantuo"] == "组选包号"


def test_lotto_and_kl8_capabilities_are_game_specific():
    dlt = capabilities_for_game("dlt")
    kl8 = capabilities_for_game("kl8")
    assert "special_zone" in dlt["research"]["data"]
    assert "large_field_rules" in kl8["research"]["strategy"]["features"]
    assert "position_omission" not in kl8["research"]["data"]
```

- [ ] **Step 2: Run the tests and verify RED**

Run:

```bash
PYTHONPATH=. .venv/bin/python -m pytest tests/test_surface_routes.py -q
```

Expected: collection fails because `lottery_luck.surface_config` does not exist.

- [ ] **Step 3: Implement the immutable capability payload**

```python
# lottery_luck/surface_config.py
from __future__ import annotations

from copy import deepcopy
from typing import Any

from .rules import FRONTEND_GAME_KEYS

COMMON_STRATEGY_FEATURES = ["preset", "backtest", "compare", "save"]
LOTTO_STRATEGY_FIELDS = [
    "exclude_recent", "min_hot", "odd_even", "sum_min", "sum_max",
    "max_consecutive_run", "ac_min", "ac_max", "prime_composite", "mod3",
    "zone", "tail_exclude", "tail_include", "min_omission",
]
DIGIT_STRATEGY_FIELDS = [
    "exclude_recent", "min_hot", "odd_even", "sum_min", "sum_max",
    "max_consecutive_run", "prime_composite", "mod3", "tail_exclude",
    "tail_include", "min_omission",
]
COMMON_TOOLS = ["quick", "lock", "full", "dantuo", "conditional", "reduce", "organize"]

GAME_SURFACES: dict[str, dict[str, Any]] = {
    "ssq": {
        "label": "双色球",
        "research": {"data": ["hot_cold", "omission", "trend", "shape", "special_zone", "recent", "calendar"], "strategy": {"features": [*COMMON_STRATEGY_FEATURES, "zone_rules"], "condition_fields": LOTTO_STRATEGY_FIELDS}},
        "tools": COMMON_TOOLS,
        "tool_labels": {"dantuo": "胆拖选号"},
    },
    "dlt": {
        "label": "大乐透",
        "research": {"data": ["hot_cold", "omission", "trend", "shape", "special_zone", "recent", "calendar"], "strategy": {"features": [*COMMON_STRATEGY_FEATURES, "zone_rules"], "condition_fields": LOTTO_STRATEGY_FIELDS}},
        "tools": COMMON_TOOLS,
        "tool_labels": {"dantuo": "胆拖选号"},
    },
    "3d": {
        "label": "福彩3D",
        "research": {"data": ["position_trend", "position_omission", "frequency", "heat", "number_query", "number_attributes", "digit_shape", "recent"], "strategy": {"features": [*COMMON_STRATEGY_FEATURES, "digit_shape"], "condition_fields": DIGIT_STRATEGY_FIELDS}},
        "tools": COMMON_TOOLS,
        "tool_labels": {"dantuo": "组选包号", "full": "定位复式", "conditional": "条件缩水"},
    },
    "pl3": {
        "label": "排列3",
        "research": {"data": ["position_trend", "position_omission", "frequency", "heat", "number_query", "number_attributes", "digit_shape", "recent"], "strategy": {"features": [*COMMON_STRATEGY_FEATURES, "digit_shape"], "condition_fields": DIGIT_STRATEGY_FIELDS}},
        "tools": COMMON_TOOLS,
        "tool_labels": {"dantuo": "组选包号", "full": "定位复式", "conditional": "条件缩水"},
    },
    "kl8": {
        "label": "快乐8",
        "research": {"data": ["hot_cold", "omission", "range_density", "odd_even", "repeat", "consecutive", "recent", "calendar"], "strategy": {"features": [*COMMON_STRATEGY_FEATURES, "large_field_rules"], "condition_fields": LOTTO_STRATEGY_FIELDS}},
        "tools": COMMON_TOOLS,
        "tool_labels": {"dantuo": "胆拖选号"},
    },
}


def capabilities_for_game(game_key: str) -> dict[str, Any]:
    key = str(game_key).strip().lower()
    if key not in GAME_SURFACES:
        raise KeyError(key)
    return deepcopy(GAME_SURFACES[key])


def surface_config_payload() -> dict[str, Any]:
    return {
        "version": 1,
        "views": ["data", "strategy"],
        "games": {key: capabilities_for_game(key) for key in FRONTEND_GAME_KEYS},
    }
```

Add a router that returns `surface_config_payload()` and register it before the static mount:

```python
# lottery_luck/surface_routes.py
from fastapi import APIRouter
from .surface_config import surface_config_payload

router = APIRouter(prefix="/api/surfaces")


@router.get("/config")
def surface_config() -> dict:
    return surface_config_payload()
```

```python
# lottery_luck/api.py
from .surface_routes import router as surface_router

app.include_router(surface_router)
```

- [ ] **Step 4: Run focused tests and verify GREEN**

Run:

```bash
PYTHONPATH=. .venv/bin/python -m pytest tests/test_surface_routes.py tests/test_tool_routes.py -q
```

Expected: all tests pass; existing `/api/tools/config` remains unchanged.

- [ ] **Step 5: Commit**

```bash
git add lottery_luck/surface_config.py lottery_luck/surface_routes.py lottery_luck/api.py tests/test_surface_routes.py
git commit -m "feat: declare research and tool capabilities"
```

---

### Task 2: 将条件选号纳入工具 API

**Files:**
- Create: `lottery_luck/conditional_tools.py`
- Create: `tests/test_conditional_tools.py`
- Modify: `lottery_luck/number_tools.py:1000-1110`
- Modify: `lottery_luck/tool_routes.py:1-160`
- Modify: `tests/test_tool_routes.py`

**Interfaces:**
- Consumes: existing `generate_strategy_candidates()`, `workbench_3d.filter_candidates()` and number-tool cost limits.
- Produces: `conditional_pick(game_key, draws, source, preset, conditions, count, options) -> dict[str, Any]`.
- Produces: `result_from_candidates(game_key, tool, candidates, options, metadata=None) -> dict[str, Any]`.
- Produces: `POST /api/tools/{game_key}/conditional` with stable `{detail: {code, message}}` errors.

- [ ] **Step 1: Write failing domain tests for strategy and digit filters**

```python
# tests/test_conditional_tools.py
import pytest

from lottery_luck.conditional_tools import conditional_pick
from lottery_luck.number_tools import ToolError


@pytest.fixture
def sample_ssq_draws():
    rows = [
        ("012", "2026-07-12", "01,04,07,12,22,33", "07"),
        ("011", "2026-07-11", "02,05,08,13,23,32", "08"),
        ("010", "2026-07-10", "03,06,09,14,24,31", "09"),
        ("009", "2026-07-09", "01,10,15,20,25,30", "10"),
        ("008", "2026-07-08", "02,11,16,21,26,29", "11"),
        ("007", "2026-07-07", "03,12,17,22,27,28", "12"),
        ("006", "2026-07-06", "04,13,18,23,28,33", "13"),
        ("005", "2026-07-05", "05,14,19,24,29,32", "14"),
        ("004", "2026-07-04", "06,15,20,25,30,31", "15"),
        ("003", "2026-07-03", "07,16,21,26,27,33", "16"),
        ("002", "2026-07-02", "08,17,22,23,28,32", "01"),
        ("001", "2026-07-01", "09,18,19,24,29,31", "02"),
    ]
    return [
        {"issue": issue, "draw_date": date, "red_numbers": main, "blue_number": special}
        for issue, date, main, special in rows
    ]


def test_digit_filter_keeps_ordered_repeated_digits():
    result = conditional_pick(
        "3d", [], "digit_filter", "balanced",
        {"types": ["组三"], "position_include": {"0": [1]}, "max_results": 10},
        10, {},
    )
    assert result["tool"] == "conditional"
    assert all(entry["main"][0] == 1 for entry in result["entries"])
    assert any(len(set(entry["main"])) == 2 for entry in result["entries"])


def test_strategy_filter_requires_history_and_returns_tool_entries(sample_ssq_draws):
    result = conditional_pick("ssq", sample_ssq_draws, "strategy", "balanced", {}, 5, {})
    assert result["ticket_count"] == 5
    assert result["source_meta"]["source"] == "strategy"
    assert all(len(entry["main"]) == 6 and len(entry["special"]) == 1 for entry in result["entries"])


def test_digit_filter_rejects_lotto_game():
    with pytest.raises(ToolError) as exc:
        conditional_pick("ssq", [], "digit_filter", "balanced", {}, 5, {})
    assert exc.value.code == "invalid_conditional_source"


def test_digit_filter_maps_invalid_nested_conditions_to_tool_error():
    with pytest.raises(ToolError) as exc:
        conditional_pick("3d", [], "digit_filter", "balanced", {"types": ["group3"]}, 5, {})
    assert exc.value.code == "invalid_conditions"


def test_strategy_filter_rejects_more_than_thirty_candidates(sample_ssq_draws):
    with pytest.raises(ToolError) as exc:
        conditional_pick("ssq", sample_ssq_draws, "strategy", "balanced", {}, 31, {})
    assert exc.value.code == "invalid_count"
```

- [ ] **Step 2: Write failing route tests**

```python
# append to tests/test_tool_routes.py
from lottery_luck.api import get_repository

TOOL_ROUTE_SSQ_DRAWS = [
    {
        "issue": f"{index:03d}",
        "draw_date": f"2026-07-{index:02d}",
        "red_numbers": "01,04,07,12,22,33",
        "blue_number": "07",
    }
    for index in range(12, 0, -1)
]


def test_conditional_route_uses_repository_history(monkeypatch):
    class Repo:
        def recent_draws(self, game_key, limit):
            assert game_key == "ssq"
            assert limit == 120
            return TOOL_ROUTE_SSQ_DRAWS

    app.dependency_overrides[get_repository] = lambda: Repo()
    try:
        response = client.post("/api/tools/ssq/conditional", json={
            "source": "strategy", "preset": "balanced", "count": 3,
            "conditions": {}, "options": {},
        })
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 200
    assert response.json()["ticket_count"] == 3


def test_conditional_route_rejects_unknown_source_with_stable_422():
    response = client.post("/api/tools/3d/conditional", json={"source": "unknown"})
    assert response.status_code == 422
    assert response.json()["detail"] == {"code": "invalid_request", "message": "工具请求参数无效。"}


def test_conditional_route_rejects_spend_over_limit():
    response = client.post("/api/tools/3d/conditional", json={
        "source": "digit_filter",
        "count": 200,
        "conditions": {"max_results": 200},
        "options": {"multiplier": 99},
    })
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "spend_limit"
```

- [ ] **Step 3: Run the focused tests and verify RED**

Run:

```bash
PYTHONPATH=. .venv/bin/python -m pytest tests/test_conditional_tools.py tests/test_tool_routes.py -q
```

Expected: import/404 failures because the domain adapter and route do not exist.

- [ ] **Step 4: Add the public result adapter in `number_tools.py`**

```python
def result_from_candidates(
    game_key: str,
    tool: str,
    candidates: list[dict[str, Any]],
    options: dict[str, Any] | None,
    *,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    normalized_options = normalize_options(game_key, options)
    entries = [
        _normalize_entry(
            game_key,
            list(candidate.get("main") or candidate.get("numbers") or []),
            list(candidate.get("special") or []),
            play_type=str(candidate.get("play_type") or "straight"),
        )
        for candidate in candidates
    ]
    payload = _result_payload(game_key, tool, entries, normalized_options)
    if payload["total_cost"] > MAX_TOTAL_COST:
        payload["warnings"].append("spend_limit")
    payload["source_meta"] = deepcopy(metadata or {})
    return payload
```

The existing `_result_payload` remains the authority for entry cost, multiplier and add-on. The adapter adds the same `spend_limit` warning consumed by `_run_tool`; the request schema caps conditional output at 200, below the 5,000-ticket ceiling.

- [ ] **Step 5: Implement the conditional adapter**

```python
# lottery_luck/conditional_tools.py
from typing import Any

from .number_tools import ToolError, result_from_candidates
from .strategy import generate_strategy_candidates
from .workbench_3d import filter_candidates as filter_digit_candidates


def conditional_pick(
    game_key: str,
    draws: list[dict[str, Any]],
    source: str,
    preset: str,
    conditions: dict[str, Any],
    count: int,
    options: dict[str, Any] | None,
) -> dict[str, Any]:
    if source == "digit_filter":
        if game_key not in {"3d", "pl3"}:
            raise ToolError("invalid_conditional_source", "该彩种不支持数字条件缩水")
        try:
            filtered = filter_digit_candidates({**conditions, "max_results": count})
        except ValueError as exc:
            raise ToolError("invalid_conditions", "数字条件不符合规则") from exc
        candidates = [{"main": row["numbers"], "special": [], "play_type": "straight"} for row in filtered["candidates"]]
        return result_from_candidates(
            game_key, "conditional", candidates, options,
            metadata={"source": source, "total_candidates": filtered["total"], "conditions": filtered["filters"]},
        )
    if source != "strategy":
        raise ToolError("invalid_conditional_source", "不支持的条件选号来源")
    if not draws:
        raise ToolError("history_unavailable", "暂无历史数据，不能应用研究策略")
    if count > 30:
        raise ToolError("invalid_count", "策略条件选号最多生成30组")
    generated = generate_strategy_candidates(
        game_key, draws,
        {"preset": preset, "candidate_count": count, "conditions": conditions},
    )
    return result_from_candidates(
        game_key, "conditional", generated["candidates"], options,
        metadata={"source": source, "preset": generated["preset"], "strategy_name": generated["strategy_name"], "conditions": generated["conditions"]},
    )
```

- [ ] **Step 6: Add the strict Pydantic request and route**

```python
# lottery_luck/tool_routes.py
from typing import Annotated

from fastapi import Depends

from .conditional_tools import conditional_pick
from .repository import LotteryRepository, get_repository


class ConditionalRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    source: Literal["strategy", "digit_filter"] = "strategy"
    preset: Literal["balanced", "conservative", "aggressive"] = "balanced"
    count: StrictInt = Field(default=8, ge=1, le=200)
    window: StrictInt = Field(default=120, ge=1, le=300)
    conditions: dict[str, Any] = Field(default_factory=dict)
    options: ToolOptions = Field(default_factory=ToolOptions)


@router.post("/{game_key}/conditional")
def tool_conditional(
    game_key: str,
    request: ConditionalRequest,
    repo: Annotated[LotteryRepository, Depends(get_repository)],
) -> dict[str, Any]:
    _ensure_game(game_key)
    draws = [] if request.source == "digit_filter" else repo.recent_draws(game_key, limit=request.window)
    return _run_tool(lambda: conditional_pick(
        game_key, draws, request.source, request.preset,
        request.conditions, request.count, request.options.to_domain_payload(),
    ))
```

- [ ] **Step 7: Run focused tests and verify GREEN**

Run:

```bash
PYTHONPATH=. .venv/bin/python -m pytest tests/test_conditional_tools.py tests/test_number_tools.py tests/test_tool_routes.py -q
```

Expected: all tests pass; malformed fields keep the existing stable `invalid_request` shape.

- [ ] **Step 8: Commit**

```bash
git add lottery_luck/conditional_tools.py lottery_luck/number_tools.py lottery_luck/tool_routes.py tests/test_conditional_tools.py tests/test_tool_routes.py
git commit -m "feat: add conditional number tool API"
```

---

### Task 3: 在选号工具接收策略、条件选号和旧号码池

**Files:**
- Modify: `web/tools.html:24-118`
- Modify: `web/tools.js:1-691`
- Modify: `web/tools.css:1-369`
- Modify: `tests/test_frontend_behavior.py:9242-end`

**Interfaces:**
- Consumes: `GET /api/surfaces/config` and `POST /api/tools/{game}/conditional`.
- Consumes: `sessionStorage["lottery_research_handoff_v1"]` version 1, max age 1,800,000 ms.
- Consumes: `localStorage["lotteryLuck:numberPool:<game>"]`.
- Produces: migrated entries in `localStorage["lottery_tool_basket_v1"]` and marker `lottery_tool_pool_migration_v1`.

- [ ] **Step 1: Write failing browser tests for the new tool and ability labels**

```python
def test_tools_render_game_specific_capabilities_and_conditional_card(live_server_url, browser_page):
    browser_page.goto(f"{live_server_url}/tools.html?game=3d&tool=conditional")
    browser_page.wait_for_selector('[data-tool-card="conditional"]')
    assert browser_page.locator('[data-tool-card="conditional"] strong').inner_text() == "条件缩水"
    assert browser_page.locator('[data-tool-card="dantuo"] strong').inner_text() == "组选包号"
    assert browser_page.locator("#conditionalDigitFields").is_visible()


def test_tools_consume_valid_strategy_handoff_once(live_server_url, browser_page):
    browser_page.add_init_script("""
      sessionStorage.setItem("lottery_research_handoff_v1", JSON.stringify({
        version: 1, created_at: Date.now(), game_key: "ssq", source: "strategy",
        preset: "balanced", name: "均衡型", window: 120,
        conditions: {odd_even: "3:3", sum_min: 80, sum_max: 130}
      }));
    """)
    browser_page.goto(f"{live_server_url}/tools.html?game=ssq&tool=conditional&source=strategy")
    browser_page.wait_for_selector("#conditionalSource")
    assert "来源：均衡型" in browser_page.locator("#conditionalSource").inner_text()
    assert browser_page.locator('[name="sum_min"]').input_value() == "80"
    assert browser_page.evaluate("() => sessionStorage.getItem('lottery_research_handoff_v1')") is None
```

- [ ] **Step 2: Write failing migration and failure-path tests**

```python
def test_old_number_pool_migrates_idempotently_without_deletion(live_server_url, browser_page):
    browser_page.add_init_script("""
      localStorage.setItem("lotteryLuck:numberPool:3d", JSON.stringify([
        {main: [1, 1, 2], special: []}, {main: [1, 2, 2], special: []}
      ]));
    """)
    browser_page.goto(f"{live_server_url}/tools.html?game=3d&tool=quick")
    browser_page.wait_for_function("() => document.querySelector('[data-basket-count]').textContent === '2'")
    browser_page.reload()
    browser_page.wait_for_function("() => document.querySelector('[data-basket-count]').textContent === '2'")
    assert browser_page.evaluate("() => localStorage.getItem('lotteryLuck:numberPool:3d')") is not None


def test_expired_or_cross_game_handoff_is_rejected_with_visible_message(live_server_url, browser_page):
    browser_page.add_init_script("""
      sessionStorage.setItem("lottery_research_handoff_v1", JSON.stringify({
        version: 1, created_at: Date.now() - 1800001, game_key: "dlt", source: "strategy", conditions: {}
      }));
    """)
    browser_page.goto(f"{live_server_url}/tools.html?game=ssq&tool=conditional&source=strategy")
    assert "策略条件未能带入" in browser_page.locator("#toolStatus").inner_text()
```

- [ ] **Step 3: Run the browser slice and verify RED**

Run:

```bash
PYTHONPATH=. .venv/bin/python -m pytest tests/test_frontend_behavior.py -k 'conditional_card or strategy_handoff or number_pool_migrates or cross_game_handoff' -q
```

Expected: selectors/tool route are missing.

- [ ] **Step 4: Add the conditional card and strategy source region**

Add to `web/tools.html`:

```html
<button class="tool-card" type="button" data-tool-card="conditional">
  <strong>条件选号</strong><span>按研究规则或数字形态筛选候选。</span>
</button>
```

Inside the workbench heading add:

```html
<p class="tool-source" id="conditionalSource" role="status" hidden></p>
```

- [ ] **Step 5: Add strict handoff consumption and migration helpers**

```javascript
const HANDOFF_KEY = "lottery_research_handoff_v1";
const HANDOFF_MAX_AGE_MS = 30 * 60 * 1000;
const POOL_MIGRATION_KEY = "lottery_tool_pool_migration_v1";
let publicGameKeys = [...GAME_KEYS];

function consumeResearchHandoff(gameKey) {
  const raw = sessionStorage.getItem(HANDOFF_KEY);
  sessionStorage.removeItem(HANDOFF_KEY);
  if (!raw) return { value: null, error: "策略条件未能带入，请重新选择。" };
  try {
    const value = JSON.parse(raw);
    const age = Date.now() - value.created_at;
    const fresh = Number.isFinite(value.created_at) && age >= 0 && age <= HANDOFF_MAX_AGE_MS;
    if (value.version !== 1 || value.game_key !== gameKey || value.source !== "strategy" || !fresh) {
      return { value: null, error: "策略条件未能带入，请重新选择。" };
    }
    return { value, error: "" };
  } catch {
    return { value: null, error: "策略条件未能带入，请重新选择。" };
  }
}

function migrateLegacyPools() {
  if (localStorage.getItem(POOL_MIGRATION_KEY) === "1") return;
  const next = sanitizeBasket(readBasket());
  for (const gameKey of publicGameKeys) {
    let rows;
    try {
      rows = JSON.parse(localStorage.getItem(`lotteryLuck:numberPool:${gameKey}`) || "[]");
    } catch {
      setStatus(`${gameKey} 的旧号码池无法读取，原数据已保留。`, true);
      continue;
    }
    if (!Array.isArray(rows)) continue;
    const seen = new Set(next.games[gameKey].map(entryIdentity));
    rows.forEach((row) => {
      const entry = normalizeEntry(
        {...row, game_key: gameKey, source: "legacy_pool", play_type: row.play_type || "straight"},
        gameKey,
      );
      if (!entry || seen.has(entryIdentity(entry)) || next.games[gameKey].length >= 500) return;
      seen.add(entryIdentity(entry));
      next.games[gameKey].push(entry);
    });
  }
  try {
    localStorage.setItem(BASKET_KEY, JSON.stringify(next));
    localStorage.setItem(POOL_MIGRATION_KEY, "1");
    memoryBasket = null;
    renderBasket(next);
  } catch {
    memoryBasket = next;
    showBasketWarning("旧号码池暂时无法写入浏览器存储，原数据已保留。");
  }
}
```

Set the migration marker only after the merged basket persists successfully. Never remove `lotteryLuck:numberPool:<game>`. After `/api/surfaces/config` succeeds, replace `publicGameKeys` with its ordered game keys before running migration; if the request fails, keep the five existing keys solely as a storage-recovery fallback.

- [ ] **Step 6: Render per-game conditional forms and call the new endpoint**

Extend `formMarkup()` and `endpointAndBody()` with `conditional`:

```javascript
if (tool === "conditional") {
  if (["3d", "pl3"].includes(game.key) && state.handoff?.source !== "strategy") {
    return digitConditionalMarkup();
  }
  return strategyConditionalMarkup(game, state.handoff);
}
```

`digitConditionalMarkup()` must render `count` (1–200), `sum_min/max`, `span_min/max`, checked-by-default `types` (`豹子`/`组三`/`组六`), checked-by-default `odd_counts` and `big_counts` (0–3), and six text inputs named `position_include_0..2` / `position_exclude_0..2`. `strategyConditionalMarkup()` must render `preset`, `count` (1–30), `window` and only the condition fields named by `capabilities.research.strategy.condition_fields`; when a valid handoff exists it pre-fills those values. Both helpers append the existing multiplier/add-on/play-type options rather than creating a second options serializer.

Use these serializers so blank optional fields are omitted and digit positions are not flattened or sorted:

```javascript
const STRATEGY_NUMBER_FIELDS = [
  "exclude_recent", "min_hot", "sum_min", "sum_max", "max_consecutive_run",
  "ac_min", "ac_max", "min_omission",
];
const STRATEGY_TEXT_FIELDS = ["odd_even", "prime_composite", "mod3", "zone", "tail_exclude", "tail_include"];

function inputDigits(value) {
  return [...new Set(String(value || "").match(/\d/g) || [])].map(Number);
}

function conditionalConditions(form, gameKey, source) {
  if (source === "digit_filter") {
    const positions = (prefix) => Object.fromEntries(
      [0, 1, 2]
        .map((index) => [String(index), inputDigits(form.elements[`${prefix}_${index}`].value)])
        .filter(([, digits]) => digits.length),
    );
    return {
      sum_min: Number(form.elements.sum_min.value),
      sum_max: Number(form.elements.sum_max.value),
      span_min: Number(form.elements.span_min.value),
      span_max: Number(form.elements.span_max.value),
      types: [...form.querySelectorAll('[name="types"]:checked')].map((input) => input.value),
      odd_counts: [...form.querySelectorAll('[name="odd_counts"]:checked')].map((input) => Number(input.value)),
      big_counts: [...form.querySelectorAll('[name="big_counts"]:checked')].map((input) => Number(input.value)),
      position_include: positions("position_include"),
      position_exclude: positions("position_exclude"),
    };
  }
  const conditions = {};
  STRATEGY_NUMBER_FIELDS.forEach((name) => {
    if (form.elements[name] && form.elements[name].value !== "") conditions[name] = Number(form.elements[name].value);
  });
  STRATEGY_TEXT_FIELDS.forEach((name) => {
    if (form.elements[name] && form.elements[name].value.trim()) conditions[name] = form.elements[name].value.trim();
  });
  return conditions;
}
```

```javascript
function isDigitGame(gameKey) {
  return gameKey === "3d" || gameKey === "pl3";
}

if (state.tool === "conditional") {
  const source = state.handoff?.source === "strategy"
    ? "strategy"
    : (isDigitGame(state.game) ? "digit_filter" : "strategy");
  return {
    endpoint: `/api/tools/${state.game}/conditional`,
    body: {
      source,
      preset: form.elements.preset?.value || "balanced",
      count: Number(form.elements.count?.value || 8),
      window: Number(form.elements.window?.value || 120),
      conditions: conditionalConditions(form, state.game, source),
      options: formOptions(form),
    },
  };
}
```

Use the surface config `tool_labels` to change card titles and use `tools` to render only supported cards. Do not duplicate the matrix in `tools.js` beyond a safe `quick` fallback.

- [ ] **Step 7: Verify result ownership, basket semantics and mobile layout**

Run:

```bash
PYTHONPATH=. .venv/bin/python -m pytest tests/test_frontend_behavior.py -k 'number_tools or tools_ or basket or conditional or handoff or migration' -q
node --check web/tools.js
```

Expected: all selected tests pass; `112` and `122` remain distinct; 390px viewport has no horizontal overflow.

- [ ] **Step 8: Commit**

```bash
git add web/tools.html web/tools.js web/tools.css tests/test_frontend_behavior.py
git commit -m "feat: add conditional selection and research handoff"
```

---

### Task 4: 将策略实验室并入研究中心

**Files:**
- Create: `web/research-strategy.js`
- Modify: `web/analysis.html:24-390`
- Modify: `web/analysis.js:1-918`
- Modify: `web/styles.css`
- Modify: `tests/test_api.py:381-430,1539-1585`
- Modify: `tests/test_frontend_behavior.py:1020-1080`

**Interfaces:**
- Consumes: `GET /api/surfaces/config`, `/api/strategy/{game}/generate|backtest|compare`.
- Produces: `window.LotteryResearch` with `getState()`, `setView(view)`, `setGame(game)`, `subscribe(callback)`.
- Produces: `lottery_research_handoff_v1` before navigating to the tools page.

- [ ] **Step 1: Write failing research-shell tests**

```python
def test_research_center_has_data_and_strategy_views_for_all_games(live_server_url, browser_page):
    browser_page.goto(f"{live_server_url}/analysis.html?game=3d&view=strategy")
    browser_page.wait_for_selector("#researchViewTabs")
    assert browser_page.locator('[data-research-view="strategy"]').get_attribute("aria-selected") == "true"
    assert browser_page.locator("#researchStrategyView").is_visible()
    assert browser_page.locator("#strategyCompat").count() == 0
    assert browser_page.locator('[data-game="3d"]').get_attribute("aria-pressed") == "true"


def test_research_view_switch_updates_url_without_duplicate_game_tabs(live_server_url, browser_page):
    browser_page.goto(f"{live_server_url}/analysis.html?game=dlt&view=data&window=60")
    assert browser_page.locator("#gameTabs").count() == 1
    browser_page.locator('[data-research-view="strategy"]').click()
    browser_page.wait_for_function("() => new URLSearchParams(location.search).get('view') === 'strategy'")
    assert browser_page.locator("#researchDataView").is_hidden()
    assert browser_page.locator("#researchStrategyView").is_visible()
```

- [ ] **Step 2: Write failing strategy-handoff and race tests**

```python
def test_strategy_view_hands_normalized_conditions_to_tools(live_server_url, browser_page):
    browser_page.goto(f"{live_server_url}/analysis.html?game=ssq&view=strategy")
    browser_page.wait_for_selector("#useStrategyButton")
    browser_page.locator('[name="sum_min"]').fill("80")
    browser_page.locator("#useStrategyButton").click()
    browser_page.wait_for_url("**/tools.html?game=ssq&tool=conditional&source=strategy")
    handoff = browser_page.evaluate("() => JSON.parse(sessionStorage.getItem('lottery_research_handoff_v1'))")
    assert handoff["version"] == 1
    assert handoff["game_key"] == "ssq"
    assert handoff["conditions"]["sum_min"] == 80


def test_saved_strategies_stay_scoped_by_legacy_game_key_and_invalid_rows_are_preserved(live_server_url, browser_page):
    browser_page.add_init_script("""
      localStorage.setItem("lotteryLuck:strategyLab:ssq", JSON.stringify([
        {name: "旧均衡策略", preset: "balanced", form: {sum_min: 80, sum_max: 130}},
        {name: "旧非法策略", preset: "removed-preset", form: {unknown_rule: 1}}
      ]));
      localStorage.setItem("lotteryLuck:strategyLab:dlt", JSON.stringify([
        {name: "大乐透策略", preset: "balanced", form: {sum_min: 60}}
      ]));
    """)
    browser_page.goto(f"{live_server_url}/analysis.html?game=ssq&view=strategy")
    browser_page.wait_for_selector('[data-saved-strategy-state="valid"]')
    assert browser_page.locator("#savedStrategies li").count() == 2
    invalid = browser_page.locator('[data-saved-strategy-state="needs-resave"]')
    assert "需要重新保存" in invalid.inner_text()
    assert invalid.get_by_role("button", name="加载").is_disabled()
    assert browser_page.locator("#savedStrategies").get_by_text("大乐透策略").count() == 0
    saved = browser_page.evaluate("() => JSON.parse(localStorage.getItem('lotteryLuck:strategyLab:ssq'))")
    assert len(saved) == 2


def test_late_strategy_response_is_ignored_after_switching_to_data(live_server_url, browser_page):
    page = browser_page
    calls = []
    page.add_init_script("""
      (() => {
        const originalFetch = window.fetch.bind(window);
        window.fetch = (input, init = {}) => {
          const url = new URL(typeof input === "string" ? input : input.url, location.origin);
          const response = originalFetch(input, init);
          if (url.pathname !== "/api/strategy/ssq/generate") return response;
          return response.then(
            (value) => new Promise((resolve) => setTimeout(() => resolve(value), 800)),
          );
        };
      })();
    """)

    def route_generate(route):
        calls.append(route.request.url)
        route.fulfill(status=200, content_type="application/json", body=json.dumps({
            "game_key": "ssq",
            "preset": "balanced",
            "strategy_name": "迟到策略",
            "description": "竞态测试",
            "conditions": {},
            "basis": {"draw_count": 12, "hot_main": [], "excluded_recent": []},
            "diagnostics": {"preset_label": "均衡型", "condition_count": 0, "active_conditions": []},
            "candidates": [{"main": [1, 2, 3, 4, 5, 6], "special": [7], "tags": ["迟到标记"]}],
            "baseline": {"label": "随机基准", "candidates": []},
            "disclaimer": "历史结果不代表未来概率。",
        }, ensure_ascii=False))

    page.route(f"{live_server_url}/api/strategy/ssq/generate", route_generate)
    page.goto(f"{live_server_url}/analysis.html?game=ssq&view=strategy")
    page.locator("#generateButton").click()
    page.locator('[data-research-view="data"]').click()
    page.wait_for_timeout(1_200)

    assert calls
    assert page.locator("#researchDataView").is_visible()
    assert page.locator("#researchStrategyView").is_hidden()
    assert "迟到标记" not in page.locator("#candidateResult").inner_text()
```

The test deliberately delays the browser-side response promise; do not replace it with Python `time.sleep` in a synchronous Playwright route handler.

- [ ] **Step 3: Run focused tests and verify RED**

Run:

```bash
PYTHONPATH=. .venv/bin/python -m pytest tests/test_frontend_behavior.py -k 'research_center or research_view or strategy_view' -q
```

Expected: research view selectors and handoff button are missing.

- [ ] **Step 4: Add the research center shell and public state API**

Insert `#researchViewTabs` immediately after `#gameTabs`. Wrap the existing `#analysisWorkbench` and `#threeDToolbox` siblings in `#researchDataView`. Move the existing `#strategyLab` markup from `strategy.html` into `#researchStrategyView`, rename its heading to “策略验证”, delete `#strategyCompat`, keep the existing `#strategyForm`, `#generateButton`, `#backtestButton`, `#compareButton`, `#saveStrategyButton`, `#candidateResult`, `#backtestResult` and `#savedStrategies` IDs, and add `#useStrategyButton` next to `#generateButton`.

```html
<div class="research-view-tabs" id="researchViewTabs" role="tablist" aria-label="研究视图">
  <button type="button" role="tab" aria-controls="researchDataView" data-research-view="data">数据观察</button>
  <button type="button" role="tab" aria-controls="researchStrategyView" data-research-view="strategy">策略验证</button>
</div>
```

Both panel wrappers use `role="tabpanel"`, the matching `aria-labelledby`, and `hidden` on the inactive panel. Do not clone the game tabs inside the strategy panel.

Extend `analysis.js` state to `{activeGame, activeView, analysisWindow, games, capabilities}` and expose:

```javascript
const researchSubscribers = new Set();
window.LotteryResearch = Object.freeze({
  getState: () => ({game: state.activeGame, view: state.activeView, window: state.analysisWindow}),
  setView: (view) => activateResearchState({view}),
  setGame: (game) => activateResearchState({game}),
  subscribe(callback) {
    researchSubscribers.add(callback);
    return () => researchSubscribers.delete(callback);
  },
});
```

`syncUrl()` must update the current `URLSearchParams` and always write `game`, `view` and `window`. Preserve `tool` only while `game=3d`, `view=data` and it is one of the seven retained 3D data tools; otherwise remove `tool`, `mode` and stale `source` parameters. `popstate` restores all three owned values and lets `ThreeDWorkbench` restore a retained 3D tool. Invalid values fall back and announce via the existing status region. Every successful `activateResearchState()` call notifies a snapshot to all `researchSubscribers`; the subscriber set is never exposed directly.

- [ ] **Step 5: Move strategy behavior into isolated `research-strategy.js`**

Wrap the new file in an IIFE so its constants do not collide with `analysis.js`. Reuse the existing form serialization, candidate preview, backtest, compare and saved-strategy code, but remove its game-tab rendering and 3D compatibility branch.

```javascript
(() => {
  const state = {game: "ssq", requestToken: 0, preset: "balanced"};
  const unsubscribe = window.LotteryResearch.subscribe((next) => {
    state.game = next.game;
    state.requestToken += 1;
    renderCapabilityFields(next.game);
    renderSavedStrategies(next.game);
    if (next.view === "strategy") generatePreview();
  });

  const initial = window.LotteryResearch.getState();
  state.game = initial.game;
  renderCapabilityFields(initial.game);
  renderSavedStrategies(initial.game);
  if (initial.view === "strategy") generatePreview();

  async function generatePreview() {
    const token = ++state.requestToken;
    const game = state.game;
    const payload = await fetchJson(`/api/strategy/${game}/generate`, requestInit());
    if (token !== state.requestToken || game !== state.game || window.LotteryResearch.getState().view !== "strategy") return;
    renderCandidatePreview(payload);
  }

  window.addEventListener("pagehide", unsubscribe, {once: true});
})();
```

Render only fields declared in `capabilities.research.strategy.condition_fields`. Candidate rows have no copy, basket or CSV controls.

Keep local strategies in their existing per-game keys `lotteryLuck:strategyLab:<game>`; infer the game from the key instead of adding a conflicting game field. Validate `preset` and every stored form key against the current game's capability schema when reading. A valid row keeps its current load/delete actions. An invalid row remains in storage, renders with `data-saved-strategy-state="needs-resave"`, keeps delete enabled, disables load and visibly says “需要重新保存”. Never rewrite another game's key while switching tabs.

Use `/api/games` metadata for the empty-history state. When the active game has `draw_count === 0`, keep rule editing and saving available, disable backtest/compare, and explain “暂无历史数据，不能回测”; switching to a game with data re-enables them. On generate/backtest/compare failure, keep the last successful result in the DOM, show a retry action in the active strategy status region, and do not navigate to tools.

- [ ] **Step 6: Add the one-way handoff producer**

```javascript
function useCurrentStrategy() {
  const research = window.LotteryResearch.getState();
  const handoff = {
    version: 1,
    created_at: Date.now(),
    game_key: research.game,
    source: "strategy",
    preset: state.preset,
    name: presetLabel(state.preset),
    window: Number(form.elements.window.value || 120),
    conditions: normalizedConditions(form, research.game),
  };
  sessionStorage.setItem("lottery_research_handoff_v1", JSON.stringify(handoff));
  window.location.assign(`./tools.html?game=${encodeURIComponent(research.game)}&tool=conditional&source=strategy`);
}
```

Do not generate numbers, add to basket or call tools API before navigation.

- [ ] **Step 7: Run research-center tests and syntax checks**

Run:

```bash
PYTHONPATH=. .venv/bin/python -m pytest tests/test_api.py tests/test_frontend_behavior.py -k 'analysis or strategy or research' -q
node --check web/analysis.js
node --check web/research-strategy.js
```

Expected: focused tests pass; all five games open the strategy view, including `3d`.

- [ ] **Step 8: Commit**

```bash
git add web/analysis.html web/analysis.js web/research-strategy.js web/styles.css tests/test_api.py tests/test_frontend_behavior.py
git commit -m "feat: merge strategy into research center"
```

---

### Task 5: 清除研究中心中的执行工具并兼容旧深链接

**Files:**
- Create: `web/strategy-redirect.js`
- Modify: `web/strategy.html`
- Delete: `web/strategy.js`
- Modify: `web/analysis.html:60-180,190-390`
- Modify: `web/analysis.js:130-220,760-918`
- Modify: `web/three-d-toolbox.js:1-381`
- Modify: `web/workbench-3d.js:35-70,190-220,600-730,1160-1260,1450-1760`
- Modify: `tests/test_api.py:381-430,1539-1585`
- Modify: `tests/test_frontend_behavior.py:1020-1080,1661-3060,3341-4760`

**Interfaces:**
- Consumes: working conditional tool from Task 3.
- Produces: `/strategy.html?...` → `/analysis.html?...&view=strategy` via `location.replace`.
- Produces: `/analysis.html?game=3d&tool=reduction` → `/tools.html?game=3d&tool=conditional&source=legacy`.
- Preserves: 3D `trend|omission|frequency|heat|number|attributes|recent` deep links in the data view.

- [ ] **Step 1: Write failing responsibility-boundary tests**

```python
def test_data_view_contains_observation_only(live_server_url, browser_page):
    browser_page.goto(f"{live_server_url}/analysis.html?game=ssq&view=data")
    browser_page.wait_for_selector("#researchDataView")
    for selector in ["#filterForm", "#backtestForm", "#poolForm", "#poolCopyButton"]:
        assert browser_page.locator(selector).count() == 0
    assert browser_page.locator("#trendPanel").count() == 1
    assert browser_page.locator("#recentPanel").count() == 1


def test_3d_data_catalog_has_no_reduction_tile(live_server_url, browser_page):
    browser_page.goto(f"{live_server_url}/analysis.html?game=3d&view=data")
    browser_page.wait_for_selector("[data-three-d-tool-key]")
    assert browser_page.locator('[data-three-d-tool-key="reduction"]').count() == 0
    assert browser_page.locator('[data-three-d-tool-panel="reduction"]').count() == 0


def test_legacy_strategy_and_reduction_urls_replace_to_new_owner(live_server_url, browser_page):
    browser_page.goto(f"{live_server_url}/strategy.html?game=dlt")
    browser_page.wait_for_url("**/analysis.html?game=dlt&view=strategy")
    browser_page.goto(f"{live_server_url}/analysis.html?game=3d&tool=reduction&window=60")
    browser_page.wait_for_url("**/tools.html?game=3d&tool=conditional&source=legacy")
```

- [ ] **Step 2: Run the focused tests and verify RED**

Run:

```bash
PYTHONPATH=. .venv/bin/python -m pytest tests/test_frontend_behavior.py -k 'observation_only or no_reduction_tile or legacy_strategy_and_reduction' -q
```

Expected: old forms, reduction tile and strategy page still exist.

- [ ] **Step 3: Remove generic execution panels from data view**

Delete the filter, backtest and number-pool articles from `analysis.html`. Remove the associated element lookups, storage helpers, form serializers, event listeners and API calls from `analysis.js`. Keep calendar, common statistics, trend and recent draws.

After removal, the only endpoints called by `view=data` are data/read endpoints such as `/api/analysis`, `/api/calendar`, `/api/workbench/3d/summary`, `/api/3d/trends` and `/api/3d/number-query`.

- [ ] **Step 4: Remove the 3D reduction surface without dropping observation tools**

Remove `reduction` from `TOOLS`, `WINDOW_TOOLS` and event tracking in `three-d-toolbox.js`. Delete the `[data-three-d-tool-panel="reduction"]` markup from `analysis.html`. In `workbench-3d.js`, remove only these responsibilities:

- `REDUCTION_TOOL` and reduction-only state.
- `threeDFilter*` DOM bindings.
- filter form serialization/submission.
- selected-candidate and saved-filter-plan behavior.
- reduction-specific freshness and telemetry branches.

Keep the seven observation tools and their existing request-token, retry, accessibility and freshness behavior.

- [ ] **Step 5: Implement old URL replacement**

```javascript
// web/strategy-redirect.js
(() => {
  const allowed = new Set(["ssq", "dlt", "3d", "pl3", "kl8"]);
  const params = new URLSearchParams(location.search);
  const game = allowed.has(params.get("game")) ? params.get("game") : "ssq";
  location.replace(`./analysis.html?game=${encodeURIComponent(game)}&view=strategy`);
})();
```

Make `strategy.html` a minimal accessible redirect page loading only this script. In `analysis.js`, call the following before initializing data requests:

```javascript
function redirectLegacySelectionRoute() {
  const params = new URLSearchParams(location.search);
  if (params.get("game") !== "3d" || params.get("tool") !== "reduction") return false;
  location.replace("./tools.html?game=3d&tool=conditional&source=legacy");
  return true;
}
```

If it returns true, skip all remaining initialization. Existing legal 3D tool parameters continue through the data view route mapper.

- [ ] **Step 6: Update existing 3D tests instead of deleting coverage**

Change the old catalog expectation from eight tools to seven. Keep trend, omission, frequency, heat, number query, attributes and recent-draw tests. Replace old reduction behavior tests with:

- compatibility redirect assertions in this task;
- conditional tool generation, ordered digits, basket and mobile tests from Task 3.

Do not remove assertions for stale data, request races, disclaimers, focus restoration or mobile overflow on the seven retained tools.

- [ ] **Step 7: Run the data/3D/compatibility slice**

Run:

```bash
PYTHONPATH=. .venv/bin/python -m pytest tests/test_api.py tests/test_frontend_behavior.py -k 'analysis or three_d or 3d_tool or strategy_redirect or legacy' -q
node --check web/analysis.js
node --check web/three-d-toolbox.js
node --check web/workbench-3d.js
node --check web/strategy-redirect.js
git diff --check
```

Expected: all selected tests pass; no reference to removed `threeDFilter*` elements remains.

- [ ] **Step 8: Commit**

```bash
git add web/strategy.html web/strategy-redirect.js web/analysis.html web/analysis.js web/three-d-toolbox.js web/workbench-3d.js tests/test_api.py tests/test_frontend_behavior.py
git rm web/strategy.js
git commit -m "refactor: enforce research and selection boundaries"
```

---

### Task 6: 统一导航并发布到 Next.js 静态层

**Files:**
- Modify: `web/index.html`
- Modify: `web/analysis.html`
- Modify: `web/tools.html`
- Modify: `web/result.html`
- Modify: `web/privacy.html`
- Modify: `web/admin.html`
- Modify: `web/app.js:360-370,1260-1290`
- Modify: `frontend/tests/routes.test.ts`
- Generate: `frontend/public/**`
- Test: `tests/test_api.py`
- Test: `tests/test_frontend_behavior.py`

**Interfaces:**
- Produces identical business navigation on every public page.
- Preserves Next rewrites for `/analysis`, `/strategy` and `/tools`; `/strategy` remains a backward-compatible static route.

- [ ] **Step 1: Write failing navigation tests**

```python
def test_public_navigation_has_research_and_tools_without_strategy_entry(live_server_url, browser_page):
    for path in ["/", "/analysis.html?game=ssq&view=data", "/tools.html?game=ssq", "/privacy.html", "/result.html"]:
        browser_page.goto(f"{live_server_url}{path}")
        nav = browser_page.locator(".header-nav")
        assert nav.get_by_role("link", name="研究中心").count() == 1
        assert nav.get_by_role("link", name="选号工具").count() == 1
        assert nav.get_by_role("link", name="策略实验室").count() == 0
```

Add an API asset assertion that `strategy.html` loads `strategy-redirect.js`, not `strategy.js`.

- [ ] **Step 2: Run navigation tests and verify RED**

Run:

```bash
PYTHONPATH=. .venv/bin/python -m pytest tests/test_api.py tests/test_frontend_behavior.py -k 'navigation or strategy_page' -q
```

Expected: old strategy links are still present.

- [ ] **Step 3: Replace the top-level links everywhere**

Use this business link set on every public header:

```html
<a class="page-link" href="./">预测首页</a>
<a class="page-link" href="./analysis.html?game=ssq&view=data">研究中心</a>
<a class="page-link" href="./tools.html?game=ssq&tool=quick">选号工具</a>
```

Preserve page-specific `active`/`aria-current`, privacy, admin and AI settings controls. In `app.js`, remove `strategyEntry` and its sync function; update `analysisEntry` to include `view=data` and current `game`.

- [ ] **Step 4: Keep deployment route compatibility**

Update `frontend/tests/routes.test.ts` so it continues to assert all three stable routes:

```typescript
expect(rewrites.beforeFiles).toEqual(expect.arrayContaining([
  { source: "/analysis", destination: "/analysis.html" },
  { source: "/strategy", destination: "/strategy.html" },
  { source: "/tools", destination: "/tools.html" },
]));
```

No Next.js runtime API change is required; do not edit Next internals.

- [ ] **Step 5: Sync `web/` into `frontend/public/`**

Run:

```bash
cd frontend
npm run sync:legacy
npm test
npm run build
```

Expected:

- sync reports copied tracked web files;
- Vitest passes;
- Next build exits 0;
- generated `frontend/public/analysis.html`, `tools.html`, redirect assets and scripts match `web/` byte-for-byte.

- [ ] **Step 6: Run static and browser navigation checks**

Run:

```bash
PYTHONPATH=. .venv/bin/python -m pytest tests/test_api.py tests/test_frontend_behavior.py -k 'navigation or research or tools or strategy_redirect' -q
node --check web/app.js
git diff --check
```

Expected: all selected tests pass and no top-level “策略实验室” link remains.

- [ ] **Step 7: Commit**

```bash
git add web/index.html web/analysis.html web/tools.html web/result.html web/privacy.html web/admin.html web/app.js frontend/public frontend/tests/routes.test.ts
git commit -m "feat: unify research and number tool navigation"
```

---

### Task 7: 文档、视觉证据和全量验收

**Files:**
- Modify: `README.md`
- Create: `artifacts/research-center-data-desktop.png`
- Create: `artifacts/research-center-strategy-mobile.png`
- Create: `artifacts/number-tools-conditional-desktop.png`
- Modify: `tests/test_frontend_behavior.py` only if a screenshot reveals a real regression and the fix needs coverage.

**Interfaces:**
- Consumes the completed source tree and generated `frontend/public/`.
- Produces final verification evidence only; no new product behavior.

- [ ] **Step 1: Update README ownership and URLs**

Document:

- two top-level business entries;
- `view=data|strategy` URLs;
- five-game capability differences;
- strategy-to-tools handoff;
- `/strategy` and 3D reduction compatibility routes;
- `web/` → `frontend/public/` sync command.

Remove claims that analysis directly owns filters, backtests, number pools or reduction.

- [ ] **Step 2: Run focused backend and frontend tests**

Run:

```bash
PYTHONPATH=. .venv/bin/python -m pytest tests/test_surface_routes.py tests/test_conditional_tools.py tests/test_number_tools.py tests/test_tool_routes.py -q
PYTHONPATH=. .venv/bin/python -m pytest tests/test_frontend_behavior.py -k 'research or strategy or tools or conditional or migration or navigation or three_d' -q
```

Expected: both commands pass with zero failures.

- [ ] **Step 3: Capture and inspect real browser screenshots**

Capture from the live application, not a mockup:

- 1440×1000: `/analysis.html?game=ssq&view=data`.
- 390×844: `/analysis.html?game=3d&view=strategy`.
- 1440×1000: `/tools.html?game=3d&tool=conditional` with generated results and visible basket.

Save to the three artifact paths listed above. Inspect each image and reject it if loading, clipped, horizontally overflowing, missing the active view/tool, or showing duplicate navigation.

- [ ] **Step 4: Run syntax, sync and production build verification**

Run:

```bash
node --check web/analysis.js
node --check web/research-strategy.js
node --check web/tools.js
node --check web/three-d-toolbox.js
node --check web/workbench-3d.js
node --check web/strategy-redirect.js
cd frontend && npm run sync:legacy && npm test && npm run build
git diff --check
```

Expected: every command exits 0; syncing produces no unexpected untracked files.

- [ ] **Step 5: Run the complete Python suite**

Run:

```bash
PYTHONPATH=. .venv/bin/python -m pytest -q
```

Expected: zero failures. If an unrelated pre-existing failure appears, compare against a fresh main baseline and report it explicitly; do not call the branch fully green or merge without a decision.

- [ ] **Step 6: Verify repository scope**

Run:

```bash
git status --short
git diff --check main..HEAD
git diff --name-only main..HEAD
```

Expected: only planned source, tests, generated public assets, README and three screenshots are present; runtime SQLite data, `.next/`, `node_modules/`, `.vercel/` and Playwright scratch files are absent.

- [ ] **Step 7: Commit**

```bash
git add README.md artifacts/research-center-data-desktop.png artifacts/research-center-strategy-mobile.png artifacts/number-tools-conditional-desktop.png frontend/public
git commit -m "docs: verify research and number tool restructure"
```

---

## Final Review Checklist

- [ ] `研究中心` 是唯一数据观察和策略验证入口。
- [ ] `选号工具` 是唯一最终号码生成、筛减、保存和导出入口。
- [ ] 五彩种使用服务端能力矩阵，不依赖多个前端硬编码副本。
- [ ] 3D/排列3位序、重复数字和组选语义未回归。
- [ ] `lottery_research_handoff_v1` 只消费一次、30分钟过期、跨彩种拒绝。
- [ ] 旧号码池迁移幂等，原键未删除。
- [ ] 旧 `/strategy`、3D缩水和7个3D数据工具深链接可用。
- [ ] 所有公共页面无顶级“策略实验室”链接。
- [ ] `frontend/public/` 与 `web/` 同步，Next production build 通过。
- [ ] Python全量、Vitest、Node语法、diff check 和真实浏览器验收均有新鲜证据。
