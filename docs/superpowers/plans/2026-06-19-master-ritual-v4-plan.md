# Master Ritual V4 Implementation Plan

> **For Worker Agents:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan step-by-step.

## Goal

把首页预测体验升级成“玄学起盘可信度 V4”：后端输出可解释起盘链路，首页渲染大师起盘闭环，点击动作和历史记录都围绕“起盘”表达。

## Architecture

- Backend: `lottery_luck/predictor.py`
  - Add `_master_ritual(...)`.
  - Include `master_ritual` in `PredictionEngine.predict`.
  - Reuse existing metaphysics profile, daily sign, avoid numbers, number reasons and formatted number path.
- Frontend: `web/index.html`, `web/app.js`, `web/styles.css`
  - Add `#masterRitual` section.
  - Add payload normalization and `renderMasterRitual`.
  - Update button/status copy from generate-style to ritual-style.
  - Persist `master_ritual` in local history records.
- Tests:
  - `tests/test_predictor.py`
  - `tests/test_api.py`
  - `tests/test_frontend_behavior.py`

## Steps

1. Backend red test
   - Add a predictor test expecting `master_ritual` with labels:
     `定命盘`, `排本命财格`, `定今日财局`, `取喜用尾数`, `避冲煞号`, `落财运号`.
   - Assert verdict includes the wealth pattern and final number path.

2. Frontend red tests
   - Update static HTML/JS tests to expect `开始起盘`, `masterRitual`, `renderMasterRitual`.
   - Add browser behavior assertion that the rendered page shows the master ritual verdict and step labels.

3. Backend implementation
   - Build `_master_ritual` from personal input, profile, mode profile, daily sign, avoid numbers and selected numbers.
   - Add helper to format tail maps by element.
   - Include the new object in prediction payload.

4. Frontend implementation
   - Add markup for the master ritual panel.
   - Add `els.masterRitual`, `normalizeMasterRitual`, `renderMasterRitual`.
   - Render after fortune hook and before credibility chain.
   - Save `master_ritual` into history records.
   - Update ritual copy and button text.

5. Styling
   - Add compact black/gold panel styles for verdict, steps and tail map.
   - Keep responsive layout readable on mobile.

6. Verification
   - Run targeted red/green tests.
   - Run `pytest -q`.
   - Run JS syntax checks.
   - Smoke test `http://127.0.0.1:8017/` in browser.
   - Commit and push, leaving runtime SQLite unstaged.
