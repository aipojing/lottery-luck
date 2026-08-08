# 福彩3D专业工具箱迭代 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将当前难以理解的“福彩3D本期助手”改造成“预测首页负责引流、专业工具箱负责留存”的产品结构，并在首期交付 8 个可真实使用、可解释、可测试的历史数据工具。

**Architecture:** 保留现有预测首页、方案保存和复盘闭环；福彩3D分析页改为工具箱首页，通过 `tool` URL 参数打开独立工具面板。后端继续复用 `workbench_3d.py` 已有的号码属性、位置频次、遗漏、冷热、查询和筛选能力，只为走势图补充一个稳定的历史序列契约；前端新增轻量工具路由层，现有 `workbench-3d.js` 继续负责保存方案和请求状态，避免大规模重写。

**Tech Stack:** FastAPI、Pydantic、SQLite、原生 HTML/CSS/JavaScript、Playwright（pytest）、pytest、现有 `LotteryProduct` 客户端与产品事件体系。

---

## 1. 产品结论

当前问题不是功能完全缺失，而是功能不可发现：

- “简单 / 专业”是内部实现视角，不是用户任务。
- 手动号码、筛选、查询、位置矩阵被塞在一张长页面里，用户无法快速判断能做什么。
- 数据过期时，页面大量按钮禁用，用户会把“本期不可保存”理解成“整个产品不能用”。
- 黑金电影感已经建立，但信息密度、工具入口和结果解释弱于参考产品。

本轮产品结构固定为：

1. **预测首页**：继续承担生辰信息输入、电影感起盘、预测结果和进入工具箱的引流任务。
2. **福彩3D工具箱首页**：展示本期开奖信息、数据状态、工具分组、最近使用和历史方案。
3. **单工具工作区**：每次只解决一个任务，结果、样本窗口、定义和保存动作放在同一屏。
4. **历史数据与本期动作分离**：数据过期时仍允许查看走势、遗漏、出次、冷热、属性和历史查询；只禁止需要声明“本期有效”的生成与保存动作。

## 2. 迭代路线图

### Iteration 1：工具箱 MVP（本计划详细实施，5-7 个开发日）

首期上线 8 个真实工具：

| 工具 | 用户问题 | 数据来源 | 当前基础 | 首期动作 |
| --- | --- | --- | --- | --- |
| 走势图 | 最近号码怎么走 | 历史开奖 | 缺少行序列接口 | 新增趋势契约与表格 |
| 遗漏统计 | 每个位置多久没出 | `position_stats` | 已有 | 独立入口与矩阵 |
| 出次统计 | 最近窗口出现几次 | `position_stats` | 已有 | 独立入口与排序 |
| 冷热码 | 哪些数字偏热/偏冷 | `heat` | 已有 | 独立入口与定义 |
| 号码查询 | 这组号码历史表现如何 | `/api/3d/number-query` | 已有 | 丰富结果表达 |
| 号码属性 | 和值、跨度、奇偶等 | `number_attributes` | 已有 | 从号码查询拆出快捷入口 |
| 缩水选号 | 怎样按条件减少候选 | `/api/3d/filter` | 已有 | 重命名、分步筛选、保存 |
| 最近开奖 | 最近 10 期是什么 | `recent_draws` | 已有 | 放入工具箱并保持可读 |

Iteration 1 不增加任何“中奖概率提高”“推荐必中”文案。工具结果统一标注：样本窗口、最新数据日期、统计定义和“历史统计不代表未来概率”。

### Iteration 2：组合查询（后续单独写实施计划，6-8 个开发日）

- 复式查询：按组选复式和直选位置复式分别生成候选，明确是否允许重复数字。
- 胆拖查询：验证胆码、拖码互斥和最小数量，返回生成规则及候选数量。
- 定位查询：百位、十位、个位分别包含或排除数字。
- 遗漏 K 线：展示指定位置、指定数字在历史窗口内的遗漏序列，而不是金融价格式的误导性涨跌。
- 未出号码：在用户筛选条件内展示窗口未出现候选，限制返回数量并显示总数。

Iteration 2 的组合生成必须先定义玩法语义和输入上限，避免“复式”“胆拖”在不同用户理解中产生歧义。

### Iteration 3：复盘与留存（后续单独写实施计划，5-7 个开发日）

- 3 星复盘：聚合已保存方案的命中类型、覆盖率和连续使用情况。
- 断组观察：只展示历史组态连续段，不使用“推荐必断”表述。
- 遗漏预警：首版为站内规则与提醒中心，不申请系统推送权限。
- 最近使用 / 收藏工具：本地优先，后续有账号体系再云同步。
- 周报：汇总用户实际使用过的工具和方案复盘，不发送预测承诺。

## 3. 成功指标与发布门槛

### 产品指标

- 工具箱访问用户中，`tool_opened` 比例达到 40% 以上。
- 打开工具后，`tool_result_generated` 比例达到 60% 以上。
- 使用缩水选号的用户中，保存方案比例达到 15% 以上。
- 7 日内第二次访问工具箱的比例达到 20% 以上；上线前两周只作为观察目标，不作为统计显著结论。
- 每个事件只记录工具 key、窗口、结果数量和数据状态，不记录生辰、号码明细或可识别个人信息。

### 质量门槛

- `390px`、`768px`、`1440px` 三种宽度无横向溢出。
- 移动端首屏可同时看到开奖状态和至少 6 个工具入口。
- 历史工具在 `fresh`、`attention`、`stale` 三种状态均可打开。
- `stale` 只阻止当前期生成/保存，不阻止历史统计查询。
- 任何工具请求失败时保留上次成功结果，并提供明确重试动作。
- 支持 `prefers-reduced-motion`；工具切换不依赖动画才能理解。
- 完整 pytest、前端语法检查、视觉回归和 `git diff --check` 全部通过。

## 4. 信息架构与页面契约

### 工具箱首页

第一屏顺序固定：

1. 品牌和一级导航。
2. 彩种切换。
3. 本期开奖信息：最新期开奖、目标期、数据新鲜度、历史方案入口。
4. 工具分组：统计、查询、选号、记录。
5. 最近开奖与最近使用。

工具卡不是宣传卡片，固定包含：Lucide 图标、工具名、一行结果导向说明、状态（可用 / 数据待更新）。卡片圆角不超过 `8px`，不做卡片嵌套。

### URL 契约

```text
/analysis.html?game=3d
/analysis.html?game=3d&tool=trend&window=30
/analysis.html?game=3d&tool=omission&window=60
/analysis.html?game=3d&tool=frequency&window=120
/analysis.html?game=3d&tool=heat&window=30
/analysis.html?game=3d&tool=number
/analysis.html?game=3d&tool=attributes
/analysis.html?game=3d&tool=reduction
/analysis.html?game=3d&tool=recent
```

