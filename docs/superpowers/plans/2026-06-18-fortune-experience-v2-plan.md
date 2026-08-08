# 财运推荐体验 V2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Strengthen the lottery fortune recommendation product hook with deeper metaphysics reasoning, selectable recommendation modes, and local generation history.

**Architecture:** Extend the existing FastAPI `/api/predict` contract with a `fortune_mode` request field and deterministic mode/profile fields in `PredictionEngine`. Update the vanilla homepage to expose a segmented mode control, render a clearer reasoning chain, and save user-initiated results to browser localStorage.

**Tech Stack:** Python, FastAPI, pytest, vanilla HTML/CSS/JS, browser localStorage.

---

## File Map

- Modify `lottery_luck/predictor.py`: add mode profiles, mode-aware scoring, and a `credibility_chain`.
- Modify `lottery_luck/api.py`: accept `fortune_mode` and pass it through.
- Modify `tests/test_predictor.py`: cover mode payloads and deeper reasoning fields.
- Modify `tests/test_api.py`: cover API request compatibility and frontend shell assets.
- Modify `web/index.html`: add segmented mode control, credibility-chain mount, and history section.
- Modify `web/app.js`: send `fortune_mode`, render reasoning chain, persist and render history.
- Modify `web/styles.css`: style mode selector, reasoning chain, and history records.

## Tasks

- [x] Backend RED: tests for `fortune_mode`, `mode_profile`, and `credibility_chain`.
- [x] Backend GREEN: implement mode-aware prediction payload and API pass-through.
- [x] Commit backend slice.
- [x] Frontend RED: tests for mode selector and history UI shell.
- [x] Frontend GREEN: implement mode selector, reasoning chain rendering, localStorage history.
- [x] Browser verify homepage desktop/mobile interactions.
- [x] Full test/JS verification, commit, and push.
