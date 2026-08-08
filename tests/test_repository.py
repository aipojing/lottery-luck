import threading

import pytest

from lottery_luck import plans as plan_store
from lottery_luck.repository import (
    LotteryRepository,
    PlanDrawUnavailableError,
    PlanNotFoundError,
    PlanRequestConflictError,
    PlanTargetAlreadyDrawnError,
)
from lottery_luck.config import DB_PATH
from lottery_luck.data_health import ensure_crawl_logs_table, record_crawl_log

import sqlite3


def test_list_games_reads_sqlite_metadata():
    repo = LotteryRepository()
    games = repo.list_games()
    keys = {game["game_key"] for game in games}
    assert {"ssq", "3d", "qlc", "kl8", "dlt", "pl3", "pl5"} <= keys
    assert all(game["provider"] in {"cwl", "sports"} for game in games)
    assert all(game["game_name"] for game in games)
    assert all(game["latest_issue"] for game in games if game["draw_count"] > 0)
    assert all(
        game["draw_count"] > 0 and game["earliest_date"] and game["latest_date"]
        for game in games
        if game["provider"] == "cwl"
    )


def test_recent_draws_are_descending_for_ssq():
    repo = LotteryRepository()
    draws = repo.recent_draws("ssq", limit=3)
    assert len(draws) == 3
    assert draws[0]["draw_date"] >= draws[1]["draw_date"] >= draws[2]["draw_date"]


def test_all_draws_for_ssq_returns_many_rows_and_descending():
    repo = LotteryRepository()
    draws = repo.all_draws("ssq")
    assert len(draws) > 3
    assert all(
        draws[i]["draw_date"] >= draws[i + 1]["draw_date"]
        for i in range(len(draws) - 1)
    )


def test_repository_accepts_string_db_path():
    repo = LotteryRepository(str(DB_PATH))
    assert repo.recent_draws("ssq", limit=1)


def test_repository_uses_injected_connection_factory(tmp_path, monkeypatch):
    db_path = tmp_path / "repository.sqlite"
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            """
            CREATE TABLE draws (
                game_key TEXT,
                game_name TEXT,
                issue TEXT,
                draw_date TEXT,
                week TEXT,
                red_numbers TEXT,
                blue_number TEXT,
                sales TEXT,
                pool_money TEXT,
                content TEXT,
                PRIMARY KEY (game_key, issue)
            )
            """
        )
        connection.execute(
            """
            INSERT INTO draws (
                game_key, game_name, issue, draw_date, week, red_numbers,
                blue_number, sales, pool_money, content
            )
            VALUES ('ssq', '双色球', '2026070', '2026-06-16', '二',
                    '01,02,03,04,05,06', '07', '', '', '')
            """
        )

    original_connect = sqlite3.connect
    calls = []

    def connection_factory():
        calls.append(True)
        connection = original_connect(db_path)
        connection.row_factory = sqlite3.Row
        return connection

    monkeypatch.setattr(
        "lottery_luck.repository.connect_database",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("repository should use the injected connection factory")
        ),
    )

    repo = LotteryRepository(connection_factory=connection_factory)

    assert repo.recent_draws("ssq", limit=1)[0]["issue"] == "2026070"
    assert calls


def test_recent_draw_dates_by_game_returns_limited_descending_dates():
    repo = LotteryRepository()
    dates = repo.recent_draw_dates_by_game(limit_per_game=3)

    assert "ssq" in dates
    assert len(dates["ssq"]) == 3
    assert dates["ssq"] == sorted(dates["ssq"], reverse=True)


def test_recent_crawl_logs_reads_log_table(tmp_path):
    db_path = tmp_path / "history.sqlite"
    connection = sqlite3.connect(db_path)
    connection.execute(
        """
        CREATE TABLE draws (
            game_key TEXT,
            issue TEXT,
            draw_date TEXT,
            PRIMARY KEY (game_key, issue)
        )
        """
    )
    ensure_crawl_logs_table(connection)
    record_crawl_log(
        connection,
        provider="sports",
        game_key="dlt",
        source="browser",
        page_size=100,
        pages=3,
        wrote_count=300,
        status="success",
        error="",
        started_at="2026-06-17T08:00:00+00:00",
        finished_at="2026-06-17T08:00:03+00:00",
        duration_ms=3000,
    )
    connection.commit()
    connection.close()

    logs = LotteryRepository(db_path).recent_crawl_logs(limit=5)

    assert len(logs) == 1
    assert logs[0]["game_key"] == "dlt"
    assert logs[0]["wrote_count"] == 300