兼容旧链接：

```text
mode=simple -> 工具箱首页
mode=pro    -> tool=frequency
```

工具切换使用 `history.pushState`，窗口切换使用 `history.replaceState`。浏览器返回键必须回到上一个工具或工具箱首页。

### API 契约

保留：

```text
GET  /api/workbench/3d/summary?window=30
POST /api/3d/number-query
POST /api/3d/filter
```

新增：

```text
GET /api/3d/trends?window=30
```

响应示例：

```json
{
  "window": 30,
  "sample_size": 30,
  "latest_issue": "2026182",
  "latest_date": "2026-07-11",
  "definition": "遗漏值按所选窗口从最早一期起累计，仅描述历史序列。",
  "rows": [
    {
      "issue": "2026180",
      "draw_date": "2026-07-09",
      "number_text": "123",
      "numbers": [1, 2, 3],
      "omissions": {
        "0": {"0": 1, "1": 0, "2": 1},
        "1": {"0": 1, "1": 1, "2": 0},
        "2": {"0": 1, "1": 1, "2": 1, "3": 0}
      }
    }
  ],
  "freshness": {
    "status": "fresh",
    "can_claim_current": true
  },
  "actions": {
    "can_read_history": true,
    "can_save_current": true
  }
}
```

`rows` 按日期正序返回，便于表格从旧到新阅读；每个 `omissions` 位置必须包含 `0-9` 十个键，示例为节选。

## 5. 文件边界

### 新建

- `lottery_luck/three_d_tools.py`：趋势行和窗口内遗漏序列构建，不访问数据库。
- `tests/test_three_d_tools.py`：纯领域测试。
- `web/three-d-toolbox.js`：工具目录、URL 状态、工具打开/关闭、产品事件，不保存方案。
- `web/assets/icons/`：从官方 Lucide 包提取的工具图标和许可证，不手绘 SVG。

### 修改

- `lottery_luck/workbench_routes.py`：新增趋势 GET 路由，继续复用已有数据新鲜度与错误映射。
- `lottery_luck/product_events.py`：允许工具打开和结果生成事件，仅开放安全属性。
- `web/analysis.html`：将 3D 区域改为工具箱壳层，并把现有工具表单放入对应面板。
- `web/workbench-3d.js`：保留加载、筛选、查询、保存和计划同步；增加按工具渲染的公共方法。
- `web/workbench-3d.css`：工具箱布局、工具工作区、移动端和 reduced-motion。
- `web/analysis.js`：3D 彩种仍交给专用入口，不重复维护工具路由。
- `web/product-client.js`：不新增业务状态，只复用 `request`、`track`、计划保存方法。
- `tests/test_workbench_routes.py`：趋势 API、stale/empty/invalid window/error mapping。
- `tests/test_frontend_behavior.py`：工具发现、深链接、返回键、历史工具 stale 可用、保存门禁。
- `tests/test_product_events.py`：新增事件白名单与隐私约束。
- `tests/capture_retention_qa.py`：新增工具箱桌面/移动视觉状态。
- `design-qa.md`：记录参考图、实现截图、可见差异和验收结果。
- `README.md`、`docs/OPERATIONS.md`：新增工具 API、数据定义、发布检查。

## 6. Iteration 1 详细开发任务

### Task 1: 固定工具目录和 URL 解析契约

**Files:**
- Create: `web/three-d-toolbox.js`
- Modify: `web/analysis.html`
- Test: `tests/test_frontend_behavior.py`

- [ ] **Step 1: 写失败的工具目录与路由解析测试**

在 `tests/test_frontend_behavior.py` 的 3D 工作台测试区域增加：

```python
def test_3d_toolbox_catalog_and_route_contract(
    live_server_url, browser_page
):
    page = browser_page
    page.goto(f"{live_server_url}/analysis.html?game=ssq")
    page.wait_for_function("Boolean(window.ThreeDToolbox)")
    assert page.evaluate("window.ThreeDToolbox.TOOLS.length") == 8
    assert page.evaluate("window.ThreeDToolbox.normalizeTool('omission')") == "omission"
    assert page.evaluate("window.ThreeDToolbox.normalizeTool('unknown')") == ""
    assert page.evaluate("window.ThreeDToolbox.normalizeWindow('60')") == 60
    assert page.evaluate("window.ThreeDToolbox.normalizeWindow('61')") == 30
```

- [ ] **Step 2: 运行测试并确认失败**

Run:

```bash
PYTHONPATH=. ../../.venv/bin/pytest tests/test_frontend_behavior.py::test_3d_toolbox_catalog_and_route_contract -q
```

Expected: FAIL，因为 `#threeDToolbox` 和 `three-d-toolbox.js` 尚不存在。

- [ ] **Step 3: 建立工具目录与 URL 归一化**

`web/three-d-toolbox.js` 的初始公共契约：

```javascript
(() => {
  "use strict";

  const WINDOWS = new Set([30, 60, 120]);
  const TOOLS = Object.freeze([
    { key: "trend", group: "stats", icon: "trending-up", title: "走势图", description: "按期查看百十个位变化" },
    { key: "omission", group: "stats", icon: "binary", title: "遗漏统计", description: "查看各位置当前遗漏" },
    { key: "frequency", group: "stats", icon: "chart-no-axes-column-increasing", title: "出次统计", description: "比较窗口内出现次数" },
    { key: "heat", group: "stats", icon: "flame", title: "冷热码", description: "频次与遗漏联合分层" },
    { key: "number", group: "query", icon: "search", title: "号码查询", description: "查直选、组选和历史命中" },
    { key: "attributes", group: "query", icon: "list-filter", title: "号码属性", description: "查和值、跨度、奇偶等" },
    { key: "reduction", group: "selection", icon: "sliders-horizontal", title: "缩水选号", description: "按条件减少候选范围" },
    { key: "recent", group: "records", icon: "history", title: "最近开奖", description: "查看最近10期真实开奖" },
  ]);
  const TOOL_KEYS = new Set(TOOLS.map((tool) => tool.key));

  function normalizeTool(value) {
    const key = String(value || "").trim().toLowerCase();
    return TOOL_KEYS.has(key) ? key : "";
  }

  function normalizeWindow(value) {
    const parsed = Number(value);
    return WINDOWS.has(parsed) ? parsed : 30;
  }

  function readRoute() {
    const params = new URLSearchParams(window.location.search);
    const legacyMode = params.get("mode");
    return {
      tool: normalizeTool(params.get("tool") || (legacyMode === "pro" ? "frequency" : "")),
      window: normalizeWindow(params.get("window")),
    };
  }

  window.ThreeDToolbox = Object.freeze({ TOOLS, normalizeTool, normalizeWindow, readRoute });
})();
```

