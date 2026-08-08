# Next.js + Vercel + Turso Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将现有彩票工具迁移为可部署到 Vercel 的 Next.js Web + FastAPI API + Turso 架构，并从所有用户页面移除会员、次数包和收费逻辑。

**Architecture:** 保留 Python 预测、分析、抓取与测试体系，FastAPI 作为独立 Vercel Python 项目；新增 Next.js 项目承载现有已验收页面，并通过 Vercel rewrite 将同源 `/api/*` 代理到 FastAPI。数据库连接层在本地使用 `sqlite3`、生产使用 Turso `libsql`，个人起盘记录继续保存在浏览器 Local Storage。

**Tech Stack:** Python 3.12、FastAPI、Pydantic、SQLite/libSQL、Turso、Next.js 16、React 19、TypeScript、Vitest、pytest、Vercel Functions、Vercel Cron。

## Global Constraints

- 首页继续以“输入个人信息并起盘预测”为主要引流入口。
- 前端不得出现会员、次数包、剩余次数、解锁、购买或付费云记录入口。
- 后端历史商业化模块可以保留，但生产预测不得依赖额度状态或返回额度不足。
- `DEEPSEEK_API_KEY`、`TURSO_AUTH_TOKEN`、`LOTTERY_LUCK_ADMIN_TOKEN` 和 `CRON_SECRET` 只能存在于 FastAPI 服务端环境变量。
- Next.js 浏览器构建只能接触非秘密的同源 `/api/*` 地址。
- 本地测试继续支持 SQLite 临时数据库；生产数据库由 `TURSO_DATABASE_URL` 和 `TURSO_AUTH_TOKEN` 启用。
- Vercel Hobby Cron 每日只执行一次，统一在 UTC 15:00 调用一个幂等抓取入口。
- 浏览器抓取不得进入 Vercel 主执行路径；生产抓取只使用直接 HTTP 数据源。
- 第一阶段 Next.js 使用兼容壳承载现有静态页面，保持已经验收的视觉和交互；React 组件化不进入本计划。
- 不迁移模拟会员、模拟次数包或付费云记录数据。

---

### Task 1: Remove Frontend Monetization

**Files:**
- Modify: `tests/test_frontend_behavior.py`
- Modify: `web/index.html`
- Modify: `web/app.js`
- Modify: `web/motion.js`
- Modify: `web/admin.js`
- Modify: `web/styles.css`

**Interfaces:**
- Consumes: existing prediction form and `POST /api/predict` payload.
- Produces: a public prediction flow that always sends `consume_quota: false` and never calls quota or cloud-record APIs.

- [ ] **Step 1: Write failing commercial-removal tests**

Append focused assertions that read the real frontend files:

```python
def test_public_frontend_contains_no_membership_or_package_controls():
    html = (PROJECT_ROOT / "web" / "index.html").read_text(encoding="utf-8")
    app_js = (PROJECT_ROOT / "web" / "app.js").read_text(encoding="utf-8")
    admin_js = (PROJECT_ROOT / "web" / "admin.js").read_text(encoding="utf-8")

    for marker in (
        "quotaStatus",
        "unlockPanel",
        "mockMemberButton",
        "mockPackageButton",
        "/api/quota/status",
        "/api/quota/mock-unlock",
        "/api/cloud/fortune-records",
        "会员额度",
        "次数包",
    ):
        assert marker not in html + app_js + admin_js


def test_prediction_requests_never_consume_quota():
    app_js = (PROJECT_ROOT / "web" / "app.js").read_text(encoding="utf-8")

    assert "requestPayload.consume_quota = false" in app_js
    assert "Boolean(userInitiated)" not in app_js
```

- [ ] **Step 2: Run the focused tests and verify RED**

Run: `pytest tests/test_frontend_behavior.py -k 'membership_or_package or never_consume_quota' -v`

Expected: both new tests fail on `quotaStatus`, quota endpoints, and `Boolean(userInitiated)`.

- [ ] **Step 3: Remove commercial UI and requests**