def test_recent_crawl_logs_by_game_returns_latest_logs_per_requested_game(tmp_path):
    db_path = tmp_path / "history.sqlite"
    connection = sqlite3.connect(db_path)
    ensure_crawl_logs_table(connection)
    record_crawl_log(
        connection,
        provider="sports",
        game_key="dlt",
        source="browser",
        page_size=100,
        pages=1,
        wrote_count=1,
        status="success",
        error="",
        started_at="2026-07-12T00:00:00+00:00",
        finished_at="2026-07-12T00:00:01+00:00",
        duration_ms=1000,
    )
    for index in range(25):
        finished_at = (
            f"2026-07-12T{index:02d}:00:01+00:00"
            if index < 24
            else "2026-07-13T00:00:01+00:00"
        )
        record_crawl_log(
            connection,
            provider="cwl",
            game_key="ssq",
            source="api",
            page_size=100,
            pages=1,
            wrote_count=1,
            status="success",
            error="",
            started_at=finished_at,
            finished_at=finished_at,
            duration_ms=1000,
        )
    connection.commit()
    connection.close()

    logs = LotteryRepository(db_path).recent_crawl_logs_by_game(
        ["ssq", "dlt"],
        limit_per_game=1,
    )

    logs_by_game = {log["game_key"]: log for log in logs}
    assert set(logs_by_game) == {"ssq", "dlt"}
    assert logs_by_game["ssq"]["finished_at"] == "2026-07-13T00:00:01+00:00"
    assert logs_by_game["dlt"]["finished_at"] == "2026-07-12T00:00:01+00:00"


def test_recent_crawl_logs_by_game_orders_by_chronological_finished_at(tmp_path):
    db_path = tmp_path / "history.sqlite"
    connection = sqlite3.connect(db_path)
    ensure_crawl_logs_table(connection)
    record_crawl_log(
        connection,
        provider="cwl",
        game_key="ssq",
        source="api",
        page_size=100,
        pages=1,
        wrote_count=1,
        status="failed",
        error="earlier absolute time",
        started_at="2026-07-12T05:30:00+08:00",
        finished_at="2026-07-12T05:30:00+08:00",
        duration_ms=1000,
    )
    record_crawl_log(
        connection,
        provider="cwl",
        game_key="ssq",
        source="api",
        page_size=100,
        pages=1,
        wrote_count=1,
        status="success",
        error="",
        started_at="2026-07-12T00:00:00+00:00",
        finished_at="2026-07-12T00:00:00+00:00",
        duration_ms=1000,
    )
    record_crawl_log(
        connection,
        provider="sports",
        game_key="dlt",
        source="browser",
        page_size=100,
        pages=1,
        wrote_count=1,
        status="failed",
        error="malformed timestamp",
        started_at="not a timestamp",
        finished_at="not a timestamp",
        duration_ms=1000,
    )
    record_crawl_log(
        connection,
        provider="sports",
        game_key="dlt",
        source="browser",
        page_size=100,
        pages=1,
        wrote_count=1,
        status="success",
        error="",
        started_at="2026-07-12T00:00:00+00:00",
        finished_at="2026-07-12T00:00:00+00:00",
        duration_ms=1000,
    )
    connection.commit()
    connection.close()

    logs = LotteryRepository(db_path).recent_crawl_logs_by_game(
        ["ssq", "dlt"],
        limit_per_game=1,
    )

    logs_by_game = {log["game_key"]: log for log in logs}
    assert logs_by_game["ssq"]["finished_at"] == "2026-07-12T00:00:00+00:00"
    assert logs_by_game["dlt"]["finished_at"] == "2026-07-12T00:00:00+00:00"


def _plan_repo(tmp_path):
    db_path = tmp_path / "plans.sqlite"
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            """
            CREATE TABLE draws (
              game_key TEXT,
              game_name TEXT,
              issue TEXT,
              draw_date TEXT,
              week TEXT,
              red_numbers TEXT,
              blue_number TEXT,
              sales TEXT,
              pool_money TEXT,
              content TEXT,
              PRIMARY KEY(game_key, issue)
            )
            """
        )
    repo = LotteryRepository(db_path)
    repo.initialize_plan_schema()
    return repo