- [ ] **Step 4: 在页面中加入脚本**

`web/analysis.html` 的脚本顺序固定为：

```html
<script src="./product-client.js?v=20260713-product-client-v2" defer></script>
<script src="./workbench-3d.js?v=20260713-toolbox-v1" defer></script>
<script src="./three-d-toolbox.js?v=20260713-toolbox-v1" defer></script>
<script src="./analysis.js?v=20260713-toolbox-v1" defer></script>
```

本任务只冻结解析规则，不改变地址栏。旧 URL 的 `replaceState` 迁移在 Task 5 与工具状态机一起完成，避免两个模块同时拥有路由写权限。

- [ ] **Step 5: 运行测试和语法检查**

Run:

```bash
node --check web/three-d-toolbox.js
PYTHONPATH=. ../../.venv/bin/pytest tests/test_frontend_behavior.py::test_3d_toolbox_catalog_and_route_contract -q
```

Expected: PASS。

- [ ] **Step 6: 提交**

```bash
git add web/three-d-toolbox.js web/analysis.html tests/test_frontend_behavior.py
git commit -m "feat: define 3d toolbox catalog"
```

### Task 2: 构建走势图与窗口内遗漏序列

**Files:**
- Create: `lottery_luck/three_d_tools.py`
- Create: `tests/test_three_d_tools.py`
- Reuse: `lottery_luck/workbench_3d.py`

- [ ] **Step 1: 写失败的领域测试**

```python
from lottery_luck.three_d_tools import build_trend_payload


def draw(issue: str, draw_date: str, red_numbers: str) -> dict[str, str]:
    return {
        "game_key": "3d",
        "game_name": "福彩3D",
        "issue": issue,
        "draw_date": draw_date,
        "red_numbers": red_numbers,
    }


def test_trend_payload_is_chronological_and_resets_window_omission():
    draws = [
        draw("2026182", "2026-07-11", "6,6,2"),
        draw("2026181", "2026-07-10", "0,0,6"),
        draw("2026180", "2026-07-09", "1,2,3"),
    ]

    payload = build_trend_payload(draws, 30)

    assert [row["issue"] for row in payload["rows"]] == [
        "2026180",
        "2026181",
        "2026182",
    ]
    assert payload["rows"][0]["number_text"] == "123"
    assert payload["rows"][0]["omissions"]["0"]["1"] == 0
    assert payload["rows"][1]["omissions"]["0"]["1"] == 1
    assert payload["rows"][2]["omissions"]["0"]["6"] == 0
    assert set(payload["rows"][2]["omissions"]["2"]) == {str(i) for i in range(10)}
```

再增加空数据、非法窗口、前导零和不修改输入列表四个测试。

- [ ] **Step 2: 运行测试并确认失败**

Run:

```bash
PYTHONPATH=. ../../.venv/bin/pytest tests/test_three_d_tools.py -q
```

Expected: FAIL with `ModuleNotFoundError: lottery_luck.three_d_tools`。

- [ ] **Step 3: 实现最小趋势构建函数**

```python
from __future__ import annotations

from typing import Any

from .workbench_3d import ALLOWED_WINDOWS, recent_draw_summaries


def build_trend_payload(
    draws: list[dict[str, Any]],
    window: int,
) -> dict[str, Any]:
    if type(window) is not int or window not in ALLOWED_WINDOWS:
        raise ValueError("invalid 3d data")

    recent = recent_draw_summaries(draws, limit=window)
    chronological = list(reversed(recent))
    omissions = [
        {str(digit): 0 for digit in range(10)}
        for _ in range(3)
    ]
    rows: list[dict[str, Any]] = []

    for draw in chronological:
        for position, hit in enumerate(draw["numbers"]):
            for digit in range(10):
                key = str(digit)
                omissions[position][key] = 0 if digit == hit else omissions[position][key] + 1
        rows.append(
            {
                "issue": draw["issue"],
                "draw_date": draw["draw_date"],
                "number_text": draw["number_text"],
                "numbers": list(draw["numbers"]),
                "omissions": {
                    str(position): dict(values)
                    for position, values in enumerate(omissions)
                },
            }
        )

    latest = chronological[-1] if chronological else None
    return {
        "window": window,
        "sample_size": len(rows),
        "latest_issue": latest["issue"] if latest else "",
        "latest_date": latest["draw_date"] if latest else "",
        "definition": "遗漏值按所选窗口从最早一期起累计，仅描述历史序列。",
        "rows": rows,
    }
```

- [ ] **Step 4: 运行领域测试与现有工作台测试**

Run:

```bash
PYTHONPATH=. ../../.venv/bin/pytest tests/test_three_d_tools.py tests/test_workbench_3d.py -q
```

Expected: PASS，且现有 `workbench_3d.py` 行为无回归。

- [ ] **Step 5: 提交**

```bash
git add lottery_luck/three_d_tools.py tests/test_three_d_tools.py
git commit -m "feat: build 3d trend sequences"
```

### Task 3: 提供趋势 API 并保持 stale 历史可读

**Files:**
- Modify: `lottery_luck/workbench_routes.py`
- Modify: `tests/test_workbench_routes.py`

- [ ] **Step 1: 写失败的路由契约测试**

```python
def test_trends_route_keeps_history_readable_when_current_data_is_stale():
    repo = FakeWorkbenchRepo(status="stale")
    app.dependency_overrides[get_repository] = lambda: repo

    response = client.get("/api/3d/trends?window=30&today=2026-07-13")

    assert response.status_code == 200
    payload = response.json()
    assert payload["rows"]
    assert payload["freshness"]["status"] == "stale"
    assert payload["actions"]["can_read_history"] is True
    assert payload["actions"]["can_save_current"] is False


@pytest.mark.parametrize("window", ["0", "29", "31", "abc", "30.0"])
def test_trends_route_rejects_invalid_window(window):
    app.dependency_overrides[get_repository] = lambda: FakeWorkbenchRepo()
    response = client.get(f"/api/3d/trends?window={window}&today=2026-07-13")
    assert response.status_code == 422
```

- [ ] **Step 2: 运行测试并确认失败**

Run:

```bash
PYTHONPATH=. ../../.venv/bin/pytest tests/test_workbench_routes.py -k trends -q
```

Expected: FAIL with `404 Not Found`。

- [ ] **Step 3: 添加 GET 路由**

在 `lottery_luck/workbench_routes.py` 导入 `build_trend_payload` 并增加：