Delete the quota badge and unlock panel from `web/index.html`. In `web/app.js`, remove quota state, quota element bindings, `quotaLabel`, `renderQuotaStatus`, unlock rendering, `loadQuotaStatus`, `mockUnlock`, cloud-record sync, quota-exhausted handling, and mock-unlock listeners. Preserve local history by making the storage state unconditional:

```javascript
const analyticsPayload = {
  ...existingPayload,
  storage_state: "local",
};

requestPayload.consume_quota = false;
```

Remove the “解锁后继续起盘” motion branch from `web/motion.js`. Remove `renderCommercialSettings` and its invocation from `web/admin.js`. Delete CSS selectors used only by `.quota-status` and `.unlock-panel`.

- [ ] **Step 4: Run frontend behavior and retention tests**

Run: `pytest tests/test_frontend_behavior.py tests/test_retention_flow.py -q`

Expected: all tests pass after obsolete monetization assertions are updated or removed; no assertion may be weakened for unrelated prediction, animation, 3D toolbox, analysis, strategy, or local-history behavior.

- [ ] **Step 5: Commit Task 1**

```bash
git add tests/test_frontend_behavior.py web/index.html web/app.js web/motion.js web/admin.js web/styles.css
git commit -m "feat: remove frontend monetization flow"
```

### Task 2: Add SQLite and Turso Connection Factory

**Files:**
- Create: `lottery_luck/database.py`
- Create: `tests/test_database.py`
- Modify: `lottery_luck/config.py`
- Modify: `lottery_luck/repository.py`
- Modify: `requirements.txt`
- Modify: `.env.example`

**Interfaces:**
- Produces: `connect_database(db_path: Path | str | None = None) -> ConnectionLike` and `remote_database_enabled() -> bool`.
- Consumes: `TURSO_DATABASE_URL`, `TURSO_AUTH_TOKEN`, and existing `DB_PATH`.

- [ ] **Step 1: Write failing connection-factory tests**

Create `tests/test_database.py` with local and injected-remote coverage:

```python
import sqlite3

import pytest

from lottery_luck import database


def test_connect_database_uses_explicit_sqlite_path(tmp_path, monkeypatch):
    monkeypatch.setenv("TURSO_DATABASE_URL", "libsql://ignored.turso.io")
    monkeypatch.setenv("TURSO_AUTH_TOKEN", "ignored-token")

    connection = database.connect_database(tmp_path / "local.sqlite")
    try:
        assert isinstance(connection, sqlite3.Connection)
        assert connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    finally:
        connection.close()


def test_connect_database_uses_libsql_for_implicit_production_connection(monkeypatch):
    calls = []

    class FakeConnection:
        row_factory = None

        def execute(self, sql):
            calls.append(("execute", sql))
            return self

        def close(self):
            return None

    class FakeLibsql:
        @staticmethod
        def connect(*, database, auth_token):
            calls.append((database, auth_token))
            return FakeConnection()

    monkeypatch.setenv("TURSO_DATABASE_URL", "libsql://lottery.turso.io")
    monkeypatch.setenv("TURSO_AUTH_TOKEN", "secret-token")
    monkeypatch.setattr(database, "_load_libsql", lambda: FakeLibsql)

    connection = database.connect_database()

    assert calls[0] == ("libsql://lottery.turso.io", "secret-token")
    assert connection.row_factory is sqlite3.Row


def test_remote_database_requires_token(monkeypatch):
    monkeypatch.setenv("TURSO_DATABASE_URL", "libsql://lottery.turso.io")
    monkeypatch.delenv("TURSO_AUTH_TOKEN", raising=False)

    with pytest.raises(RuntimeError, match="TURSO_AUTH_TOKEN"):
        database.connect_database()
```

- [ ] **Step 2: Run tests and verify RED**

Run: `pytest tests/test_database.py -v`

Expected: collection fails because `lottery_luck.database` does not exist.

- [ ] **Step 3: Implement the connection factory**

Implement `lottery_luck/database.py` with lazy driver loading so local tests do not require network access:

