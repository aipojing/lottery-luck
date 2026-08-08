from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from lottery_luck import scheduler
from lottery_luck.api import app, get_repository


client = TestClient(app)
ADMIN_TOKEN = "admin-secret"


class AdminRouteRepo:
    def recent_tasks(self, limit=20):
        return []

    def list_games(self):
        return []

    def recent_draw_dates_by_game(self, limit_per_game=500):
        return {}

    def recent_crawl_logs(self, limit=20):
        return []


ADMIN_ROUTES = [
    ("GET", "/api/admin/data-health?today=2026-06-17", None),
    ("GET", "/api/admin/settings", None),
    ("GET", "/api/admin/tasks", None),
    ("POST", "/api/admin/tasks/run", {"provider": "cwl", "games": ["ssq"], "page_size": 50}),
    ("POST", "/api/admin/crawl/sports", {"games": ["dlt"], "source": "direct"}),
    ("POST", "/api/admin/crawl/cwl", {"games": ["ssq"], "page_size": 50}),
]


def request_admin_route(method: str, path: str, body: dict | None, token: str | None = None):
    headers = {}
    if token is not None:
        headers["X-Lottery-Admin-Token"] = token
    if method == "POST":
        return client.post(path, json=body, headers=headers)
    return client.get(path, headers=headers)


@pytest.mark.parametrize(("method", "path", "body"), ADMIN_ROUTES)
@pytest.mark.parametrize(
    ("env_token", "supplied_token", "expected_status"),
    [
        (None, ADMIN_TOKEN, 401),
        (ADMIN_TOKEN, None, 401),
        (ADMIN_TOKEN, "wrong-token", 401),
        (f"  {ADMIN_TOKEN}  ", f"  {ADMIN_TOKEN}  ", 200),
    ],
)
def test_admin_routes_require_matching_token_per_request(
    monkeypatch,
    method,
    path,
    body,
    env_token,
    supplied_token,
    expected_status,
):
    if env_token is None:
        monkeypatch.delenv("LOTTERY_LUCK_ADMIN_TOKEN", raising=False)
    else:
        monkeypatch.setenv("LOTTERY_LUCK_ADMIN_TOKEN", env_token)

    def fake_run_once(**kwargs):
        return {
            "task": {
                "id": 123,
                "status": "success",
                "result": {
                    "provider": kwargs["provider"],
                    "status": "success",
                    "wrote_count": 0,
                    "failed_games": [],
                    "games": [],
                },
            }
        }

    monkeypatch.setattr(scheduler, "run_once", fake_run_once)
    app.dependency_overrides[get_repository] = lambda: AdminRouteRepo()
    try:
        response = request_admin_route(method, path, body, supplied_token)
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == expected_status
    if expected_status == 401:
        assert response.json() == {"detail": "admin authorization required"}
        assert response.headers["WWW-Authenticate"] == "LotteryAdmin"


def test_admin_token_is_read_from_environment_on_each_request(monkeypatch):
    monkeypatch.setenv("LOTTERY_LUCK_ADMIN_TOKEN", "first-token")
    first = client.get("/api/admin/settings", headers={"X-Lottery-Admin-Token": "first-token"})

    monkeypatch.setenv("LOTTERY_LUCK_ADMIN_TOKEN", "second-token")
    stale = client.get("/api/admin/settings", headers={"X-Lottery-Admin-Token": "first-token"})
    current = client.get("/api/admin/settings", headers={"X-Lottery-Admin-Token": "second-token"})

    assert first.status_code == 200
    assert stale.status_code == 401
    assert current.status_code == 200


@pytest.mark.parametrize("supplied_token", [None, "wrong-token"])
def test_admin_malformed_json_is_unauthorized_before_body_validation(
    monkeypatch,
    supplied_token,
):
    monkeypatch.setenv("LOTTERY_LUCK_ADMIN_TOKEN", ADMIN_TOKEN)
    headers = {"Content-Type": "application/json"}
    if supplied_token is not None:
        headers["X-Lottery-Admin-Token"] = supplied_token

    response = client.post(
        "/api/admin/tasks/run",
        headers=headers,
        content="{not-json",
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "admin authorization required"}
    assert response.headers["WWW-Authenticate"] == "LotteryAdmin"


def test_admin_malformed_json_with_correct_token_reaches_body_validation(monkeypatch):
    monkeypatch.setenv("LOTTERY_LUCK_ADMIN_TOKEN", ADMIN_TOKEN)

    response = client.post(
        "/api/admin/tasks/run",
        headers={
            "Content-Type": "application/json",
            "X-Lottery-Admin-Token": ADMIN_TOKEN,
        },
        content="{not-json",
    )

    assert response.status_code == 422


def test_admin_shell_starts_locked_and_never_prefills_token():
    response = client.get("/admin.html")

    assert response.status_code == 200
    assert 'id="adminAuthForm"' in response.text
    assert 'id="adminTokenInput"' in response.text
    assert 'type="password"' in response.text
    assert 'autocomplete="current-password"' in response.text
    assert 'for="adminTokenInput"' in response.text
    assert 'id="apiStatus"' in response.text
    assert 'id="adminAuthMessage"' in response.text
    assert 'role="status"' in response.text
    assert 'aria-live="polite"' in response.text
    assert "value=" not in response.text.partition('id="adminTokenInput"')[2].split(">", 1)[0]
    assert 'data-locked="true"' in response.text


def test_admin_frontend_uses_session_token_without_leaking_it():
    response = client.get("/admin.js")

    assert response.status_code == 200
    assert "sessionStorage" in response.text
    assert "localStorage" not in response.text
    assert "X-Lottery-Admin-Token" in response.text
    assert "Content-Type" in response.text
    assert "adminAuthForm" in response.text
    assert "adminTokenInput" in response.text
    assert "lockAdmin" in response.text
    assert "handleUnauthorized" in response.text
    assert ".searchParams" not in response.text
    assert "location.search" not in response.text
    assert "console.log" not in response.text


@pytest.mark.parametrize("path", ["/analysis.html", "/result.html", "/strategy.html"])
def test_public_pages_do_not_link_to_admin(path):
    response = client.get(path)

    assert response.status_code == 200
    assert 'href="./admin.html"' not in response.text