```python
@router.get("/3d/trends")
def three_d_trends(
    repo: Annotated[LotteryRepository, Depends(get_repository)],
    current_day: CurrentDay,
    window: WindowQuery = "30",
) -> dict[str, Any]:
    normalized_window = int(window)
    try:
        freshness = _public_3d_freshness(repo, current_day)
        draws = repo.recent_draws("3d", limit=normalized_window)
        payload = build_trend_payload(draws, normalized_window)
    except HTTPException:
        raise
    except Exception as exc:
        _handle_workbench_exception(exc)

    payload["freshness"] = freshness
    payload["actions"] = _actions(freshness, draws)
    return payload
```

不要调用 `can_claim_current` 作为读取门禁；趋势属于历史只读工具。

- [ ] **Step 4: 补齐 empty、503 与 OpenAPI 测试**

断言：空数据返回 `200 + rows=[]`；SQLite/OSError 返回不泄漏细节的 `503`；OpenAPI 的 `window` 只允许 `30|60|120`。

- [ ] **Step 5: 运行路由和 API 回归测试**

Run:

```bash
PYTHONPATH=. ../../.venv/bin/pytest tests/test_workbench_routes.py tests/test_api.py -q
```

Expected: PASS。

- [ ] **Step 6: 提交**

```bash
git add lottery_luck/workbench_routes.py tests/test_workbench_routes.py
git commit -m "feat: expose 3d trend history"
```

### Task 4: 建立工具箱首页和工具工作区

**Files:**
- Modify: `web/analysis.html`
- Modify: `web/workbench-3d.css`
- Modify: `web/three-d-toolbox.js`
- Modify: `web/workbench-3d.js`
- Add: `web/assets/icons/*.svg`
- Add: `web/assets/icons/LICENSE`
- Test: `tests/test_frontend_behavior.py`

- [ ] **Step 1: 写失败的可发现性和移动端测试**

```python
def test_3d_toolbox_first_screen_exposes_tools_and_has_no_mobile_overflow(
    live_server_url, browser_page
):
    page = browser_page
    page.set_viewport_size({"width": 390, "height": 844})
    page.goto(f"{live_server_url}/analysis.html?game=3d")
    page.wait_for_selector("#threeDToolbox:not([hidden])")

    assert page.get_by_role("heading", name="福彩3D工具箱").is_visible()
    assert page.get_by_role("button", name="走势图").is_visible()
    assert page.get_by_role("button", name="缩水选号").is_visible()
    assert page.locator("#threeDToolbox").evaluate(
        "node => node.scrollWidth <= document.documentElement.clientWidth"
    )
```

- [ ] **Step 2: 运行测试并确认失败**

Run:

```bash
PYTHONPATH=. ../../.venv/bin/pytest tests/test_frontend_behavior.py::test_3d_toolbox_first_screen_exposes_tools_and_has_no_mobile_overflow -q
```

Expected: FAIL，因为工具箱首页未渲染。

- [ ] **Step 3: 将 3D 区域改成壳层而不是长表单**

`web/analysis.html` 的核心结构：

```html
<section class="three-d-toolbox" id="threeDToolbox" aria-labelledby="threeDToolboxTitle" hidden>
  <header class="three-d-toolbox-head">
    <div>
      <p class="section-kicker">福彩3D · 数据工具</p>
      <h1 id="threeDToolboxTitle">福彩3D工具箱</h1>
      <p>走势、遗漏、查询与选号工具</p>
    </div>
    <a href="./result.html?game=3d">历史方案</a>
  </header>

  <section class="three-d-issue-band" id="threeDIssueBand" aria-live="polite"></section>

  <div id="threeDToolHome">
    <section class="three-d-tool-group" aria-labelledby="threeDStatsToolsTitle">
      <h2 id="threeDStatsToolsTitle">走势统计</h2>
      <div class="three-d-tool-grid" id="threeDStatsTools"></div>
    </section>
    <section class="three-d-tool-group" aria-labelledby="threeDQueryToolsTitle">
      <h2 id="threeDQueryToolsTitle">号码查询</h2>
      <div class="three-d-tool-grid" id="threeDQueryTools"></div>
    </section>
    <section class="three-d-tool-group" aria-labelledby="threeDSelectionToolsTitle">
      <h2 id="threeDSelectionToolsTitle">选号工具</h2>
      <div class="three-d-tool-grid" id="threeDSelectionTools"></div>
    </section>
    <section class="three-d-tool-group" aria-labelledby="threeDRecordToolsTitle">
      <h2 id="threeDRecordToolsTitle">开奖记录</h2>
      <div class="three-d-tool-grid" id="threeDRecordTools"></div>
    </section>
  </div>

  <section id="threeDToolWorkspace" aria-live="polite" hidden>
    <header class="three-d-workspace-head">
      <button type="button" id="threeDToolBack" aria-label="返回工具箱"></button>
      <div><p id="threeDToolKicker"></p><h2 id="threeDToolTitle"></h2></div>
      <div id="threeDToolWindows" role="group" aria-label="统计窗口"></div>
    </header>
    <div id="threeDToolPanels"></div>
  </section>
</section>
```

原手动号码、筛选、号码查询、最近开奖和专业矩阵节点迁入 `#threeDToolPanels`，保留原 ID，避免破坏 `workbench-3d.js` 的绑定。

同时把 `workbench-3d.js` 的根节点缓存从 `#threeDWorkbench` 改为 `#threeDToolbox`。Task 4 只调整根节点和 DOM 归属，不改变筛选、查询或保存行为。

- [ ] **Step 4: 使用官方 Lucide 资源**

固定使用 `lucide-static@0.468.0`，只提取并提交下列官方图标：`trending-up`、`chart-no-axes-column-increasing`、`binary`、`flame`、`search`、`list-filter`、`sliders-horizontal`、`history`、`arrow-left`。同时提交 Lucide 许可证。不得手绘或内联近似 SVG。

Run:

```bash
npm pack lucide-static@0.468.0
tar -xzf lucide-static-0.468.0.tgz
mkdir -p web/assets/icons
cp package/icons/trending-up.svg package/icons/chart-no-axes-column-increasing.svg package/icons/binary.svg package/icons/flame.svg package/icons/search.svg package/icons/list-filter.svg package/icons/sliders-horizontal.svg package/icons/history.svg package/icons/arrow-left.svg web/assets/icons/
cp package/LICENSE web/assets/icons/LICENSE
rm -rf package lucide-static-0.468.0.tgz
```

- [ ] **Step 5: 渲染工具目录并实现稳定布局**

`three-d-toolbox.js` 以 `TOOLS` 为唯一目录来源，使用 DOM API 创建工具按钮：