```python
from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from typing import Any

from .config import DB_PATH


def _load_libsql():
    import libsql
    return libsql


def remote_database_enabled() -> bool:
    return bool(os.environ.get("TURSO_DATABASE_URL", "").strip())


def connect_database(db_path: Path | str | None = None) -> Any:
    if db_path is not None or not remote_database_enabled():
        target = Path(db_path) if db_path is not None else DB_PATH
        if not target.exists():
            raise FileNotFoundError(target)
        connection = sqlite3.connect(target, timeout=10.0)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout = 10000")
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    url = os.environ["TURSO_DATABASE_URL"].strip()
    token = os.environ.get("TURSO_AUTH_TOKEN", "").strip()
    if not token:
        raise RuntimeError("TURSO_AUTH_TOKEN is required when TURSO_DATABASE_URL is set")
    connection = _load_libsql().connect(database=url, auth_token=token)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection
```

Change `LotteryRepository` so `LotteryRepository(path)` always uses the explicit local file while `LotteryRepository()` allows the environment-selected remote database:

```python
class LotteryRepository:
    def __init__(self, db_path: Path | str | None = None):
        self.db_path = Path(db_path) if db_path is not None else None

    def _connect(self):
        return connect_database(self.db_path)
```

Add `libsql>=0.1.11` to `requirements.txt`, and document empty `TURSO_DATABASE_URL` and `TURSO_AUTH_TOKEN` entries in `.env.example`.

- [ ] **Step 4: Run repository and database tests**

Run: `pytest tests/test_database.py tests/test_repository.py tests/test_plans.py tests/test_tasks.py -q`

Expected: all tests pass using local SQLite; remote-driver test passes using the injected fake.

- [ ] **Step 5: Commit Task 2**

```bash
git add lottery_luck/database.py lottery_luck/config.py lottery_luck/repository.py tests/test_database.py requirements.txt .env.example
git commit -m "feat: add Turso database connection factory"
```

### Task 3: Route Crawlers and Operational Writes Through the Database Factory

**Files:**
- Modify: `lottery_luck/crawler.py`
- Modify: `lottery_luck/sports_crawler.py`
- Modify: `lottery_luck/repository.py`
- Modify: `tests/test_crawler.py`
- Modify: `tests/test_sports_crawler.py`
- Modify: `tests/test_repository.py`

**Interfaces:**
- Consumes: `connect_database()` from Task 2.
- Produces: crawler functions that accept `connection_factory: Callable[[], ConnectionLike] | None` and default to the same production Turso connection as `LotteryRepository()`.

- [ ] **Step 1: Write failing remote-connection crawler tests**

Add one test per crawler that injects a connection factory and verifies no module-level `sqlite3.connect(DB_PATH)` call is required:

```python
def test_crawl_cwl_games_uses_injected_connection_factory(tmp_path, monkeypatch):
    db_path = tmp_path / "crawl.sqlite"
    initialize_draw_database(db_path)
    monkeypatch.setattr(crawler, "fetch_game_rows", lambda *args, **kwargs: [VALID_CWL_ROW])

    result = crawler.crawl_cwl_games(
        ["3d"],
        connection_factory=lambda: sqlite3.connect(db_path),
    )

    assert result["wrote_count"] == 1
```

Use the existing fixture/helper names from each test file rather than duplicating draw rows; the sports test must pass `source="direct"` so Playwright is never imported.

- [ ] **Step 2: Run the focused crawler tests and verify RED**

Run: `pytest tests/test_crawler.py tests/test_sports_crawler.py -k injected_connection_factory -v`

Expected: both fail because the crawler functions reject `connection_factory`.

- [ ] **Step 3: Replace direct production file opens**

Add an optional factory parameter to the production crawl entry points and use it in a context manager:

```python
factory = connection_factory or connect_database
with factory() as connection:
    ensure_draws_schema(connection)
    # Existing normalization, upsert, logging, and commit flow remains unchanged.
```

CLI-only commands that receive an explicit `--db-path` continue to call `connect_database(explicit_path)`. Repository methods remain the scheduler's preferred path. Do not change the direct HTTP fetch or normalization algorithms.

- [ ] **Step 4: Run crawler, scheduler, task, and health tests**

