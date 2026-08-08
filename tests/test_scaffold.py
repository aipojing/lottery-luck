from lottery_luck.config import DB_PATH, PROJECT_ROOT


def test_project_paths_point_to_existing_history_database():
    assert (PROJECT_ROOT / "lottery_luck").is_dir()
    assert DB_PATH == PROJECT_ROOT / "cwl_history" / "cwl_history.sqlite"
    assert DB_PATH.exists()