```javascript
const GROUP_TARGETS = Object.freeze({
  stats: "#threeDStatsTools",
  query: "#threeDQueryTools",
  selection: "#threeDSelectionTools",
  records: "#threeDRecordTools",
});

function renderCatalog() {
  for (const selector of new Set(Object.values(GROUP_TARGETS))) {
    document.querySelector(selector)?.replaceChildren();
  }
  for (const tool of TOOLS) {
    const target = document.querySelector(GROUP_TARGETS[tool.group]);
    if (!target) continue;
    const button = document.createElement("button");
    button.type = "button";
    button.className = "three-d-tool-tile";
    button.dataset.threeDToolKey = tool.key;
    button.setAttribute("aria-label", tool.title);

    const icon = document.createElement("img");
    icon.src = `./assets/icons/${tool.icon}.svg`;
    icon.alt = "";
    icon.width = 28;
    icon.height = 28;

    const title = document.createElement("strong");
    title.textContent = tool.title;
    const description = document.createElement("span");
    description.textContent = tool.description;
    button.append(icon, title, description);
    target.append(button);
  }
}

renderCatalog();
```

为每个 `TOOLS` 条目补充与已提交文件同名的 `icon` 字段。不得使用 `innerHTML` 渲染 API 或目录文本。

CSS 约束：

```css
.three-d-tool-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  border-block-start: 1px solid var(--line);
  border-inline-start: 1px solid var(--line);
}

.three-d-tool-tile {
  min-width: 0;
  min-height: 132px;
  border: 0;
  border-radius: 0;
  border-inline-end: 1px solid var(--line);
  border-block-end: 1px solid var(--line);
}

@media (max-width: 720px) {
  .three-d-tool-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .three-d-tool-tile { min-height: 108px; }
}

@media (prefers-reduced-motion: reduce) {
  .three-d-toolbox *, .three-d-toolbox *::before, .three-d-toolbox *::after {
    scroll-behavior: auto;
    transition-duration: 0.01ms !important;
    animation-duration: 0.01ms !important;
  }
}
```

- [ ] **Step 6: 运行移动端和现有 3D 回归测试**

Run:

```bash
PYTHONPATH=. ../../.venv/bin/pytest tests/test_frontend_behavior.py -k "3d_toolbox or 3d_workbench" -q
```

Expected: PASS，旧保存和查询流程仍可运行。

- [ ] **Step 7: 提交**

```bash
git add web/analysis.html web/workbench-3d.css web/three-d-toolbox.js web/workbench-3d.js web/assets/icons tests/test_frontend_behavior.py
git commit -m "feat: build discoverable 3d toolbox"
```

### Task 5: 完成工具切换、返回键和请求竞态控制

**Files:**
- Modify: `web/three-d-toolbox.js`
- Modify: `web/workbench-3d.js`
- Test: `tests/test_frontend_behavior.py`

- [ ] **Step 1: 写失败的工具切换测试**

测试必须覆盖：点击工具写入 URL；直接深链接恢复工具；旧 `mode=pro` 替换为 `tool=frequency`；切换工具时旧请求晚到不覆盖当前面板；浏览器返回回到工具箱；同一工具切换窗口只替换历史记录。

```python
def test_3d_tool_deep_link_legacy_mode_and_browser_back(
    live_server_url, browser_page
):
    page = browser_page
    page.goto(f"{live_server_url}/analysis.html?game=3d")
    page.get_by_role("button", name="走势图").click()
    page.wait_for_url("**tool=trend&window=30")
    page.go_back()
    assert page.locator("#threeDToolHome").is_visible()

    page.goto(f"{live_server_url}/analysis.html?game=3d&tool=omission&window=60")
    page.wait_for_selector('[data-three-d-tool-panel="omission"]:not([hidden])')
    assert page.locator('[data-three-d-window="60"]').get_attribute("aria-pressed") == "true"

    page.goto(f"{live_server_url}/analysis.html?game=3d&mode=pro&window=120")
    page.wait_for_url("**/analysis.html?game=3d&tool=frequency&window=120")
```

另写 `test_3d_tool_switch_ignores_late_result`：延迟 `/api/workbench/3d/summary`，打开遗漏统计后在响应前使用浏览器返回工具箱并打开号码查询；随后释放 summary 响应，断言当前仍是号码查询且遗漏文本没有写入当前面板。

- [ ] **Step 2: 运行测试并确认失败**

Run:

```bash
PYTHONPATH=. ../../.venv/bin/pytest tests/test_frontend_behavior.py -k "tool_deep_link or tool_switch" -q
```

Expected: FAIL。

- [ ] **Step 3: 实现路由状态机**

`three-d-toolbox.js` 使用单一状态：

```javascript
const state = {
  active: false,
  tool: "",
  window: 30,
  generation: 0,
  abortController: null,
  lastSuccessByTool: new Map(),
};

function routeUrl(tool, windowSize) {
  const params = new URLSearchParams();
  params.set("game", "3d");
  if (tool) params.set("tool", tool);
  if (tool && ["trend", "omission", "frequency", "heat"].includes(tool)) {
    params.set("window", String(windowSize));
  }
  return `./analysis.html?${params.toString()}`;
}

function renderRoute() {
  const home = document.querySelector("#threeDToolHome");
  const workspace = document.querySelector("#threeDToolWorkspace");
  if (!home || !workspace) return;
  const hasTool = Boolean(state.tool);
  home.hidden = hasTool;
  workspace.hidden = !hasTool;
  const selected = TOOLS.find((tool) => tool.key === state.tool);
  const title = document.querySelector("#threeDToolTitle");
  const kicker = document.querySelector("#threeDToolKicker");
  if (title) title.textContent = selected?.title || "";
  if (kicker) kicker.textContent = selected?.description || "";
  document.querySelectorAll("[data-three-d-tool-panel]").forEach((panel) => {
    panel.hidden = panel.dataset.threeDToolPanel !== state.tool;
  });
}

function openTool(tool, { historyMode = "push" } = {}) {
  const normalized = normalizeTool(tool);
  state.tool = normalized;
  state.generation += 1;
  state.abortController?.abort();
  state.abortController = null;
  renderRoute();
  const method = historyMode === "replace" ? "replaceState" : "pushState";
  window.history[method]({}, "", routeUrl(state.tool, state.window));
  loadActiveTool();
}

function initializeRoute() {
  const params = new URLSearchParams(window.location.search);
  const route = readRoute();
  state.tool = route.tool;
  state.window = route.window;
  renderRoute();
  if (params.has("mode")) {
    window.history.replaceState({}, "", routeUrl(state.tool, state.window));
  }
  if (state.tool) loadActiveTool();
}

window.addEventListener("popstate", () => {
  const route = readRoute();
  state.tool = route.tool;
  state.window = route.window;
  state.generation += 1;
  state.abortController?.abort();
  state.abortController = null;
  renderRoute();
  if (state.tool) loadActiveTool();
});

async function loadActiveTool() {
  if (!state.tool || !window.ThreeDWorkbench?.renderTool) return;
  const generation = state.generation;
  const controller = new AbortController();
  state.abortController = controller;
  try {
    await window.ThreeDWorkbench.renderTool(state.tool, {
      window: state.window,
      signal: controller.signal,
    });
  } catch (error) {
    if (error?.name !== "AbortError" && generation === state.generation) {
      renderToolError(state.tool, "加载失败，请重试。");
    }
  } finally {
    if (generation === state.generation) state.abortController = null;
  }
}

function renderToolError(tool, message) {
  if (tool !== state.tool) return;
  const panel = document.querySelector(`[data-three-d-tool-panel="${tool}"]`);
  const status = panel?.querySelector('[data-tool-status]');
  if (!status) return;
  status.textContent = message;
  status.dataset.state = "error";
}

document.querySelector("#threeDToolHome")?.addEventListener("click", (event) => {
  const button = event.target.closest("[data-three-d-tool-key]");
  if (!button) return;
  openTool(button.dataset.threeDToolKey);
});

document.querySelector("#threeDToolBack")?.addEventListener("click", () => {
  if (state.tool) window.history.back();
});

window.ThreeDToolbox = Object.freeze({
  TOOLS,
  normalizeTool,
  normalizeWindow,
  readRoute,
  openTool,
  initializeRoute,
});

initializeRoute();
```

