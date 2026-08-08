# 数据健康与爬虫中台 V1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a local admin workbench that shows lottery data health, crawler logs, and lets the user manually run official sports-lottery crawling.

**Architecture:** Add a focused backend module for data health and crawl-log persistence, expose admin API endpoints from FastAPI, and add an independent `admin.html` page that consumes those APIs. Reuse existing repository, rules, crawlers, and black-gold frontend patterns.

**Tech Stack:** FastAPI, SQLite, httpx, Playwright-backed sports crawler, vanilla HTML/CSS/JS, pytest.

---

## File Map

- Create `lottery_luck/data_health.py`: pure health-report and crawl-log helpers.
- Modify `lottery_luck/repository.py`: add efficient draw summary and recent draw date helpers.
- Modify `lottery_luck/sports_crawler.py`: expose a reusable crawl function that records logs.
- Modify `lottery_luck/api.py`: add `/api/admin/data-health` and `/api/admin/crawl/sports`.
- Create `web/admin.html` and `web/admin.js`: standalone data backend page.
- Modify `web/index.html`, `web/analysis.html`, `web/strategy.html`: add admin navigation link.
- Modify `web/styles.css`: compact admin table and status styles.
- Add tests in `tests/test_data_health.py`, update `tests/test_api.py`, `tests/test_sports_crawler.py`.

## Task 1: Data Health Core

- [x] Add tests for `build_data_health_report()` with healthy, attention, and empty games.
- [x] Implement `lottery_luck/data_health.py`.
- [x] Add repository helper methods for per-game draw summaries and recent draw dates.
- [x] Run `PYTHONPATH=. .venv/bin/pytest tests/test_data_health.py tests/test_repository.py -q`.

## Task 2: Crawl Logs And Reusable Sports Crawl

- [x] Add tests for creating, writing, and reading `crawl_logs`.
- [x] Refactor `sports_crawler` into reusable `crawl_sports_games()` while keeping CLI behavior.
- [x] Record one log row per game run with status, write count, error, and duration.
- [x] Run `PYTHONPATH=. .venv/bin/pytest tests/test_sports_crawler.py -q`.

## Task 3: Admin APIs

- [x] Add `GET /api/admin/data-health`.
- [x] Add `POST /api/admin/crawl/sports`.
- [x] Add API tests for both endpoints with dependency overrides and mocked crawler.
- [x] Run `PYTHONPATH=. .venv/bin/pytest tests/test_api.py -q`.

## Task 4: Admin Frontend

- [x] Create `web/admin.html`.
- [x] Create `web/admin.js` with health loading, sports crawl form, and log rendering.
- [x] Add navigation links to existing pages.
- [x] Add CSS for dashboard KPIs, health table, crawl panel, and logs.
- [x] Run `node --check web/admin.js web/app.js web/analysis.js web/strategy.js`.

## Task 5: Verification And Push

- [x] Run `PYTHONPATH=. .venv/bin/pytest -q`.
- [x] Run JS syntax checks.
- [x] HTTP smoke `/api/admin/data-health` and `/admin.html`.
- [ ] Commit and push to `main`.
