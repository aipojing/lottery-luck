# 玄学推荐引擎 V2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reframe the home prediction flow into a metaphysics-led fortune recommendation flow.

**Architecture:** Keep the existing FastAPI and frontend structure. Modify `PredictionEngine` to use metaphysics-led scoring and return recommendation explanations, then update the homepage to render those fields while preserving legacy response fields.

**Tech Stack:** Python, FastAPI, pytest, vanilla HTML/CSS/JS.

---

## File Map

- Modify `tests/test_predictor.py`: add red tests for `recommendation_basis`, `number_reasons`, `ritual_summary`, and disclaimer wording.
- Modify `tests/test_api.py`: assert homepage copy and `/api/predict` payload reflect recommendation positioning.
- Modify `lottery_luck/predictor.py`: change combined scoring weights and add deterministic reason builders.
- Modify `web/index.html`: adjust homepage copy and add a number-reason section.
- Modify `web/app.js`: render `recommendation_basis`, `ritual_summary`, and `number_reasons`.
- Modify `web/styles.css`: style the new reason section.

## Tasks

- [x] Write failing predictor tests for metaphysics-led output.
- [x] Implement predictor fields and scoring weights.
- [x] Run focused predictor tests and confirm pass.
- [x] Write failing API/frontend shell tests for recommendation copy.
- [x] Update homepage HTML/JS/CSS copy and rendering.
- [x] Run focused API tests and JS syntax checks.
- [x] Run full pytest, HTTP smoke, commit, and push.