def _plan_payload(**overrides):
    payload = {
        "game_key": "3d",
        "target_issue": "2026156",
        "target_draw_date": "2026-06-16",
        "source_type": "manual",
        "request_id": "repo-plan",
        "title": "repo plan",
        "entries": [{"main_numbers": [1, 2, 3], "special_numbers": []}],
        "condition_snapshot": {
            "mode": "simple",
            "analysis_window": 30,
            "conditions_json": {},
            "metrics_json": {},
            "latest_data_issue": "2026155",
            "latest_data_date": "2026-06-15",
        },
    }
    payload.update(overrides)
    return payload


def _insert_3d_draw(repo, *, issue, draw_date, red_numbers="1,2,3"):
    with sqlite3.connect(repo.db_path) as connection:
        connection.execute(
            """
            INSERT INTO draws (
                game_key, game_name, issue, draw_date, week, red_numbers,
                blue_number, sales, pool_money, content
            )
            VALUES ('3d', 'FC3D', ?, ?, '', ?, '', '', '', '')
            """,
            (issue, draw_date, red_numbers),
        )


def _delete_3d_draw(repo, *, issue):
    with sqlite3.connect(repo.db_path) as connection:
        connection.execute(
            "DELETE FROM draws WHERE game_key = '3d' AND issue = ?",
            (issue,),
        )


def _plan_review_count(repo, plan_id):
    with sqlite3.connect(repo.db_path) as connection:
        row = connection.execute(
            "SELECT COUNT(*) FROM plan_reviews WHERE plan_id = ?",
            (plan_id,),
        ).fetchone()
    return int(row[0])


def test_create_plan_lifecycle_rejects_request_id_payload_conflicts(tmp_path):
    repo = _plan_repo(tmp_path)
    first = repo.create_plan_lifecycle("client-a", _plan_payload(request_id="same"))
    retry = repo.create_plan_lifecycle("client-a", _plan_payload(request_id="same"))
    other_client = repo.create_plan_lifecycle("client-b", _plan_payload(request_id="same"))

    with pytest.raises(PlanRequestConflictError):
        repo.create_plan_lifecycle(
            "client-a",
            _plan_payload(request_id="same", title="changed"),
        )

    assert retry["id"] == first["id"]
    assert other_client["id"] != first["id"]


def test_create_plan_lifecycle_holds_immediate_lock_until_plan_insert(
    tmp_path,
    monkeypatch,
):
    repo = _plan_repo(tmp_path)
    entered = threading.Event()
    release = threading.Event()
    errors = []
    result = {}
    original_new_plan_id = plan_store._new_plan_id

    def gated_new_plan_id():
        entered.set()
        if not release.wait(timeout=5):
            raise AssertionError("test gate was not released")
        return original_new_plan_id()

    monkeypatch.setattr(plan_store, "_new_plan_id", gated_new_plan_id)

    def create_worker():
        try:
            result["plan"] = repo.create_plan_lifecycle(
                "client-a",
                _plan_payload(request_id="write-lock"),
            )
        except Exception as exc:
            errors.append(exc)
            entered.set()

    worker = threading.Thread(target=create_worker)
    worker.start()
    assert entered.wait(timeout=2), "create worker did not reach the insert gate"
    if errors:
        release.set()
        worker.join(timeout=5)
        raise errors[0]

    writer_error = ""
    try:
        with sqlite3.connect(repo.db_path, timeout=0.05) as connection:
            connection.execute(
                """
                INSERT INTO draws (
                    game_key, game_name, issue, draw_date, week, red_numbers,
                    blue_number, sales, pool_money, content
                )
                VALUES ('3d', 'FC3D', '2026156', '2026-06-16', '', '9,9,9', '', '', '', '')
                """
            )
    except sqlite3.OperationalError as exc:
        writer_error = str(exc)
    finally:
        release.set()
        worker.join(timeout=5)

    assert not worker.is_alive()
    assert writer_error
    assert "locked" in writer_error.lower()
    assert result["plan"]["target_issue"] == "2026156"
    assert repo.draw_by_issue("3d", "2026156") is None


def test_review_plan_lifecycle_missing_draw_is_atomic_and_missing_plan_is_404(tmp_path):
    repo = _plan_repo(tmp_path)
    plan = repo.create_plan("client-a", _plan_payload(request_id="review-missing"))

    with pytest.raises(PlanDrawUnavailableError):
        repo.review_plan_lifecycle("client-a", plan["id"])

    fetched = repo.get_plan("client-a", plan["id"])
    assert fetched["status"] == "pending_review"
    assert fetched["review"] is None

    repo.delete_plan("client-a", plan["id"])
    with pytest.raises(PlanNotFoundError):
        repo.review_plan_lifecycle("client-a", plan["id"])