Run: `pytest tests/test_crawler.py tests/test_sports_crawler.py tests/test_tasks.py tests/test_data_health.py tests/test_auto_update.py -q`

Expected: all pass, and Playwright remains a local/manual fallback only.

- [ ] **Step 5: Commit Task 3**

```bash
git add lottery_luck/crawler.py lottery_luck/sports_crawler.py lottery_luck/repository.py tests/test_crawler.py tests/test_sports_crawler.py tests/test_repository.py
git commit -m "refactor: use shared database connections for crawlers"
```

### Task 4: Make FastAPI Vercel-Ready and Disable Quotas

**Files:**
- Create: `api/index.py`
- Create: `vercel.json`
- Create: `.python-version`
- Modify: `lottery_luck/api.py`
- Modify: `lottery_luck/config.py`
- Modify: `tests/test_api.py`
- Modify: `tests/test_config.py`
- Modify: `requirements.txt`

**Interfaces:**
- Produces: `GET /api/cron/crawl`, `quota_enabled() -> bool`, configurable CORS, and Vercel ASGI export `api.index:app`.
- Consumes: `CRON_SECRET`, `ALLOWED_ORIGINS`, `LOTTERY_LUCK_QUOTA_ENABLED`, and existing scheduler runners.

- [ ] **Step 1: Write failing API policy tests**

Add tests for quota-off prediction, hidden commercial routes, CORS, and cron authorization:

```python
def test_prediction_ignores_requested_quota_when_disabled(client, monkeypatch):
    monkeypatch.setenv("LOTTERY_LUCK_QUOTA_ENABLED", "false")
    response = client.post("/api/predict", json={**VALID_PREDICT_REQUEST, "consume_quota": True})
    assert response.status_code == 200
    assert "quota" not in response.json()


def test_commercial_routes_are_hidden_from_openapi(client):
    paths = client.get("/openapi.json").json()["paths"]
    assert "/api/quota/status" not in paths
    assert "/api/quota/mock-unlock" not in paths
    assert "/api/cloud/fortune-records" not in paths


def test_cron_requires_bearer_secret(client, monkeypatch):
    monkeypatch.setenv("CRON_SECRET", "cron-secret-123456")
    assert client.get("/api/cron/crawl").status_code == 401
```

The authorized cron test must monkeypatch both scheduler calls and assert providers are invoked as `cwl` then `sports`, with sports `source="direct"`.

- [ ] **Step 2: Run focused tests and verify RED**

Run: `pytest tests/test_api.py -k 'ignores_requested_quota or hidden_from_openapi or cron_requires' -v`

Expected: quota appears in the response, commercial routes appear in OpenAPI, and the cron route returns 404.

- [ ] **Step 3: Implement runtime flags, CORS, cron, and serverless entry**

Add reusable boolean parsing in `lottery_luck/config.py`:

```python
FALSE_ENV_VALUES = {"0", "false", "no", "off", "disabled"}


def env_flag(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() not in FALSE_ENV_VALUES
```

In `lottery_luck/api.py`:

- Add `CORSMiddleware` only when `ALLOWED_ORIGINS` contains one or more comma-separated origins.
- Add `include_in_schema=False` to quota and cloud-record decorators.
- Only execute quota consumption/refund/status branches when `env_flag("LOTTERY_LUCK_QUOTA_ENABLED", False)` is true.
- Only mount `web/` when `env_flag("LOTTERY_LUCK_SERVE_STATIC", True)` is true.
- Add `GET /api/cron/crawl`, compare `Authorization` exactly with `Bearer ${CRON_SECRET}`, run CWL and sports direct-source jobs, and return `{ "ok": true, "results": [...] }`.

Create `api/index.py`:

```python
import os

os.environ.setdefault("LOTTERY_LUCK_SERVE_STATIC", "false")
os.environ.setdefault("LOTTERY_LUCK_AUTO_UPDATE_ENABLED", "false")

from lottery_luck.api import app

__all__ = ["app"]
```

Create `.python-version` with the exact content `3.12`. Vercel must use Python 3.12 because `libsql==0.1.11` publishes a compatible manylinux CPython 3.12 wheel, while Python 3.14 currently falls back to a native source build.

