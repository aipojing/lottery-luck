# 四彩种数据分析工作台 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a four-game lottery analysis workbench below the existing prediction board.

**Architecture:** Add a pure backend analysis module that computes hot, cold, omission, trend, shape, and recent draw metadata from repository history. Expose it through `GET /api/analysis/{game_key}`, then render a compact black-gold frontend workbench that reloads on game and window changes without triggering prediction.

**Tech Stack:** FastAPI, Pydantic, Python stdlib counters, existing SQLite-backed `LotteryRepository`, vanilla HTML/CSS/JS.

---

## File Structure

- Create: `lottery_luck/analysis.py`
  - Owns all historical analysis calculations and payload formatting.
- Create: `tests/test_analysis.py`
  - Unit tests for hot/cold/omission/shape/trend calculations using hand-built samples.
- Modify: `lottery_luck/api.py`
  - Adds `GET /api/analysis/{game_key}` and validates supported games/windows.
- Modify: `tests/test_api.py`
  - Adds API coverage for all games and invalid windows.
- Modify: `web/index.html`
  - Adds `analysisWorkbench` below the current basis grid.
- Modify: `web/app.js`
  - Adds analysis state, fetch, rendering, demo fallback, and window tab behavior.
- Modify: `web/styles.css`
  - Adds responsive black-gold analysis layouts and compact trend grid styling.

## Task 1: Backend Analysis Engine

**Files:**
- Create: `tests/test_analysis.py`
- Create: `lottery_luck/analysis.py`

- [ ] **Step 1: Write failing unit tests**

```python
from lottery_luck.analysis import build_analysis_payload


def test_analysis_payload_calculates_hot_cold_and_omission_for_ssq_sample():
    draws = [
        {"issue": "003", "draw_date": "2026-06-10", "red_numbers": "01,02,03,04,05,06", "blue_number": "07"},
        {"issue": "002", "draw_date": "2026-06-08", "red_numbers": "01,02,03,07,08,09", "blue_number": "08"},
        {"issue": "001", "draw_date": "2026-06-06", "red_numbers": "10,11,12,13,14,15", "blue_number": "07"},
    ]

    payload = build_analysis_payload("ssq", draws, 30)

    assert payload["summary"] == {"draw_count": 3, "latest_issue": "003", "latest_date": "2026-06-10"}
    assert payload["hot"]["main"][:3] == [
        {"number": 1, "count": 2},
        {"number": 2, "count": 2},
        {"number": 3, "count": 2},
    ]
    assert payload["hot"]["special"][0] == {"number": 7, "count": 2}
    assert payload["cold"]["main"][0] == {"number": 16, "count": 0}
    assert payload["omission"]["main"][0] == {"number": 16, "missing": 3}
    assert payload["omission"]["special"][0] == {"number": 1, "missing": 3}


def test_analysis_payload_calculates_3d_position_and_shape():
    draws = [
        {"issue": "003", "draw_date": "2026-06-10", "red_numbers": "1,2,3", "blue_number": ""},
        {"issue": "002", "draw_date": "2026-06-09", "red_numbers": "1,1,2", "blue_number": ""},
        {"issue": "001", "draw_date": "2026-06-08", "red_numbers": "7,7,7", "blue_number": ""},
    ]

    payload = build_analysis_payload("3d", draws, 30)

    assert payload["position_hot"][0][0] == {"number": 1, "count": 2}
    assert payload["position_hot"][1][0] == {"number": 1, "count": 1}
    assert {"label": "组六", "count": 1} in payload["shape"]["digit_types"]
    assert {"label": "组三", "count": 1} in payload["shape"]["digit_types"]
    assert {"label": "豹子", "count": 1} in payload["shape"]["digit_types"]


def test_analysis_payload_groups_kl8_ranges_and_recent_overlap():
    draws = [
        {
            "issue": "002",
            "draw_date": "2026-06-10",
            "red_numbers": "01,02,11,12,21,22,31,32,41,42,51,52,61,62,71,72,73,74,75,76",
            "blue_number": "",
        },
        {
            "issue": "001",
            "draw_date": "2026-06-09",
            "red_numbers": "03,04,13,14,23,24,33,34,43,44,53,54,63,64,77,78,79,80,05,06",
            "blue_number": "",
        },
    ]

    payload = build_analysis_payload("kl8", draws, 30, prediction={"main": [1, 2, 3], "special": []})

    assert payload["shape"]["range_distribution"][0] == {"label": "01-10", "count": 6}
    assert payload["recent_draws"][0]["overlap_with_prediction"] == 2
    assert payload["trend"]["columns"][0] == "01-10"
    assert payload["trend"]["rows"][0]["hits"][0] == "01-10"
```