def test_review_plan_lifecycle_missing_draw_clears_existing_review(tmp_path):
    repo = _plan_repo(tmp_path)
    plan = repo.create_plan("client-a", _plan_payload(request_id="review-clear"))
    _insert_3d_draw(repo, issue="2026156", draw_date="2026-06-16")
    reviewed = repo.review_plan_lifecycle("client-a", plan["id"])
    assert reviewed["status"] == "reviewed"
    assert _plan_review_count(repo, plan["id"]) == 1
    _delete_3d_draw(repo, issue="2026156")

    with pytest.raises(PlanDrawUnavailableError):
        repo.review_plan_lifecycle("client-a", plan["id"])

    fetched = repo.get_plan("client-a", plan["id"])
    assert fetched["status"] == "pending_review"
    assert fetched["review"] is None
    assert _plan_review_count(repo, plan["id"]) == 0


def test_review_plan_lifecycle_rolls_back_when_review_clear_fails(
    tmp_path,
    monkeypatch,
):
    repo = _plan_repo(tmp_path)
    plan = repo.create_plan("client-a", _plan_payload(request_id="review-rollback"))
    _insert_3d_draw(repo, issue="2026156", draw_date="2026-06-16")
    reviewed = repo.review_plan_lifecycle("client-a", plan["id"])
    assert reviewed["status"] == "reviewed"
    _delete_3d_draw(repo, issue="2026156")

    def fail_after_delete(connection, plan_id):
        connection.execute("DELETE FROM plan_reviews WHERE plan_id = ?", (plan_id,))
        raise sqlite3.OperationalError("sqlite secret path")

    monkeypatch.setattr(
        plan_store,
        "clear_plan_review_in_transaction",
        fail_after_delete,
        raising=False,
    )

    with pytest.raises(sqlite3.OperationalError):
        repo.review_plan_lifecycle("client-a", plan["id"])

    fetched = repo.get_plan("client-a", plan["id"])
    assert fetched["status"] == "reviewed"
    assert fetched["review"] is not None
    assert _plan_review_count(repo, plan["id"]) == 1


def test_carry_forward_lifecycle_requires_source_draw_and_rejects_drawn_target(tmp_path):
    repo = _plan_repo(tmp_path)
    source = repo.create_plan(
        "client-a",
        _plan_payload(request_id="carry-source", target_issue="2026156"),
    )
    _insert_3d_draw(repo, issue="2026155", draw_date="2026-06-15")

    with pytest.raises(PlanDrawUnavailableError):
        repo.carry_forward_plan_lifecycle("client-a", source["id"])

    assert len(repo.list_plans("client-a", limit=10)) == 1

    _insert_3d_draw(repo, issue="2026156", draw_date="2026-06-18")
    _insert_3d_draw(repo, issue="2026157", draw_date="2026-06-17")

    with pytest.raises(PlanTargetAlreadyDrawnError):
        repo.carry_forward_plan_lifecycle("client-a", source["id"])


def test_carry_forward_lifecycle_request_id_conflicts_on_different_payload(tmp_path):
    repo = _plan_repo(tmp_path)
    first_source = repo.create_plan(
        "client-a",
        _plan_payload(request_id="carry-first", title="first"),
    )
    second_source = repo.create_plan(
        "client-a",
        _plan_payload(
            request_id="carry-second",
            title="second",
            target_issue="2026157",
            target_draw_date="2026-06-17",
        ),
    )
    _insert_3d_draw(repo, issue="2026156", draw_date="2026-06-16")
    first = repo.carry_forward_plan_lifecycle(
        "client-a",
        first_source["id"],
        request_id="carry-conflict",
    )
    retry = repo.carry_forward_plan_lifecycle(
        "client-a",
        first_source["id"],
        request_id="carry-conflict",
    )
    _insert_3d_draw(repo, issue="2026157", draw_date="2026-06-17")

    with pytest.raises(PlanRequestConflictError):
        repo.carry_forward_plan_lifecycle(
            "client-a",
            second_source["id"],
            request_id="carry-conflict",
        )

    assert retry["id"] == first["id"]