Create `vercel.json`:

```json
{
  "$schema": "https://openapi.vercel.sh/vercel.json",
  "functions": {
    "api/index.py": {
      "maxDuration": 300,
      "excludeFiles": "{tests/**,web/**,frontend/**,.worktrees/**,cwl_history/**}"
    }
  },
  "crons": [
    {
      "path": "/api/cron/crawl",
      "schedule": "0 15 * * *"
    }
  ]
}
```

Remove `pytest` and `playwright` from production `requirements.txt`; create `requirements-dev.txt` containing `-r requirements.txt`, `pytest>=8.2.0`, and `playwright>=1.45.0` so the Vercel function bundle does not include test tooling or browser binaries.

- [ ] **Step 4: Run API and configuration tests**

Run: `pytest tests/test_api.py tests/test_config.py tests/test_admin_auth.py tests/test_auto_update.py -q`

Expected: all pass; cron tests prove unauthorized requests do not invoke a crawler and duplicate scheduler execution remains idempotent through existing issue constraints.

- [ ] **Step 5: Commit Task 4**

```bash
git add api/index.py vercel.json .python-version lottery_luck/api.py lottery_luck/config.py tests/test_api.py tests/test_config.py requirements.txt requirements-dev.txt
git commit -m "feat: prepare FastAPI for Vercel deployment"
```