每个请求捕获 `generation`；只有 generation 与当前 tool 都匹配时才能写 DOM。

- [ ] **Step 4: 为现有工作台公开只读适配方法**

`renderTool` 只控制现有面板显示并确保所需 summary 已加载，不改变 URL；URL 只归 `ThreeDToolbox` 管理：

```javascript
const TOOL_KEYS = new Set([
  "trend", "omission", "frequency", "heat",
  "number", "attributes", "reduction", "recent",
]);
const SUMMARY_TOOLS = new Set(["omission", "frequency", "heat", "recent"]);

async function renderTool(tool, options = {}) {
  if (!TOOL_KEYS.has(tool)) return false;
  state.window = normalizeWindow(options.window);
  document.querySelectorAll("[data-three-d-tool-panel]").forEach((panel) => {
    panel.hidden = panel.dataset.threeDToolPanel !== tool;
  });
  if (SUMMARY_TOOLS.has(tool)) {
    await loadAll({ skipFlush: true, signal: options.signal });
  }
  renderAll();
  return true;
}

function setWindow(value) {
  state.window = normalizeWindow(value);
  syncWindowTabs();
}

async function reload(options = {}) {
  return loadAll({ skipFlush: true, signal: options.signal });
}

window.ThreeDWorkbench = Object.freeze({
  activate,
  deactivate,
  renderTool,
  setWindow,
  reload,
  getSummary: () => state.summary,
});
```

把 `loadSummary` 和 `loadAll` 扩展为接受外部 `signal`；外部 signal abort 时必须中止内部 fetch，且不能写入 `state.error`。已有内部 generation 检查继续保留。

- [ ] **Step 5: 运行竞态、返回键和旧工作台回归测试**

Run:

```bash
node --check web/three-d-toolbox.js
node --check web/workbench-3d.js
PYTHONPATH=. ../../.venv/bin/pytest tests/test_frontend_behavior.py -k "tool_switch or ignores_late or 3d_workbench" -q
```

Expected: PASS。

- [ ] **Step 6: 提交**

```bash
git add web/three-d-toolbox.js web/workbench-3d.js tests/test_frontend_behavior.py
git commit -m "feat: route 3d toolbox interactions"
```

### Task 6: 上线走势、遗漏、出次和冷热四个统计工具

**Files:**
- Modify: `web/analysis.html`
- Modify: `web/three-d-toolbox.js`
- Modify: `web/workbench-3d.js`
- Modify: `web/workbench-3d.css`
- Test: `tests/test_frontend_behavior.py`

- [ ] **Step 1: 写失败的四工具渲染测试**

路由拦截 `/api/3d/trends` 和 `/api/workbench/3d/summary`，分别断言：

- 走势表包含期号、日期、百十个位和窗口遗漏。
- 遗漏矩阵完整显示 3 个位置 × 10 个数字。
- 出次统计按当前窗口读取 `frequency`。
- 冷热码展示 `热 / 温 / 冷`，同时显示定义，不能渲染“推荐”“概率”。

```python
assert page.locator('[data-three-d-tool-panel="omission"] [data-position]').count() == 3
assert page.locator('[data-three-d-tool-panel="frequency"] [data-digit-cell]').count() == 30
assert "不代表概率" in page.locator("#threeDToolDefinition").inner_text()
assert "推荐" not in page.locator("#threeDToolWorkspace").inner_text()
```

- [ ] **Step 2: 运行测试并确认失败**

Run:

```bash
PYTHONPATH=. ../../.venv/bin/pytest tests/test_frontend_behavior.py -k "trend_tool or omission_tool or frequency_tool or heat_tool" -q
```

Expected: FAIL。

- [ ] **Step 3: 实现走势图语义表格**

表格使用真实 HTML `<table>`，不使用手绘 SVG。列固定为期号、日期、百位、十位、个位；数字使用圆形标记，窗口遗漏放在单元格的次要文本。移动端外层使用带可见滚动提示的横向滚动容器。

```javascript
function appendCell(row, value, className = "") {
  const cell = document.createElement("td");
  if (className) cell.className = className;
  cell.textContent = String(value ?? "--");
  row.append(cell);
}

function appendDigitCell(row, digit, omission) {
  const cell = document.createElement("td");
  cell.className = "three-d-trend-digit";
  const ball = document.createElement("strong");
  ball.textContent = String(digit);
  const meta = document.createElement("span");
  meta.textContent = `遗漏 ${omission}`;
  cell.append(ball, meta);
  row.append(cell);
}

function renderTrend(payload, panel) {
  const table = document.createElement("table");
  table.className = "three-d-trend-table";
  const body = document.createElement("tbody");
  for (const row of payload.rows || []) {
    const tr = document.createElement("tr");
    appendCell(tr, row.issue);
    appendCell(tr, row.draw_date);
    row.numbers.forEach((digit, position) => {
      appendDigitCell(tr, digit, row.omissions[String(position)][String(digit)]);
    });
    body.append(tr);
  }
  table.append(body);
  panel.replaceChildren(table);
}
```

所有文本使用 `textContent`；禁止拼接 API 文本到 `innerHTML`。

- [ ] **Step 4: 复用 summary 渲染三个矩阵工具**

`omission` 使用 `current_omission`；`frequency` 使用 `frequency`；`heat` 使用 `heat`、`heat_label`、`current_omission`。切换 30/60/120 期时只重新请求 summary，不清空上次成功结果。