- [ ] **Step 2: Run tests to verify RED**

Run: `PYTHONPATH=. .venv/bin/pytest tests/test_analysis.py -q`

Expected: FAIL because `lottery_luck.analysis` does not exist.

- [ ] **Step 3: Implement analysis module**

Create `lottery_luck/analysis.py` with:

```python
from __future__ import annotations

from collections import Counter
from typing import Any

from .rules import GAME_RULES, parse_numbers

ALLOWED_WINDOWS = {30, 60, 120}


def normalize_window(value: int | str | None) -> int:
    try:
        window = int(value) if value is not None else 30
    except (TypeError, ValueError):
        return 30
    return window if window in ALLOWED_WINDOWS else 30


def build_analysis_payload(
    game_key: str,
    draws: list[dict[str, Any]],
    window: int | str | None = 30,
    prediction: dict[str, list[int]] | None = None,
) -> dict[str, Any]:
    game = game_key.strip().lower()
    if game not in GAME_RULES:
        raise ValueError(f"unsupported game_key: {game}")
    normalized_window = normalize_window(window)
    window_draws = draws[:normalized_window]
    parsed_draws = [_parse_draw(game, draw) for draw in window_draws]

    return {
        "game_key": game,
        "window": normalized_window,
        "summary": _summary(window_draws),
        "hot": {
            "main": _rank_counts(game, parsed_draws, "main", "hot"),
            "special": _rank_counts(game, parsed_draws, "special", "hot"),
        },
        "cold": {
            "main": _rank_counts(game, parsed_draws, "main", "cold"),
            "special": _rank_counts(game, parsed_draws, "special", "cold"),
        },
        "omission": {
            "main": _omission(game, parsed_draws, "main"),
            "special": _omission(game, parsed_draws, "special"),
        },
        "position_hot": _position_hot(game, parsed_draws),
        "shape": _shape(game, parsed_draws),
        "trend": _trend(game, parsed_draws),
        "recent_draws": _recent_draws(parsed_draws, prediction),
    }
```

The implementation keeps helpers private and focused: `_parse_draw` normalizes repository rows, `_summary` reads latest metadata, `_rank_counts` sorts hot/cold rows, `_omission` computes latest-missing windows, `_position_rank` and `_position_omission` handle 3D position statistics, `_shape` composes per-game shape metrics, `_trend` emits compact trend rows, and `_recent_draws` formats recent draw rows.

- [ ] **Step 4: Run unit tests to verify GREEN**

Run: `PYTHONPATH=. .venv/bin/pytest tests/test_analysis.py -q`

Expected: PASS.

## Task 2: Analysis API

**Files:**
- Modify: `tests/test_api.py`
- Modify: `lottery_luck/api.py`

- [ ] **Step 1: Write failing API tests**

Append to `tests/test_api.py`:

```python
@pytest.mark.parametrize("game_key", ["ssq", "3d", "qlc", "kl8"])
def test_analysis_endpoint_returns_supported_games(game_key):
    response = client.get(f"/api/analysis/{game_key}?window=30")

    assert response.status_code == 200
    payload = response.json()
    assert payload["game_key"] == game_key
    assert payload["window"] == 30
    assert payload["summary"]["draw_count"] > 0
    assert "hot" in payload
    assert "cold" in payload
    assert "omission" in payload
    assert "shape" in payload
    assert "trend" in payload
    assert "recent_draws" in payload


def test_analysis_endpoint_invalid_window_falls_back_to_30():
    response = client.get("/api/analysis/ssq?window=999")

    assert response.status_code == 200
    assert response.json()["window"] == 30


def test_analysis_endpoint_invalid_game_returns_404():
    response = client.get("/api/analysis/nope")

    assert response.status_code == 404
```

- [ ] **Step 2: Run tests to verify RED**

Run: `PYTHONPATH=. .venv/bin/pytest tests/test_api.py::test_analysis_endpoint_returns_supported_games tests/test_api.py::test_analysis_endpoint_invalid_window_falls_back_to_30 tests/test_api.py::test_analysis_endpoint_invalid_game_returns_404 -q`

Expected: FAIL with 404 because the route is missing.

- [ ] **Step 3: Implement API route**

Modify `lottery_luck/api.py`:

```python
from .analysis import build_analysis_payload, normalize_window
from .rules import GAME_RULES
```

Add before `app.mount(...)`:

