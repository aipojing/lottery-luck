# 玄学命中钩子 V1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a stronger metaphysics hook to the homepage recommendation flow.

**Architecture:** Extend `PredictionEngine` with deterministic profile builders that derive a fortune hook, metaphysics profile, avoid numbers, and richer number reasons from existing personal and AI features. Render those fields in the existing homepage without adding a new page.

**Tech Stack:** Python, pytest, FastAPI, vanilla HTML/CSS/JS.

---

## File Map

- Modify `tests/test_predictor.py`: add failing tests for `fortune_hook`, `metaphysics_profile`, `avoid_numbers`, and structured `number_reasons`.
- Modify `tests/test_api.py`: assert `/api/predict` and the root shell expose the new hook fields/copy.
- Modify `lottery_luck/predictor.py`: add profile and hook helpers, include fields in prediction payload, enrich number reasons.
- Modify `web/index.html`: add the hook band and placeholders for profile and avoid numbers.
- Modify `web/app.js`: render hook, profile, avoid numbers, and richer reason lines.
- Modify `web/styles.css`: style the hook band, profile grid, avoid chips, and reason list.

## Tasks

- [x] Write failing predictor and API tests for the new hook payload.
- [x] Run focused tests and confirm failures are missing-field failures.
- [x] Implement backend profile, hook, avoid number, and reason builders.
- [x] Run focused predictor/API tests and confirm they pass.
- [x] Add homepage markup, renderer logic, and styling.
- [x] Run JS syntax checks, full pytest, and browser layout checks.
- [x] Commit and push the finished iteration.
