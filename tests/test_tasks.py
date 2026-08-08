import sqlite3

from lottery_luck.tasks import (
    create_task,
    ensure_task_table,
    list_tasks,
    mark_task_finished,
)
from lottery_luck.scheduler import normalize_scheduler_games


def test_task_queue_creates_and_completes_crawl_task():
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    ensure_task_table(connection)

    task = create_task(connection, kind="crawl", provider="cwl", game_keys=["ssq", "3d"])
    mark_task_finished(connection, task["id"], status="success", result={"wrote_count": 2})

    tasks = list_tasks(connection, limit=5)
    assert tasks[0]["kind"] == "crawl"
    assert tasks[0]["provider"] == "cwl"
    assert tasks[0]["game_keys"] == ["ssq", "3d"]
    assert tasks[0]["status"] == "success"
    assert tasks[0]["result"]["wrote_count"] == 2


def test_scheduler_normalizes_provider_game_defaults():
    assert normalize_scheduler_games("cwl", "") == ["ssq", "3d", "kl8"]
    assert normalize_scheduler_games("sports", "dlt,pl3") == ["dlt", "pl3"]
