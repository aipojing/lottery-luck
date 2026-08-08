# 复盘闭环与运营增强 V1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Finish the P1/P2 retention loop by adding one-click CWL crawl, draw review, AI interpretation layers, number-pool fortune commentary, analyst-friendly defaults, and stronger data-health monitoring.

**Architecture:** Add small backend units for CWL crawl orchestration and prediction review, extend existing prediction/analysis/data-health payloads, and wire the vanilla frontend to render the new sections. Keep user-generated history in browser localStorage and perform review through stateless API calls.

**Tech Stack:** Python, FastAPI, pytest, SQLite, vanilla HTML/CSS/JS, browser localStorage.

---

## File Map

- Create `lottery_luck/review.py`: stateless latest-draw hit review.
- Modify `lottery_luck/crawler.py`: expose reusable `crawl_cwl_games`.
- Modify `lottery_luck/api.py`: add CWL crawl and review endpoints; extend request models.
- Modify `lottery_luck/predictor.py`: return `interpretation_layers`.
- Modify `lottery_luck/analysis.py`: add number-pool fortune commentary.
- Modify `lottery_luck/data_health.py`: add failed-log summary and status tone metadata.
- Modify `web/index.html`, `web/app.js`, `web/styles.css`: render history review and AI layers.
- Modify `web/admin.html`, `web/admin.js`, `web/styles.css`: add one-click CWL crawl and stronger health status.
- Modify `web/analysis.html`, `web/analysis.js`, `web/styles.css`: add “彩民常看” summary.
- Modify tests in `tests/test_api.py`, `tests/test_predictor.py`, `tests/test_analysis.py`, `tests/test_data_health.py`.

## Tasks

- [x] Backend RED: tests for CWL crawl endpoint, review endpoint, interpretation layers, number-pool commentary, and data-health failure summary.
- [x] Backend GREEN: implement CWL crawl orchestration, review module/API, payload extensions, and data-health fields.
- [x] Commit backend slice.
- [x] Frontend RED: tests for homepage review UI, admin CWL controls, and analysis common-view shell.
- [x] Frontend GREEN: implement homepage review rendering, admin CWL button, common-view panel, and styles.
- [x] Browser verify homepage/admin/analysis desktop and mobile.
- [x] Full test/JS verification, commit, and push.
