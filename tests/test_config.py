from lottery_luck.config import load_local_env


def test_load_local_env_sets_missing_values_without_overriding_existing(
    monkeypatch, tmp_path
):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.setenv("LOTTERY_LUCK_AI_ENABLED", "false")
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                "# local development settings",
                "DEEPSEEK_API_KEY='test-key'",
                'LOTTERY_LUCK_AI_ENABLED="true"',
                "BLANK_VALUE=",
            ]
        ),
        encoding="utf-8",
    )

    load_local_env(env_file)

    assert __import__("os").environ["DEEPSEEK_API_KEY"] == "test-key"
    assert __import__("os").environ["LOTTERY_LUCK_AI_ENABLED"] == "false"
    assert __import__("os").environ["BLANK_VALUE"] == ""


def test_env_flag_parses_false_values_and_defaults(monkeypatch):
    from lottery_luck.config import env_flag

    monkeypatch.delenv("LOTTERY_LUCK_FEATURE_FLAG", raising=False)
    assert env_flag("LOTTERY_LUCK_FEATURE_FLAG") is False
    assert env_flag("LOTTERY_LUCK_FEATURE_FLAG", default=True) is True

    for value in ["0", "false", "False", " no ", "OFF", "disabled"]:
        monkeypatch.setenv("LOTTERY_LUCK_FEATURE_FLAG", value)
        assert env_flag("LOTTERY_LUCK_FEATURE_FLAG", default=True) is False

    monkeypatch.setenv("LOTTERY_LUCK_FEATURE_FLAG", "yes")
    assert env_flag("LOTTERY_LUCK_FEATURE_FLAG") is True