### Task 5: Add the Next.js Compatibility Web Project

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/package-lock.json`
- Create: `frontend/tsconfig.json`
- Create: `frontend/next-env.d.ts`
- Create: `frontend/next.config.mjs`
- Create: `frontend/app/layout.tsx`
- Create: `frontend/app/page.tsx`
- Create: `frontend/app/globals.css`
- Create: `frontend/scripts/sync-legacy.mjs`
- Create: `frontend/tests/routes.test.ts`
- Create generated copies: `frontend/public/**` from `web/**`
- Modify: `.gitignore`

**Interfaces:**
- Consumes: canonical static frontend files under `web/` and `API_BASE_URL`.
- Produces: a Next.js deployment whose user routes preserve the existing page HTML, CSS, assets, scripts, query strings, and same-origin API calls.

- [ ] **Step 1: Create the Next.js test harness and failing route tests**

Use `next@16`, `react@19`, `react-dom@19`, TypeScript, and Vitest. `frontend/tests/routes.test.ts` must import the Next config and assert these exact rewrite destinations:

```typescript
import { describe, expect, it } from "vitest";
import nextConfig from "../next.config.mjs";

describe("legacy compatibility routes", () => {
  it("keeps product URLs stable", async () => {
    const rewrites = await nextConfig.rewrites();
    expect(rewrites.beforeFiles).toEqual(
      expect.arrayContaining([
        { source: "/", destination: "/index.html" },
        { source: "/analysis", destination: "/analysis.html" },
        { source: "/strategy", destination: "/strategy.html" },
        { source: "/admin", destination: "/admin.html" },
      ]),
    );
  });

  it("proxies API calls to the configured FastAPI origin", async () => {
    process.env.API_BASE_URL = "https://api.example.test";
    const rewrites = await nextConfig.rewrites();
    expect(rewrites.beforeFiles).toContainEqual({
      source: "/api/:path*",
      destination: "https://api.example.test/api/:path*",
    });
  });
});
```

- [ ] **Step 2: Run tests and verify RED**

Run: `cd frontend && npm test -- --run`

Expected: fail because `next.config.mjs` and the package do not exist.

- [ ] **Step 3: Scaffold the compatibility project**

Implement `next.config.mjs` with `output: "standalone"`, extensionless page rewrites, and an API proxy. Resolve `API_BASE_URL` inside `rewrites()` so tests can change the environment after module import:

```javascript
const nextConfig = {
  output: "standalone",
  async rewrites() {
    const apiBaseUrl = (process.env.API_BASE_URL || "http://127.0.0.1:8017").replace(/\/$/, "");
    return {
      beforeFiles: [
        { source: "/api/:path*", destination: `${apiBaseUrl}/api/:path*` },
        { source: "/", destination: "/index.html" },
        { source: "/analysis", destination: "/analysis.html" },
        { source: "/strategy", destination: "/strategy.html" },
        { source: "/admin", destination: "/admin.html" },
        { source: "/privacy", destination: "/privacy.html" }
      ]
    };
  }
};

export default nextConfig;
```

The sync script must copy only files tracked under `web/` into `frontend/public/`, remove stale generated files, and reject any symbolic link whose resolved path leaves `web/`. Run it once and commit the generated files. The canonical source remains `web/`; every later frontend change must run `npm run sync:legacy`.

`app/page.tsx` is a non-commercial fallback page used only if rewrites are disabled; it must link to `/index.html` and contain no feature explanation or marketing hero.

- [ ] **Step 4: Install, sync, test, and build**

Run:

```bash
cd frontend
npm install
npm run sync:legacy
npm test -- --run
npm run build
```

Expected: Vitest passes and Next.js production build completes without TypeScript, route, or static-asset errors.

- [ ] **Step 5: Commit Task 5**

```bash
git add frontend .gitignore
git commit -m "feat: add Next.js web deployment"
```

### Task 6: Add Turso Migration and Deployment Verification

**Files:**
- Create: `scripts/check_turso_source.py`
- Create: `scripts/verify_remote_database.py`
- Create: `tests/test_turso_migration_scripts.py`
- Modify: `README.md`
- Modify: `docs/OPERATIONS.md`
- Modify: `docs/ARCHITECTURE.md`
- Modify: `docs/COMMERCIALIZATION.md`

**Interfaces:**
- Consumes: local `cwl_history/cwl_history.sqlite`, Turso credentials, Vercel Web/API project settings.
- Produces: repeatable preflight and post-import checks with nonzero exit codes on data mismatch.

- [ ] **Step 1: Write failing script tests**

Create tests for a valid source database and for count/latest-issue mismatch:

```python
def test_source_check_reports_required_pragmas_and_draw_count(tmp_path):
    db_path = create_sample_database(tmp_path)
    result = check_source_database(db_path)
    assert result["page_size"] == 4096
    assert result["encoding"] == "UTF-8"
    assert result["draw_count"] == 2


def test_compare_snapshots_rejects_latest_issue_mismatch():
    with pytest.raises(ValueError, match="latest issue mismatch"):
        compare_snapshots(
            {"3d": {"count": 10, "latest_issue": "2026200"}},
            {"3d": {"count": 10, "latest_issue": "2026199"}},
        )
```

- [ ] **Step 2: Run tests and verify RED**

Run: `pytest tests/test_turso_migration_scripts.py -v`

Expected: fail because both script modules are absent.

- [ ] **Step 3: Implement deterministic migration checks and docs**

`check_turso_source.py` must report file size, `PRAGMA integrity_check`, page size, encoding, auto-vacuum, total draw count, per-game count, and latest issue. It must exit nonzero unless integrity is `ok`, page size is 4096, encoding is UTF-8, and auto-vacuum is 0.

`verify_remote_database.py` must use `connect_database()`, read the same snapshot shape, accept `--source-snapshot path.json`, and call a pure `compare_snapshots(source, remote)` function. Counts and latest issue must match for `ssq`, `dlt`, `3d`, `pl3`, and `kl8`.

Document this exact import sequence:

```bash
python scripts/check_turso_source.py cwl_history/cwl_history.sqlite --output artifacts/turso-source.json
sqlite3 cwl_history/cwl_history.sqlite "PRAGMA journal_mode=WAL; PRAGMA wal_checkpoint(TRUNCATE);"
turso db create lottery-luck --from-file cwl_history/cwl_history.sqlite
turso db show lottery-luck --url
turso db tokens create lottery-luck
TURSO_DATABASE_URL='libsql://...' TURSO_AUTH_TOKEN='...' \
  python scripts/verify_remote_database.py --source-snapshot artifacts/turso-source.json
```

README and operations docs must specify two Vercel projects:

- API root: repository root; variables `TURSO_DATABASE_URL`, `TURSO_AUTH_TOKEN`, `DEEPSEEK_API_KEY`, `DEEPSEEK_MODEL`, `LOTTERY_LUCK_ADMIN_TOKEN`, `CRON_SECRET`, `ALLOWED_ORIGINS`, `LOTTERY_LUCK_QUOTA_ENABLED=false`.
- Web root: `frontend`; variable `API_BASE_URL=https://<api-project>.vercel.app`.

Replace commercialization documentation with a historical note stating the code is dormant and no production page exposes payment or quota behavior.

- [ ] **Step 4: Run migration-script and documentation checks**

Run:

```bash
pytest tests/test_turso_migration_scripts.py tests/test_config.py -q
python scripts/check_turso_source.py cwl_history/cwl_history.sqlite --output /tmp/turso-source.json
```

Expected: tests pass; source check reports integrity `ok`, approximately 51MB, and a positive count for all five public games.

- [ ] **Step 5: Commit Task 6**

```bash
git add scripts/check_turso_source.py scripts/verify_remote_database.py tests/test_turso_migration_scripts.py README.md docs/OPERATIONS.md docs/ARCHITECTURE.md docs/COMMERCIALIZATION.md
git commit -m "docs: add Turso and Vercel deployment runbook"
```

### Task 7: Full Regression and Browser Acceptance

**Files:**
- Modify only when verification exposes a regression in files already owned by Tasks 1-6.
- Create verification artifacts under `artifacts/` without committing screenshots unless the repository already tracks the matching artifact class.

**Interfaces:**
- Consumes: complete API and Web migration.
- Produces: fresh test, build, browser, and secret-leak evidence.

- [ ] **Step 1: Run the complete Python suite**

Run: `pytest -q`

Expected: all tests pass. The previously documented unrelated failure must be reproduced and explicitly identified if it still exists; no new failure is accepted.

- [ ] **Step 2: Run frontend tests and production build**

Run: `cd frontend && npm test -- --run && npm run build`

Expected: Vitest and Next.js build pass.

- [ ] **Step 3: Scan browser artifacts for secrets and commercial copy**

Run:

```bash
rg -n "DEEPSEEK_API_KEY|TURSO_AUTH_TOKEN|LOTTERY_LUCK_ADMIN_TOKEN|CRON_SECRET|会员|次数包|模拟购买|解锁今日财运号" frontend/.next frontend/public web
```

Expected: no secret variable names or commercial copy in `frontend/.next/static`, `frontend/public`, or `web`; server-side build manifests may contain only the non-secret variable name `API_BASE_URL`.

- [ ] **Step 4: Start both local servers**

Run API: `uvicorn lottery_luck.api:app --host 127.0.0.1 --port 8017`

Run Web in a second session: `cd frontend && API_BASE_URL=http://127.0.0.1:8017 npm run dev -- --hostname 127.0.0.1 --port 3000`

Expected: `GET http://127.0.0.1:3000/api/health` returns 200 through the Next.js proxy.

- [ ] **Step 5: Verify desktop and mobile workflows with Playwright**

At 1440x1000 and 390x844:

- Open `/`, submit a valid birth form, and confirm a prediction result appears without quota UI.
- Open `/analysis.html?game=3d&mode=simple&window=30` and confirm the simple toolbox renders nonblank.
- Switch to advanced mode and confirm tools remain usable without overlapping controls.
- Open `/strategy.html`, `/result.html`, and `/admin.html`; confirm navigation and API requests resolve.
- Check console errors, failed requests, horizontal overflow, and text overlap.

Expected: no uncaught exception, failed first-party request, commercial UI, or incoherent overlap.

- [ ] **Step 6: Commit verification fixes**

```bash
git add <only-files-changed-to-fix-verification>
git commit -m "fix: resolve migration acceptance regressions"
```

Skip this commit only when verification required no source change.

- [ ] **Step 7: Record release evidence**

Append the exact test counts, build result, checked viewport sizes, local URLs, and any external provisioning still requiring the user's Vercel/Turso account to `docs/OPERATIONS.md`, then commit:

```bash
git add docs/OPERATIONS.md
git commit -m "docs: record migration verification"
```