- [ ] **Step 5: 运行四工具测试和注入安全测试**

Run:

```bash
PYTHONPATH=. ../../.venv/bin/pytest tests/test_frontend_behavior.py -k "trend_tool or omission_tool or frequency_tool or heat_tool or html_injection" -q
```

Expected: PASS。

- [ ] **Step 6: 提交**

```bash
git add web/analysis.html web/three-d-toolbox.js web/workbench-3d.js web/workbench-3d.css tests/test_frontend_behavior.py
git commit -m "feat: ship 3d statistics tools"
```

### Task 7: 上线号码查询与号码属性

**Files:**
- Modify: `web/analysis.html`
- Modify: `web/workbench-3d.js`
- Modify: `web/workbench-3d.css`
- Test: `tests/test_frontend_behavior.py`

- [ ] **Step 1: 写失败的查询与属性测试**

测试前导零 `006`，断言：直选次数、组选次数、最近命中、三个位置遗漏、和值、和值尾、跨度、组态、奇偶、大小、012 路、质合、相邻和连号全部可见。

```python
page.goto(f"{live_server_url}/analysis.html?game=3d&tool=attributes")
panel = page.locator('[data-three-d-tool-panel="attributes"]')
panel.get_by_label("属性号码").fill("006")
panel.get_by_role("button", name="查询属性").click()

result = panel.locator("[data-tool-result]")
assert "006" in result.inner_text()
assert "和值 6" in result.inner_text()
assert "跨度 6" in result.inner_text()
assert "组三" in result.inner_text()
```

- [ ] **Step 2: 运行测试并确认失败**

Run:

```bash
PYTHONPATH=. ../../.venv/bin/pytest tests/test_frontend_behavior.py -k "number_tool or attributes_tool" -q
```

Expected: FAIL。

- [ ] **Step 3: 共用一个请求，提供两种结果重点**

两个工具都调用现有 `/api/3d/number-query`：

- `number` 面板优先展示历史 exact/group 和位置遗漏。
- `attributes` 面板优先展示 `attributes`，历史命中收起为次要信息。

不得在前端重新计算完整属性；`minimalMetrics()` 只保留给离线保存兼容，在线展示以服务器返回为准。

- [ ] **Step 4: 处理输入、错误和竞态**

- 只接受三个 ASCII 数字。
- 输入变化立即废弃旧结果的可保存状态。
- HTTP 422 显示“请输入三位数字”。
- 网络失败保留上次成功结果并显示“刷新失败”。
- stale 状态仍允许查询，因为该接口只读历史。

- [ ] **Step 5: 运行测试**

Run:

```bash
PYTHONPATH=. ../../.venv/bin/pytest tests/test_workbench_routes.py -k number_query -q
PYTHONPATH=. ../../.venv/bin/pytest tests/test_frontend_behavior.py -k "number_tool or attributes_tool" -q
```

Expected: PASS。

- [ ] **Step 6: 提交**

```bash
git add web/analysis.html web/workbench-3d.js web/workbench-3d.css tests/test_frontend_behavior.py
git commit -m "feat: clarify 3d number analysis"
```

### Task 8: 将快速筛选升级为缩水选号并接回方案闭环

**Files:**
- Modify: `web/analysis.html`
- Modify: `web/workbench-3d.js`
- Modify: `web/workbench-3d.css`
- Test: `tests/test_frontend_behavior.py`
- Test: `tests/test_retention_flow.py`

- [ ] **Step 1: 写失败的缩水流程测试**

测试流程：选择和值、跨度、组态、奇数个数和位置包含/排除；生成候选；显示 `1000 -> N`；选中若干号码；保存为 `source_type=filter` 方案；stale 时允许编辑条件但禁止声明本期并保存。

```python
assert page.get_by_text("原始范围 1000 组").is_visible()
assert page.get_by_text("筛后候选 12 组").is_visible()
assert page.locator("[data-candidate-number]").count() == 12
assert saved_payload["source_type"] == "filter"
assert saved_payload["condition_snapshot"]["window"] == 30
```

- [ ] **Step 2: 运行测试并确认失败**

Run:

```bash
PYTHONPATH=. ../../.venv/bin/pytest tests/test_frontend_behavior.py -k reduction_tool -q
```

Expected: FAIL。

- [ ] **Step 3: 重排表单，不改变后端过滤语义**

分为三组控件：

1. 数值范围：和值、跨度。
2. 号码形态：豹子/组三/组六、奇数个数。
3. 位置约束：百十个位包含/排除。

调用仍为：

```javascript
const payload = await window.LotteryProduct.request("/api/3d/filter", {
  method: "POST",
  body: JSON.stringify({ filters, window: state.window }),
  signal: controller.signal,
});
```

候选总数使用服务器 `total`，不以当前分页列表长度冒充。

- [ ] **Step 4: 保持当前期门禁准确**

- `fresh/attention + can_claim_current=true`：允许生成和保存。
- `stale/empty`：表单仍可查看，提交前显示数据日期并阻止请求；历史工具不受影响。
- 网络失败：保留上次候选和已选项。
- 条件变化：清除旧 request id，下一次保存生成新 id。

- [ ] **Step 5: 运行缩水、方案保存和 retention 回归测试**

Run:

```bash
PYTHONPATH=. ../../.venv/bin/pytest tests/test_workbench_3d.py -k filter_candidates -q
PYTHONPATH=. ../../.venv/bin/pytest tests/test_frontend_behavior.py -k "reduction_tool or save_plan" -q
PYTHONPATH=. ../../.venv/bin/pytest tests/test_retention_flow.py -q
```

Expected: PASS。

- [ ] **Step 6: 提交**

```bash
git add web/analysis.html web/workbench-3d.js web/workbench-3d.css tests/test_frontend_behavior.py tests/test_retention_flow.py
git commit -m "feat: turn filters into 3d reduction tool"
```

### Task 9: 增加安全的工具使用事件

**Files:**
- Modify: `lottery_luck/product_events.py`
- Modify: `web/three-d-toolbox.js`
- Modify: `web/workbench-3d.js`
- Test: `tests/test_product_events.py`
- Test: `tests/test_frontend_behavior.py`

- [ ] **Step 1: 写失败的事件白名单测试**

```python
@pytest.mark.parametrize(
    ("event_name", "properties"),
    [
        ("tool_opened", {"game_key": "3d", "tool_key": "trend", "window": 30}),
        (
            "tool_result_generated",
            {"game_key": "3d", "tool_key": "reduction", "result_count": 12},
        ),
    ],
)
def test_tool_events_accept_only_safe_aggregate_properties(connection, event_name, properties):
    event = record_event(
        connection,
        client_id="client-a",
        event_name=event_name,
        properties=properties,
    )
    assert event["properties"] == properties
```

