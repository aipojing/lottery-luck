# 分析中心 V2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deepen the standalone analysis center into a more professional lottery analysis workstation.

**Architecture:** Extend the existing `lottery_luck.analysis` module with reusable professional metrics and richer strategy helpers, then expose them through the existing API layer. Upgrade `web/analysis.html` and `web/analysis.js` in place so the current analysis page gains advanced filters, strategy comparison, richer pool diagnostics, and deeper visual summaries.

**Tech Stack:** FastAPI, Pydantic, Python stdlib, existing SQLite repository, vanilla HTML/CSS/JS.

---

## Task 1: Professional Metrics

**Files:**
- Modify: `tests/test_analysis.py`
- Modify: `lottery_luck/analysis.py`

- [x] Write failing tests for AC 值、质合比、尾数、012 路、区间比、邻号、遗漏分层.
- [x] Implement pure helper functions and add `professional` to `build_analysis_payload`.
- [x] Run `PYTHONPATH=. .venv/bin/pytest tests/test_analysis.py -q`.

## Task 2: Advanced Filtering And Backtest

**Files:**
- Modify: `tests/test_analysis.py`
- Modify: `tests/test_api.py`
- Modify: `lottery_luck/analysis.py`
- Modify: `lottery_luck/api.py`

- [x] Add failing tests for AC 范围、质合比、012 路、区间比、尾数排除、遗漏优先.
- [x] Add strategy comparison payload and API.
- [x] Run targeted API tests.

## Task 3: Frontend V2

**Files:**
- Modify: `web/analysis.html`
- Modify: `web/analysis.js`
- Modify: `web/styles.css`

- [x] Add advanced filter controls and strategy comparison UI.
- [x] Render professional metrics and pool risk score.
- [x] Add pool remove/clear/copy interactions.
- [x] Run `node --check web/analysis.js`.

## Task 4: Verification

- [x] Run `PYTHONPATH=. .venv/bin/pytest -q`.
- [x] Verify desktop and mobile analysis page in the browser.
- [x] Check browser console errors.