```python
@app.get("/api/analysis/{game_key}")
def analysis(
    game_key: str,
    repo: Annotated[LotteryRepository, Depends(get_repository)],
    window: int = 30,
) -> dict[str, Any]:
    game = game_key.strip().lower()
    if game not in GAME_RULES:
        raise HTTPException(status_code=404, detail=f"unsupported game_key: {game}")
    return build_analysis_payload(game, repo.recent_draws(game, limit=normalize_window(window)), window)
```

- [ ] **Step 4: Run API tests to verify GREEN**

Run: `PYTHONPATH=. .venv/bin/pytest tests/test_api.py -q`

Expected: PASS.

## Task 3: Frontend Analysis Workbench

**Files:**
- Modify: `web/index.html`
- Modify: `web/app.js`
- Modify: `web/styles.css`

- [ ] **Step 1: Add DOM shell**

Insert below the existing `basis-grid` section in `web/index.html`:

```html
<section class="analysis-workbench" id="analysisWorkbench" aria-label="数据分析">
  <div class="analysis-head">
    <div>
      <p class="section-kicker">历史数据</p>
      <h2>数据分析</h2>
    </div>
    <div class="analysis-window-tabs" id="analysisWindowTabs" aria-label="分析窗口"></div>
  </div>
  <div class="analysis-summary" id="analysisSummary">分析数据加载中。</div>
  <div class="analysis-grid">
    <article class="analysis-card" id="analysisHotCold"></article>
    <article class="analysis-card" id="analysisTrend"></article>
    <article class="analysis-card" id="analysisShape"></article>
    <article class="analysis-card" id="analysisRecentDraws"></article>
  </div>
</section>
```

Update asset query strings to `20260616-gold-plate-8`.

- [ ] **Step 2: Add frontend analysis state and renderers**

Modify `web/app.js`:

```javascript
const ANALYSIS_WINDOWS = [30, 60, 120];

state.analysisWindow = 30;

Object.assign(els, {
  analysisWorkbench: document.querySelector("#analysisWorkbench"),
  analysisWindowTabs: document.querySelector("#analysisWindowTabs"),
  analysisSummary: document.querySelector("#analysisSummary"),
  analysisHotCold: document.querySelector("#analysisHotCold"),
  analysisTrend: document.querySelector("#analysisTrend"),
  analysisShape: document.querySelector("#analysisShape"),
  analysisRecentDraws: document.querySelector("#analysisRecentDraws"),
});
```

Add functions `demoAnalysisPayload`, `renderAnalysisWindowTabs`, `renderAnalysis`, `renderAnalysisStatus`, `renderAnalysisRank`, `loadAnalysis`, `formatAnalysisNumber`, and `analysisTitle`.

Hook `renderAnalysisWindowTabs()` into startup, call `loadAnalysis()` after `loadGames()`, and call `loadAnalysis()` in game tab clicks without calling `predict()` twice.

- [ ] **Step 3: Add styles**

Append styles to `web/styles.css`:

```css
.analysis-workbench {
  width: min(1220px, calc(100% - 76px));
  margin: 42px auto 0;
  border-top: 1px solid rgba(214, 169, 88, 0.24);
  padding-top: 32px;
}
```

Add complete styles for `analysis-head`, `section-kicker`, `analysis-window-tabs`, `analysis-window-button`, `analysis-summary`, `analysis-grid`, `analysis-card`, `analysis-rank`, `analysis-trend-grid`, `analysis-shape-list`, `analysis-draw-list`, and responsive rules under existing media queries.

- [ ] **Step 4: Browser smoke check**

Use the in-app browser on `http://127.0.0.1:8017/`.

Expected:
- The page shows `数据分析`.
- Window buttons switch between 30, 60, and 120.
- Game tabs refresh analysis content.
- Desktop has no horizontal overflow.
- Mobile viewport has no overlapping text.

## Task 4: Full Verification

**Files:**
- Read only unless a verification issue requires a fix.

- [ ] **Step 1: Run all tests**

Run: `PYTHONPATH=. .venv/bin/pytest -q`

Expected: all tests pass.

- [ ] **Step 2: Verify frontend manually**

Use browser inspection or screenshots for desktop and mobile.

Expected:
- `#analysisWorkbench` exists and is visible.
- `#analysisWindowTabs button` count is 3.
- `document.documentElement.scrollWidth <= window.innerWidth` is true on desktop and mobile.

- [ ] **Step 3: Summarize changes**

Report changed files, test command output, and any known limitation. Because this workspace is not a git repository, skip commit steps and state that explicitly.