再断言 `number_text`、`birth_date`、`birth_time`、任意未知 `tool_key` 被拒绝。

- [ ] **Step 2: 运行测试并确认失败**

Run:

```bash
PYTHONPATH=. ../../.venv/bin/pytest tests/test_product_events.py -k tool_event -q
```

Expected: FAIL with `invalid product event`。

- [ ] **Step 3: 扩展最小事件契约**

```python
ALLOWED_EVENT_NAMES = {
    # existing names...
    "tool_opened",
    "tool_result_generated",
}

ALLOWED_PROPERTY_KEYS = {
    # existing keys...
    "tool_key",
    "result_count",
}

STRING_PROPERTY_VALUES["tool_key"] = {
    "trend",
    "omission",
    "frequency",
    "heat",
    "number",
    "attributes",
    "reduction",
    "recent",
}

COUNT_PROPERTY_KEYS = {"entry_count", "candidate_count", "result_count"}
INTEGER_PROPERTY_KEYS = {"window", *COUNT_PROPERTY_KEYS}
```

保持事件 payload 最大 `2048 bytes` 和 client id 截断规则不变。

- [ ] **Step 4: 前端只在真实成功后记录一次**

- 工具面板首次成功打开后记录 `tool_opened`。
- 用户主动提交并收到有效响应后记录 `tool_result_generated`。
- 返回缓存、请求失败、被取消和 UI 重渲染不能重复记录。
- `number` 与 `attributes` 事件不包含用户输入号码。

- [ ] **Step 5: 运行隐私与事件去重测试**

Run:

```bash
PYTHONPATH=. ../../.venv/bin/pytest tests/test_product_events.py -q
PYTHONPATH=. ../../.venv/bin/pytest tests/test_frontend_behavior.py -k "tool_event or event_payloads_are_safe" -q
```

Expected: PASS。

- [ ] **Step 6: 提交**

```bash
git add lottery_luck/product_events.py web/three-d-toolbox.js web/workbench-3d.js tests/test_product_events.py tests/test_frontend_behavior.py
git commit -m "feat: measure 3d toolbox usage safely"
```

### Task 10: 视觉、可访问性、文档与发布验收

**Files:**
- Modify: `tests/capture_retention_qa.py`
- Modify: `design-qa.md`
- Modify: `README.md`
- Modify: `docs/OPERATIONS.md`
- Add: `artifacts/fc3d-toolbox-home-desktop.png`
- Add: `artifacts/fc3d-toolbox-trend-desktop.png`
- Add: `artifacts/fc3d-toolbox-reduction-mobile.png`
- Add: `artifacts/fc3d-toolbox-stale-mobile.png`

- [ ] **Step 1: 扩展确定性视觉捕获**

固定临时 SQLite、固定 `today=2026-07-13`、关闭自动更新、禁用外部网络。捕获：

1. `1440px` 工具箱首页。
2. `1440px` 走势工具 30 期。
3. `390px` 缩水选号筛选结果。
4. `390px` stale 状态的历史工具可读、本期保存禁用。

- [ ] **Step 2: 运行行为和视觉检查**

Run:

```bash
PYTHONPATH=. ../../.venv/bin/pytest tests/test_frontend_behavior.py -k "3d_toolbox or trend_tool or reduction_tool" -q
PYTHONPATH=. ../../.venv/bin/python tests/capture_retention_qa.py
```

Expected: 测试 PASS，四张截图存在且非空。

- [ ] **Step 3: 做真实视觉对照**

把用户提供的参考截图和四张实现截图放入同一次对照检查，逐项确认：

- 工具可发现性达到参考图水平。
- 黑金视觉没有牺牲文字可读性。
- 首屏没有巨型标题或空白装饰。
- 工具卡不是卡片嵌套。
- 最长中文标签在 390px 不截断、不覆盖。
- 数据状态与禁用原因紧邻受影响动作。

将可见差异、接受原因和修复项写入 `design-qa.md`。

- [ ] **Step 4: 做可访问性检查**

至少验证：键盘 Tab 顺序、返回按钮可访问名称、`aria-pressed` 窗口状态、`aria-live` 错误、焦点进入工具工作区、reduced-motion、文本对比度和 200% 缩放。

- [ ] **Step 5: 更新运行文档**

`README.md` 增加工具 URL 与开发验证命令；`docs/OPERATIONS.md` 增加趋势定义、stale 行为、事件隐私和发布前数据新鲜度检查。

- [ ] **Step 6: 运行完整验收**

Run:

```bash
PYTHONPATH=. ../../.venv/bin/pytest -q
for file in web/app.js web/product-client.js web/workbench-3d.js web/three-d-toolbox.js web/analysis.js web/result.js web/strategy.js web/admin.js web/motion.js; do node --check "$file"; done
git diff --check
git status --short
```

Expected:

- 全量测试 PASS。
- 所有 `node --check` PASS。
- `git diff --check` 无输出。
- `git status --short` 只包含本计划预期文件；不提交 `cwl_history/cwl_history.sqlite`。

- [ ] **Step 7: 提交**

```bash
git add tests/capture_retention_qa.py design-qa.md README.md docs/OPERATIONS.md artifacts/fc3d-toolbox-*.png
git commit -m "docs: complete 3d toolbox release qa"
```

## 7. Iteration 1 验收清单

- [ ] 首页仍是预测首页，生辰起盘流程不被工具箱改动。
- [ ] 进入福彩3D分析后默认看到工具箱，而不是“简单/专业”长表单。
- [ ] 8 个工具入口名称、说明和状态一眼可见。
- [ ] 走势图、遗漏、出次、冷热、号码查询、号码属性、缩水选号、最近开奖均返回真实结果。
- [ ] 所有历史工具在 stale 数据下仍可读。
- [ ] 当前期生成和保存严格受 `can_claim_current` 控制。
- [ ] 工具深链接、返回键和窗口参数可恢复。
- [ ] 方案保存、离线队列、历史方案、开奖复盘和携带方案无回归。
- [ ] 产品事件不包含生辰、号码明细或自由文本。
- [ ] 移动端首屏、桌面端、reduced-motion 和网络错误状态均有视觉证据。

## 8. 后续计划拆分

Iteration 2 和 Iteration 3 不应直接追加到本计划中执行。Iteration 1 上线并取得真实工具使用数据后，分别创建：

```text
docs/superpowers/plans/2026-xx-xx-fc3d-combination-tools-plan.md
docs/superpowers/plans/2026-xx-xx-fc3d-review-alerts-plan.md
```

组合工具计划必须先确认玩法语义；复盘预警计划必须先确认站内提醒、账号同步和隐私边界。
