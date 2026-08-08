# Task 4 Report: FastAPI Vercel Deployment Prep

## Status

Completed.

## Changes

- Added `api/index.py` as the Vercel ASGI entry and disabled static serving and auto-update by default for serverless imports.
- Added `vercel.json` with the cron route and function bundle exclusions.
- Added `.python-version` with `3.12`.
- Added `env_flag()` and `quota_enabled()` in config.
- Made prediction quota consumption, refund, and status payloads run only when `LOTTERY_LUCK_QUOTA_ENABLED` is true.
- Hid quota and cloud commercial endpoints from OpenAPI.
- Added optional CORS from comma-separated `ALLOWED_ORIGINS`.
- Added authenticated `GET /api/cron/crawl`; it returns 401 when `CRON_SECRET` is unset, missing, or mismatched, and only runs CWL then sports with `source="direct"` after exact Bearer auth.
- Moved `pytest` and `playwright` from `requirements.txt` to `requirements-dev.txt`.

## TDD Evidence

- RED: `test_prediction_ignores_requested_quota_when_disabled` failed because quota was still returned.
- RED: `test_commercial_routes_are_hidden_from_openapi` failed because commercial routes were still listed.
- RED: `test_cron_requires_bearer_secret_and_never_runs_without_it` failed because the cron route returned 404; it now covers unset, missing, and mismatched secrets without scheduler execution.
- RED: `test_authorized_cron_runs_cwl_then_direct_sports` failed because the cron route returned 404.
- RED: `test_allowed_origins_enable_cors_for_configured_origin` failed because CORS headers were absent.
- RED: `test_env_flag_parses_false_values_and_defaults` failed because `env_flag` did not exist.

## Verification

- `PYTHONPATH=. /Users/ahs/Documents/vibe-coding/codex/data/.venv/bin/pytest tests/test_api.py -k 'ignores_requested_quota or hidden_from_openapi or cron_requires' -v`
- `PYTHONPATH=. /Users/ahs/Documents/vibe-coding/codex/data/.venv/bin/pytest tests/test_api.py -k 'allowed_origins_enable_cors or authorized_cron_runs' -v`
- `PYTHONPATH=. /Users/ahs/Documents/vibe-coding/codex/data/.venv/bin/pytest tests/test_config.py -k env_flag -v`
- `PYTHONPATH=. /Users/ahs/Documents/vibe-coding/codex/data/.venv/bin/pytest tests/test_api.py tests/test_config.py tests/test_admin_auth.py tests/test_auto_update.py -q`

Final focused suite result: 176 passed, 1 warning.

## Concerns

- The parent repository venv is currently Python 3.14, while Vercel is pinned to Python 3.12 through `.python-version`.
- The only warning is the existing FastAPI/TestClient `httpx` deprecation warning.

## Follow-up Fix: Limit Production Crawl Games

### Changes

- Tightened the authorized cron test to prove production cron passes exactly `["ssq", "3d", "kl8"]` for CWL and `["dlt", "pl3"]` for sports even when the shared default helper would include hidden sports game `pl5`.
- Updated `/api/cron/crawl` to pass explicit production game lists instead of depending on default scheduler/task game collections.
- Added `.superpowers/**` to the Vercel function `excludeFiles` bundle exclusions.

### TDD Evidence

- RED: `PYTHONPATH=. ../../.venv/bin/pytest tests/test_api.py::test_authorized_cron_runs_cwl_then_direct_sports -q` failed because sports cron received `["dlt", "pl3", "pl5"]`.
- GREEN: the same focused cron test passed after the route used explicit production game lists.

### Verification

- `PYTHONPATH=. ../../.venv/bin/pytest tests/test_api.py::test_authorized_cron_runs_cwl_then_direct_sports -q`
- `PYTHONPATH=. ../../.venv/bin/pytest tests/test_api.py -k 'ignores_requested_quota or hidden_from_openapi or cron_requires or authorized_cron_runs or allowed_origins_enable_cors' -v`
- `PYTHONPATH=. ../../.venv/bin/pytest tests/test_api.py tests/test_config.py tests/test_admin_auth.py tests/test_auto_update.py -q`

Final regression result: 176 passed, 1 warning.

### Concerns

- The remaining warning is the existing FastAPI/TestClient `httpx` deprecation warning.
