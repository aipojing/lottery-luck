# Strategy Lab V1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a standalone Strategy Lab page where users can configure, generate, backtest, compare, and locally save lottery number strategies.

**Architecture:** Add a focused `lottery_luck.strategy` module that translates presets and custom strategy conditions into existing analysis filters, then layers deterministic historical backtests and a deterministic random baseline on top. Expose this through `/api/strategy/{game}/generate`, `/api/strategy/{game}/backtest`, and `/api/strategy/{game}/compare`; add `strategy.html` and `strategy.js` as a separate frontend surface. Reserve sports-lottery rules in `rules.py` without exposing them as active games until a sports-lottery crawler/data source exists.

**Tech Stack:** FastAPI, Pydantic, Python stdlib, existing SQLite repository, vanilla HTML/CSS/JS, localStorage.

---

## File Structure

- Create `lottery_luck/strategy.py`: preset definitions, strategy request normalization, candidate generation, deterministic baseline, strategy backtest, preset comparison.
- Modify `lottery_luck/api.py`: Pydantic request models and strategy endpoints.
- Modify `lottery_luck/rules.py`: reserve sports-lottery rule definitions for 大乐透、排列3、排列5 without adding them to active `GAME_RULES`.
- Create `tests/test_strategy.py`: unit tests for strategy presets, generation, backtest, compare, and deterministic baseline.
- Modify `tests/test_api.py`: API and static-page tests for strategy lab.
- Modify `tests/test_rules.py`: sports-lottery reserve tests.
- Create `web/strategy.html`: standalone Strategy Lab page.
- Create `web/strategy.js`: game tabs, preset/custom strategy form, generate/backtest/compare, local saved strategies.
- Modify `web/styles.css`: reuse the black-gold system and add Strategy Lab layouts.
- Modify `web/index.html` and `web/analysis.html`: add navigation links to Strategy Lab.
- Modify `tests/test_scaffold.py`: make project-root test compatible with git worktrees.

## Task 1: Sports Lottery Extension Slot

**Files:**
- Modify `lottery_luck/rules.py`
- Modify `tests/test_rules.py`

- [x] Write a failing test that imports `RESERVED_GAME_RULES` and asserts `dlt`, `pl3`, and `pl5` exist with provider `sports`, while active `GAME_RULES` remains exactly `{"ssq", "3d", "qlc", "kl8"}`.
- [x] Run `PYTHONPATH=. .venv/bin/pytest tests/test_rules.py -q` and verify it fails because `RESERVED_GAME_RULES` is missing.
- [x] Add reserved `GameRule` entries:
  - `dlt`: 大乐透, main 1-35 pick 5, special 1-12 pick 2, provider `sports`.
  - `pl3`: 排列3, digits 0-9 pick 3, repeat allowed, provider `sports`.
  - `pl5`: 排列5, digits 0-9 pick 5, repeat allowed, provider `sports`.
- [x] Run `PYTHONPATH=. .venv/bin/pytest tests/test_rules.py -q` and verify pass.

## Task 2: Strategy Domain Module

**Files:**
- Create `lottery_luck/strategy.py`
- Create `tests/test_strategy.py`

- [x] Write failing tests for:
  - `STRATEGY_PRESETS` containing `conservative`, `balanced`, `aggressive`.
  - `generate_strategy_candidates("ssq", draws, {"preset": "balanced", "candidate_count": 5})` returning conditions, candidates, diagnostics, and random baseline candidates.
  - custom overrides such as `{"conditions": {"tail_exclude": [0], "ac_min": 4}}` being applied to all candidates.
  - `backtest_strategy_lab` returning average hits, max hits, hit distribution, and baseline average.
  - `compare_strategy_presets` returning the three preset rows sorted by average hits.
- [x] Run `PYTHONPATH=. .venv/bin/pytest tests/test_strategy.py -q` and verify import/function failures.
- [x] Implement `lottery_luck.strategy` by reusing `filter_candidates`, `GAME_RULES`, and parsed draw rows compatible with existing `analysis.py`.
- [x] Use deterministic baseline generation based on issue/date offsets, not global randomness.
- [x] Run `PYTHONPATH=. .venv/bin/pytest tests/test_strategy.py -q` and verify pass.

## Task 3: Strategy API

**Files:**
- Modify `lottery_luck/api.py`
- Modify `tests/test_api.py`

- [x] Write failing API tests for:
  - `GET /strategy.html` serving the page shell.
  - `POST /api/strategy/ssq/generate` returning candidates and baseline.
  - `POST /api/strategy/ssq/backtest` returning hit distribution and baseline average.
  - `POST /api/strategy/ssq/compare` returning at least three preset rows.
- [x] Run targeted tests and verify failures.
- [x] Add `StrategyRequest` and `StrategyCompareRequest` Pydantic models.
- [x] Add endpoints that call the strategy module with repository draws.
- [x] Run targeted API tests and verify pass.

## Task 4: Strategy Lab Frontend

**Files:**
- Create `web/strategy.html`
- Create `web/strategy.js`
- Modify `web/styles.css`
- Modify `web/index.html`
- Modify `web/analysis.html`

- [x] Create a standalone Strategy Lab page with game tabs, preset buttons, custom condition form, result panels, and saved strategy panel.
- [x] Implement frontend actions:
  - Generate candidates via `/api/strategy/{game}/generate`.
  - Backtest current strategy via `/api/strategy/{game}/backtest`.
  - Compare presets via `/api/strategy/{game}/compare`.
  - Save/load/delete local strategies via localStorage.
- [x] Add navigation links from home and analysis pages.
- [x] Add responsive CSS for desktop and mobile without nested cards.
- [x] Run `node --check web/strategy.js` and verify pass.

## Task 5: Verification

- [x] Run `PYTHONPATH=. .venv/bin/pytest -q`.
- [x] Run `node --check web/analysis.js` and `node --check web/strategy.js`.
- [x] Start the worktree app on a free port.
- [x] HTTP verify because the browser control channel was unavailable:
  - Strategy Lab loads.
  - Generate/backtest/compare APIs return valid payloads.
  - Four active games can generate strategy candidates.
  - Browser-only checks for localStorage, mobile overflow, and console errors remain manual follow-up while the browser control channel is unavailable.
- [x] Commit the feature branch with a concise message.
