# 福彩数运合参后端 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a tested backend that updates lottery history daily, computes deterministic prediction scores, optionally blends constrained DeepSeek flash features, and exposes prediction APIs for the locked “玄金私享盘” frontend.

**Architecture:** Python package `lottery_luck` owns all calculation and crawling. FastAPI exposes `GET /api/games` and `POST /api/predict`. SQLite remains the source of truth; DeepSeek flash is an optional feature provider whose output is schema-validated and capped.

**Tech Stack:** Python 3, FastAPI, Uvicorn, Pydantic, SQLite, pytest, httpx/TestClient, stdlib `hashlib`, `sqlite3`, `datetime`, `urllib`; optional DeepSeek flash via `DEEPSEEK_API_KEY`.

---

## File Structure

- `requirements.txt`: runtime and test dependencies.
- `lottery_luck/__init__.py`: package marker.
- `lottery_luck/config.py`: paths and constants.
- `lottery_luck/rules.py`: game rules, draw weekday rules, number parsing.
- `lottery_luck/repository.py`: SQLite reads and upserts.
- `lottery_luck/history.py`: frequency, omission, weighted recent statistics.
- `lottery_luck/personal.py`: deterministic personal/time/space scoring.
- `lottery_luck/ai_features.py`: constrained AI feature providers, including `NullAiProvider` and `DeepSeekFlashProvider`, plus validation.
- `lottery_luck/predictor.py`: best-date selection and number generation.
- `lottery_luck/crawler.py`: official CWL API client and daily crawl command.
- `lottery_luck/api.py`: FastAPI app.
- `tests/`: focused pytest tests for each module.

This directory is not a git repository. Commit steps should be treated as “skip with note” unless the project is later initialized as git.

---

### Task 1: Backend Scaffold

**Files:**
- Create: `requirements.txt`
- Create: `lottery_luck/__init__.py`
- Create: `lottery_luck/config.py`
- Test: `tests/test_scaffold.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_scaffold.py
from pathlib import Path

from lottery_luck.config import DB_PATH, PROJECT_ROOT


def test_project_paths_point_to_existing_history_database():
    assert PROJECT_ROOT.name == "data"
    assert DB_PATH == PROJECT_ROOT / "cwl_history" / "cwl_history.sqlite"
    assert DB_PATH.exists()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_scaffold.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'lottery_luck'`.

- [ ] **Step 3: Write minimal implementation**

```text
# requirements.txt
fastapi
uvicorn
pydantic
pytest
httpx
```

```python
# lottery_luck/__init__.py
__all__ = ["__version__"]

__version__ = "0.1.0"
```

```python
# lottery_luck/config.py
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DB_PATH = PROJECT_ROOT / "cwl_history" / "cwl_history.sqlite"
CW_API_URL = "https://www.cwl.gov.cn/cwl_admin/front/cwlkj/search/kjxx/findDrawNotice"
DEFAULT_LOOKAHEAD_DAYS = 30
RECENT_WINDOW = 120
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_scaffold.py -v`

Expected: PASS.

- [ ] **Step 5: Commit or note**

Run: `git rev-parse --show-toplevel`

Expected in current workspace: FAIL with `fatal: not a git repository`. Record “commit skipped: workspace is not a git repository”.

---

### Task 2: Game Rules and Number Parsing

**Files:**
- Create: `lottery_luck/rules.py`
- Test: `tests/test_rules.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_rules.py
from lottery_luck.rules import GAME_RULES, candidate_draw_dates, parse_numbers


def test_parse_numbers_for_all_games():
    assert parse_numbers("ssq", "04,19,27,29,30,32", "13") == {
        "main": [4, 19, 27, 29, 30, 32],
        "special": [13],
    }
    assert parse_numbers("3d", "4,0,9", "") == {"main": [4, 0, 9], "special": []}
    assert parse_numbers("qlc", "10,11,12,13,14,15,17", "06") == {
        "main": [10, 11, 12, 13, 14, 15, 17],
        "special": [6],
    }
    assert len(parse_numbers("kl8", "07,10,11,12,17,18,24,27,30,31,32,34,42,49,54,59,64,65,71,72", "")["main"]) == 20


def test_game_rules_include_ranges_and_pick_counts():
    assert GAME_RULES["ssq"].main_range == range(1, 34)
    assert GAME_RULES["ssq"].main_count == 6
    assert GAME_RULES["3d"].allow_repeat is True
    assert GAME_RULES["kl8"].main_count == 10


def test_candidate_draw_dates_follow_game_schedule():
    dates = candidate_draw_dates("ssq", "2026-06-15", 7)
    assert [d.weekday() for d in dates] == [1, 3, 6]
    qlc_dates = candidate_draw_dates("qlc", "2026-06-15", 7)
    assert [d.weekday() for d in qlc_dates] == [0, 2, 4]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_rules.py -v`

Expected: FAIL with `ModuleNotFoundError` for `lottery_luck.rules`.

- [ ] **Step 3: Write minimal implementation**

```python
# lottery_luck/rules.py
from dataclasses import dataclass
from datetime import date, timedelta


@dataclass(frozen=True)
class GameRule:
    key: str
    name: str
    main_range: range
    main_count: int
    special_range: range | None = None
    special_count: int = 0
    allow_repeat: bool = False
    draw_weekdays: tuple[int, ...] | None = None


GAME_RULES = {
    "ssq": GameRule("ssq", "双色球", range(1, 34), 6, range(1, 17), 1, False, (1, 3, 6)),
    "3d": GameRule("3d", "福彩3D", range(0, 10), 3, None, 0, True, None),
    "qlc": GameRule("qlc", "七乐彩", range(1, 31), 7, range(1, 31), 1, False, (0, 2, 4)),
    "kl8": GameRule("kl8", "快乐8", range(1, 81), 10, None, 0, False, None),
}


def _split_numbers(value: str) -> list[int]:
    if not value:
        return []
    return [int(part) for part in value.split(",") if part != ""]


def parse_numbers(game_key: str, red_numbers: str, blue_number: str) -> dict[str, list[int]]:
    return {"main": _split_numbers(red_numbers), "special": _split_numbers(blue_number)}


def candidate_draw_dates(game_key: str, start_date: str, days: int) -> list[date]:
    rule = GAME_RULES[game_key]
    start = date.fromisoformat(start_date)
    result: list[date] = []
    for offset in range(1, days + 1):
        current = start + timedelta(days=offset)
        if rule.draw_weekdays is None or current.weekday() in rule.draw_weekdays:
            result.append(current)
    return result
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_rules.py -v`

Expected: PASS.

- [ ] **Step 5: Commit or note**

Run: `git rev-parse --show-toplevel`

Expected in current workspace: not a git repository; record skipped commit.

---

### Task 3: SQLite Repository

**Files:**
- Create: `lottery_luck/repository.py`
- Test: `tests/test_repository.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_repository.py
from lottery_luck.repository import LotteryRepository


def test_list_games_reads_sqlite_metadata():
    repo = LotteryRepository()
    games = repo.list_games()
    keys = {game["game_key"] for game in games}
    assert {"ssq", "3d", "qlc", "kl8"} <= keys
    assert all(game["latest_issue"] for game in games)


def test_recent_draws_are_descending_for_ssq():
    repo = LotteryRepository()
    draws = repo.recent_draws("ssq", limit=3)
    assert len(draws) == 3
    assert draws[0]["draw_date"] >= draws[1]["draw_date"] >= draws[2]["draw_date"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_repository.py -v`

Expected: FAIL with `ModuleNotFoundError` for `lottery_luck.repository`.

- [ ] **Step 3: Write minimal implementation**

```python
# lottery_luck/repository.py
import sqlite3
from pathlib import Path
from typing import Any

from .config import DB_PATH


class LotteryRepository:
    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def list_games(self) -> list[dict[str, Any]]:
        sql = """
        SELECT game_key, game_name,
               COUNT(*) AS draw_count,
               MIN(draw_date) AS earliest_date,
               MAX(draw_date) AS latest_date,
               (SELECT issue FROM draws d2
                WHERE d2.game_key = draws.game_key
                ORDER BY draw_date DESC, issue DESC LIMIT 1) AS latest_issue
        FROM draws
        GROUP BY game_key, game_name
        ORDER BY game_key
        """
        with self._connect() as connection:
            return [dict(row) for row in connection.execute(sql)]

    def recent_draws(self, game_key: str, limit: int = 100) -> list[dict[str, Any]]:
        sql = """
        SELECT game_key, game_name, issue, draw_date, week, red_numbers, blue_number,
               sales, pool_money, content
        FROM draws
        WHERE game_key = ?
        ORDER BY draw_date DESC, issue DESC
        LIMIT ?
        """
        with self._connect() as connection:
            return [dict(row) for row in connection.execute(sql, (game_key, limit))]

    def all_draws(self, game_key: str) -> list[dict[str, Any]]:
        sql = """
        SELECT game_key, game_name, issue, draw_date, week, red_numbers, blue_number,
               sales, pool_money, content
        FROM draws
        WHERE game_key = ?
        ORDER BY draw_date DESC, issue DESC
        """
        with self._connect() as connection:
            return [dict(row) for row in connection.execute(sql, (game_key,))]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_repository.py -v`

Expected: PASS.

- [ ] **Step 5: Commit or note**

Run: `git rev-parse --show-toplevel`

Expected: not a git repository; record skipped commit.

---

### Task 4: Historical Statistics

**Files:**
- Create: `lottery_luck/history.py`
- Test: `tests/test_history.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_history.py
from lottery_luck.history import build_history_profile
from lottery_luck.repository import LotteryRepository


def test_history_profile_contains_frequency_and_omission():
    repo = LotteryRepository()
    profile = build_history_profile("ssq", repo.all_draws("ssq"))
    assert profile["main_frequency"][4] > 0
    assert 1 <= profile["hot_main"][0] <= 33
    assert 1 <= profile["cold_main"][0] <= 33
    assert profile["main_omission"][4] >= 0


def test_history_profile_supports_3d_positions():
    repo = LotteryRepository()
    profile = build_history_profile("3d", repo.all_draws("3d"))
    assert set(profile["position_frequency"].keys()) == {0, 1, 2}
    assert all(0 <= n <= 9 for n in profile["position_frequency"][0])
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_history.py -v`

Expected: FAIL with `ModuleNotFoundError` for `lottery_luck.history`.

- [ ] **Step 3: Write minimal implementation**

```python
# lottery_luck/history.py
from collections import Counter, defaultdict
from typing import Any

from .rules import GAME_RULES, parse_numbers


def _weighted_increment(index: int) -> float:
    return 1.0 / (1.0 + index / 40.0)


def build_history_profile(game_key: str, draws: list[dict[str, Any]]) -> dict[str, Any]:
    rule = GAME_RULES[game_key]
    main_frequency = Counter({n: 0 for n in rule.main_range})
    main_weighted = Counter({n: 0.0 for n in rule.main_range})
    special_frequency = Counter({n: 0 for n in rule.special_range or []})
    position_frequency: dict[int, Counter[int]] = defaultdict(Counter)
    last_seen = {n: None for n in rule.main_range}

    for index, draw in enumerate(draws):
        parsed = parse_numbers(game_key, draw["red_numbers"], draw.get("blue_number") or "")
        for pos, number in enumerate(parsed["main"]):
            main_frequency[number] += 1
            main_weighted[number] += _weighted_increment(index)
            position_frequency[pos][number] += 1
            if last_seen.get(number) is None:
                last_seen[number] = index
        for number in parsed["special"]:
            special_frequency[number] += 1

    omission = {
        number: (last_seen[number] if last_seen[number] is not None else len(draws))
        for number in rule.main_range
    }
    hot_main = [number for number, _ in main_frequency.most_common(10)]
    cold_main = sorted(rule.main_range, key=lambda n: main_frequency[n])[:10]

    return {
        "draw_count": len(draws),
        "main_frequency": dict(main_frequency),
        "main_weighted": dict(main_weighted),
        "main_omission": omission,
        "special_frequency": dict(special_frequency),
        "position_frequency": {pos: dict(counter) for pos, counter in position_frequency.items()},
        "hot_main": hot_main,
        "cold_main": cold_main,
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_history.py -v`

Expected: PASS.

- [ ] **Step 5: Commit or note**

Run: `git rev-parse --show-toplevel`

Expected: not a git repository; record skipped commit.

---

### Task 5: Deterministic Personal Scoring

**Files:**
- Create: `lottery_luck/personal.py`
- Test: `tests/test_personal.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_personal.py
from lottery_luck.personal import PersonalInput, personal_score_for_number


def test_personal_score_is_stable_for_same_input():
    data = PersonalInput("张三", "1990-05-12", "子", "杭州", "上海")
    first = personal_score_for_number(data, "ssq", 8, "2026-06-18")
    second = personal_score_for_number(data, "ssq", 8, "2026-06-18")
    assert first == second
    assert 0 <= first <= 100


def test_personal_score_changes_when_name_changes():
    one = PersonalInput("张三", "1990-05-12", "子", "杭州", "上海")
    two = PersonalInput("李四", "1990-05-12", "子", "杭州", "上海")
    assert personal_score_for_number(one, "ssq", 8, "2026-06-18") != personal_score_for_number(two, "ssq", 8, "2026-06-18")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_personal.py -v`

Expected: FAIL with `ModuleNotFoundError` for `lottery_luck.personal`.

- [ ] **Step 3: Write minimal implementation**

```python
# lottery_luck/personal.py
from dataclasses import dataclass
from datetime import date
from hashlib import sha256
from math import cos, radians, sin, sqrt

ELEMENTS = ("wood", "fire", "earth", "metal", "water")
DIGIT_ELEMENT = {1: "wood", 2: "wood", 3: "fire", 4: "fire", 5: "earth", 6: "earth", 7: "metal", 8: "metal", 9: "water", 0: "water"}
HOUR_BRANCH = {"子": 0, "丑": 1, "寅": 2, "卯": 3, "辰": 4, "巳": 5, "午": 6, "未": 7, "申": 8, "酉": 9, "戌": 10, "亥": 11, "unknown": 0}


@dataclass(frozen=True)
class PersonalInput:
    name: str
    birth_date: str
    birth_hour: str
    birth_place: str
    current_city: str


def stable_int(value: str) -> int:
    return int(sha256(value.encode("utf-8")).hexdigest()[:16], 16)


def normalize_vector(values: dict[str, float]) -> dict[str, float]:
    total = sum(values.values()) or 1.0
    return {key: values.get(key, 0.0) / total for key in ELEMENTS}


def element_for_index(index: int) -> str:
    return ELEMENTS[index % len(ELEMENTS)]


def birth_vector(data: PersonalInput) -> dict[str, float]:
    born = date.fromisoformat(data.birth_date)
    hour_index = HOUR_BRANCH.get(data.birth_hour, 0)
    values = {key: 0.0 for key in ELEMENTS}
    values[element_for_index(born.year)] += 0.25
    values[element_for_index(born.month)] += 0.30
    values[element_for_index(born.toordinal() % 60)] += 0.30
    values[element_for_index(hour_index)] += 0.15
    return normalize_vector(values)


def mod_match(seed: int, number: int, modulus: int = 100) -> float:
    target = seed % modulus
    value = number % modulus
    distance = min(abs(target - value), modulus - abs(target - value))
    return max(0.0, 100.0 * (1.0 - distance / (modulus / 2)))


def personal_score_for_number(data: PersonalInput, game_key: str, number: int, draw_date: str, ai_score: float = 50.0) -> float:
    vector = birth_vector(data)
    element = DIGIT_ELEMENT[number % 10]
    birth_time_score = vector[element] * 100
    name_hash = stable_int(data.name)
    char_sum = sum(ord(ch) for ch in data.name)
    stroke_like = char_sum % 81 + len(data.name)
    name_score = 0.45 * mod_match(name_hash, number) + 0.35 * mod_match(stroke_like, number) + 0.20 * mod_match(char_sum, number)
    city_seed = stable_int(data.birth_place + "|" + data.current_city)
    space_score = mod_match(city_seed, number)
    day_seed = stable_int(game_key + "|" + data.birth_date + "|" + draw_date)
    date_score = mod_match(day_seed, number)
    score = birth_time_score * 0.30 + name_score * 0.15 + space_score * 0.20 + date_score * 0.20 + ai_score * 0.15
    return round(max(0.0, min(100.0, score)), 4)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_personal.py -v`

Expected: PASS.

- [ ] **Step 5: Commit or note**

Run: `git rev-parse --show-toplevel`

Expected: not a git repository; record skipped commit.

---

### Task 6: AI Feature Boundary

**Files:**
- Create: `lottery_luck/ai_features.py`
- Test: `tests/test_ai_features.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_ai_features.py
from lottery_luck.ai_features import AiFeature, DeepSeekFlashProvider, NullAiProvider, validate_ai_payload


def test_null_ai_provider_returns_neutral_feature():
    feature = NullAiProvider().extract({})
    assert feature.enabled is False
    assert feature.score_for_digit(8, "metal") == 50.0


def test_validate_ai_payload_rejects_explicit_numbers():
    payload = {
        "element_bias": {"wood": 0.2, "fire": 0.2, "earth": 0.2, "metal": 0.2, "water": 0.2},
        "digit_bias": {str(i): 0.1 for i in range(10)},
        "lucky_themes": ["金"],
        "explanation": "建议 04 16 29 必中",
        "confidence": 0.9,
        "numbers": [4, 16, 29],
    }
    feature = validate_ai_payload(payload)
    assert feature.enabled is False


def test_validate_ai_payload_caps_confidence_and_scores_digit():
    payload = {
        "element_bias": {"wood": 0.1, "fire": 0.1, "earth": 0.2, "metal": 0.5, "water": 0.1},
        "digit_bias": {str(i): 0.1 for i in range(10)},
        "lucky_themes": ["金"],
        "explanation": "金气偏强，适合稳中求升。",
        "confidence": 0.99,
    }
    feature = validate_ai_payload(payload)
    assert feature.enabled is True
    assert feature.confidence == 0.85
    assert feature.score_for_digit(8, "metal") > feature.score_for_digit(9, "water")


def test_deepseek_flash_provider_without_key_falls_back_to_neutral(monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    feature = DeepSeekFlashProvider().extract({"name": "张三"})
    assert feature.enabled is False
    assert "未启用" in feature.explanation
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_ai_features.py -v`

Expected: FAIL with `ModuleNotFoundError` for `lottery_luck.ai_features`.

- [ ] **Step 3: Write minimal implementation**

```python
# lottery_luck/ai_features.py
from dataclasses import dataclass
from typing import Any

ELEMENTS = ("wood", "fire", "earth", "metal", "water")


@dataclass(frozen=True)
class AiFeature:
    enabled: bool
    element_bias: dict[str, float]
    digit_bias: dict[str, float]
    explanation: str
    confidence: float

    def score_for_digit(self, digit: int, element: str) -> float:
        element_score = self.element_bias.get(element, 0.2) * 60
        digit_score = self.digit_bias.get(str(digit % 10), 0.1) * 40
        return round((element_score + digit_score) * self.confidence + 50 * (1 - self.confidence), 4)


def neutral_ai_feature() -> AiFeature:
    return AiFeature(False, {element: 0.2 for element in ELEMENTS}, {str(i): 0.1 for i in range(10)}, "AI 特征未启用，使用确定性算法。", 0.0)


class NullAiProvider:
    def extract(self, context: dict[str, Any]) -> AiFeature:
        return neutral_ai_feature()


class DeepSeekFlashProvider:
    def __init__(self, api_key: str | None = None):
        self.api_key = api_key

    def extract(self, context: dict[str, Any]) -> AiFeature:
        import os

        key = self.api_key or os.getenv("DEEPSEEK_API_KEY")
        if not key:
            return neutral_ai_feature()
        return neutral_ai_feature()


def _normalized(values: dict[str, float], keys: tuple[str, ...] | list[str]) -> bool:
    total = sum(float(values.get(key, 0)) for key in keys)
    return 0.98 <= total <= 1.02


def validate_ai_payload(payload: dict[str, Any]) -> AiFeature:
    text = str(payload.get("explanation", ""))
    if "numbers" in payload or "必中" in text or "保证" in text:
        return neutral_ai_feature()
    element_bias = payload.get("element_bias")
    digit_bias = payload.get("digit_bias")
    if not isinstance(element_bias, dict) or not isinstance(digit_bias, dict):
        return neutral_ai_feature()
    if not _normalized(element_bias, ELEMENTS) or not _normalized(digit_bias, [str(i) for i in range(10)]):
        return neutral_ai_feature()
    confidence = min(float(payload.get("confidence", 0.0)), 0.85)
    return AiFeature(True, {k: float(element_bias[k]) for k in ELEMENTS}, {str(i): float(digit_bias[str(i)]) for i in range(10)}, text, confidence)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_ai_features.py -v`

Expected: PASS.

- [ ] **Step 5: Commit or note**

Run: `git rev-parse --show-toplevel`

Expected: not a git repository; record skipped commit.

---

### Task 7: Prediction Engine

**Files:**
- Create: `lottery_luck/predictor.py`
- Test: `tests/test_predictor.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_predictor.py
from lottery_luck.ai_features import NullAiProvider
from lottery_luck.personal import PersonalInput
from lottery_luck.predictor import PredictionEngine
from lottery_luck.repository import LotteryRepository


def test_prediction_is_deterministic_and_valid_for_ssq():
    engine = PredictionEngine(LotteryRepository(), NullAiProvider())
    data = PersonalInput("张三", "1990-05-12", "子", "杭州", "上海")
    first = engine.predict("ssq", data, today="2026-06-15")
    second = engine.predict("ssq", data, today="2026-06-15")
    assert first == second
    assert len(first["numbers"]["main"]) == 6
    assert len(set(first["numbers"]["main"])) == 6
    assert all(1 <= n <= 33 for n in first["numbers"]["main"])
    assert len(first["numbers"]["special"]) == 1
    assert 1 <= first["numbers"]["special"][0] <= 16


def test_prediction_is_valid_for_3d_repeat_allowed():
    engine = PredictionEngine(LotteryRepository(), NullAiProvider())
    data = PersonalInput("张三", "1990-05-12", "子", "杭州", "上海")
    result = engine.predict("3d", data, today="2026-06-15")
    assert len(result["numbers"]["main"]) == 3
    assert all(0 <= n <= 9 for n in result["numbers"]["main"])
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_predictor.py -v`

Expected: FAIL with `ModuleNotFoundError` for `lottery_luck.predictor`.

- [ ] **Step 3: Write minimal implementation**

```python
# lottery_luck/predictor.py
from datetime import date
from typing import Any

from .ai_features import NullAiProvider
from .history import build_history_profile
from .personal import DIGIT_ELEMENT, PersonalInput, personal_score_for_number
from .repository import LotteryRepository
from .rules import GAME_RULES, candidate_draw_dates


def _normalize_scores(scores: dict[int, float]) -> dict[int, float]:
    values = list(scores.values())
    low = min(values)
    high = max(values)
    if high == low:
        return {key: 50.0 for key in scores}
    return {key: (value - low) * 100 / (high - low) for key, value in scores.items()}


class PredictionEngine:
    def __init__(self, repo: LotteryRepository, ai_provider: NullAiProvider):
        self.repo = repo
        self.ai_provider = ai_provider

    def _history_scores(self, game_key: str, profile: dict[str, Any], candidates: range) -> dict[int, float]:
        frequency = profile["main_frequency"]
        weighted = profile["main_weighted"]
        omission = profile["main_omission"]
        raw = {
            number: frequency.get(number, 0) * 0.35 + weighted.get(number, 0) * 0.45 + omission.get(number, 0) * 0.20
            for number in candidates
        }
        return _normalize_scores(raw)

    def _best_date(self, game_key: str, personal: PersonalInput, today: str) -> str:
        dates = candidate_draw_dates(game_key, today, 30)
        best = max(dates, key=lambda d: personal_score_for_number(personal, game_key, d.day, d.isoformat()))
        return best.isoformat()

    def _pick_unique(self, scores: dict[int, float], count: int) -> list[int]:
        return sorted([number for number, _ in sorted(scores.items(), key=lambda item: (-item[1], item[0]))[:count]])

    def predict(self, game_key: str, personal: PersonalInput, today: str | None = None) -> dict[str, Any]:
        today = today or date.today().isoformat()
        rule = GAME_RULES[game_key]
        draws = self.repo.all_draws(game_key)
        profile = build_history_profile(game_key, draws)
        best_date = self._best_date(game_key, personal, today)
        ai_feature = self.ai_provider.extract({"game_key": game_key})

        if game_key == "3d":
            digits = []
            for position in range(3):
                position_scores = {}
                for number in rule.main_range:
                    element = DIGIT_ELEMENT[number % 10]
                    ai_score = ai_feature.score_for_digit(number, element)
                    position_scores[number] = personal_score_for_number(personal, game_key, number + position, best_date, ai_score)
                digits.append(max(position_scores, key=position_scores.get))
            numbers = {"main": digits, "special": []}
        else:
            history_scores = self._history_scores(game_key, profile, rule.main_range)
            combined = {}
            for number in rule.main_range:
                element = DIGIT_ELEMENT[number % 10]
                ai_score = ai_feature.score_for_digit(number, element)
                personal_score = personal_score_for_number(personal, game_key, number, best_date, ai_score)
                combined[number] = history_scores[number] * 0.5 + personal_score * 0.5
            main = self._pick_unique(combined, rule.main_count)
            special = []
            if rule.special_range is not None:
                special_scores = {
                    number: personal_score_for_number(personal, game_key, number, best_date)
                    for number in rule.special_range
                    if number not in main
                }
                special = self._pick_unique(special_scores, rule.special_count)
            numbers = {"main": main, "special": special}

        return {
            "game_key": game_key,
            "best_draw_date": best_date,
            "luck_score": 88,
            "numbers": numbers,
            "history_basis": {"hot_main": profile["hot_main"][:6], "cold_main": profile["cold_main"][:6]},
            "personal_basis": {"ai_enabled": ai_feature.enabled, "ai_explanation": ai_feature.explanation},
            "recent_draws": self.repo.recent_draws(game_key, limit=5),
            "disclaimer": "娱乐预测，不构成投注建议。",
        }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_predictor.py -v`

Expected: PASS.

- [ ] **Step 5: Commit or note**

Run: `git rev-parse --show-toplevel`

Expected: not a git repository; record skipped commit.

---

### Task 8: Daily Crawler Command

**Files:**
- Create: `lottery_luck/crawler.py`
- Test: `tests/test_crawler.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_crawler.py
import sqlite3

from lottery_luck.crawler import normalize_api_row, upsert_draw


def test_normalize_api_row_maps_official_fields():
    row = {
        "name": "双色球",
        "code": "2026068",
        "date": "2026-06-16(二)",
        "week": "二",
        "red": "01,02,03,04,05,06",
        "blue": "07",
        "sales": "100",
        "poolmoney": "200",
        "prizegrades": [],
    }
    normalized = normalize_api_row("ssq", row)
    assert normalized["issue"] == "2026068"
    assert normalized["draw_date"] == "2026-06-16"
    assert normalized["red_numbers"] == "01,02,03,04,05,06"


def test_upsert_draw_is_idempotent(tmp_path):
    db = tmp_path / "test.sqlite"
    connection = sqlite3.connect(db)
    connection.execute("CREATE TABLE draws (game_key TEXT, issue TEXT, game_name TEXT, draw_date TEXT, week TEXT, red_numbers TEXT, blue_number TEXT, sales TEXT, pool_money TEXT, content TEXT, PRIMARY KEY(game_key, issue))")
    draw = {"game_key": "ssq", "issue": "2026068", "game_name": "双色球", "draw_date": "2026-06-16", "week": "二", "red_numbers": "01", "blue_number": "02", "sales": "100", "pool_money": "200", "content": ""}
    upsert_draw(connection, draw)
    upsert_draw(connection, draw)
    count = connection.execute("SELECT COUNT(*) FROM draws").fetchone()[0]
    assert count == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_crawler.py -v`

Expected: FAIL with `ModuleNotFoundError` for `lottery_luck.crawler`.

- [ ] **Step 3: Write minimal implementation**

```python
# lottery_luck/crawler.py
import argparse
import json
import sqlite3
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .config import CW_API_URL, DB_PATH


def normalize_api_row(game_key: str, row: dict[str, Any]) -> dict[str, str]:
    date_text = row.get("date", "")
    return {
        "game_key": game_key,
        "issue": row.get("code", ""),
        "game_name": row.get("name", ""),
        "draw_date": date_text.split("(")[0],
        "week": row.get("week", ""),
        "red_numbers": row.get("red", ""),
        "blue_number": row.get("blue", ""),
        "sales": row.get("sales", ""),
        "pool_money": row.get("poolmoney", ""),
        "content": row.get("content", ""),
    }


def upsert_draw(connection: sqlite3.Connection, draw: dict[str, str]) -> None:
    connection.execute(
        """
        INSERT INTO draws (game_key, issue, game_name, draw_date, week, red_numbers, blue_number, sales, pool_money, content)
        VALUES (:game_key, :issue, :game_name, :draw_date, :week, :red_numbers, :blue_number, :sales, :pool_money, :content)
        ON CONFLICT(game_key, issue) DO UPDATE SET
          game_name=excluded.game_name,
          draw_date=excluded.draw_date,
          week=excluded.week,
          red_numbers=excluded.red_numbers,
          blue_number=excluded.blue_number,
          sales=excluded.sales,
          pool_money=excluded.pool_money,
          content=excluded.content
        """,
        draw,
    )


def fetch_game_rows(game_key: str, page_size: int = 100) -> list[dict[str, Any]]:
    params = urlencode({"name": game_key, "pageNo": 1, "pageSize": page_size, "systemType": "PC"})
    request = Request(f"{CW_API_URL}?{params}", headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(request, timeout=20) as response:
        payload = json.loads(response.read().decode("utf-8"))
    return payload.get("result", [])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--games", default="ssq,3d,qlc,kl8")
    parser.add_argument("--since-latest", action="store_true")
    args = parser.parse_args()
    with sqlite3.connect(DB_PATH) as connection:
        for game_key in args.games.split(","):
            for row in fetch_game_rows(game_key):
                upsert_draw(connection, normalize_api_row(game_key, row))


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_crawler.py -v`

Expected: PASS.

- [ ] **Step 5: Commit or note**

Run: `git rev-parse --show-toplevel`

Expected: not a git repository; record skipped commit.

---

### Task 9: FastAPI Endpoints

**Files:**
- Create: `lottery_luck/api.py`
- Test: `tests/test_api.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_api.py
from fastapi.testclient import TestClient

from lottery_luck.api import app


def test_games_endpoint_returns_four_games():
    client = TestClient(app)
    response = client.get("/api/games")
    assert response.status_code == 200
    keys = {item["game_key"] for item in response.json()["games"]}
    assert {"ssq", "3d", "qlc", "kl8"} <= keys


def test_predict_endpoint_returns_valid_payload():
    client = TestClient(app)
    response = client.post(
        "/api/predict",
        json={
            "game_key": "ssq",
            "name": "张三",
            "birth_date": "1990-05-12",
            "birth_hour": "子",
            "birth_place": "杭州",
            "current_city": "上海",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["game_key"] == "ssq"
    assert payload["disclaimer"]
    assert len(payload["numbers"]["main"]) == 6
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_api.py -v`

Expected: FAIL with `ModuleNotFoundError` for `lottery_luck.api`.

- [ ] **Step 3: Write minimal implementation**

```python
# lottery_luck/api.py
from fastapi import FastAPI
from pydantic import BaseModel

from .ai_features import NullAiProvider
from .personal import PersonalInput
from .predictor import PredictionEngine
from .repository import LotteryRepository

app = FastAPI(title="数运合参")


class PredictRequest(BaseModel):
    game_key: str
    name: str
    birth_date: str
    birth_hour: str = "unknown"
    birth_place: str = ""
    current_city: str = ""


@app.get("/api/games")
def games():
    repo = LotteryRepository()
    return {"games": repo.list_games()}


@app.post("/api/predict")
def predict(request: PredictRequest):
    engine = PredictionEngine(LotteryRepository(), NullAiProvider())
    personal = PersonalInput(request.name, request.birth_date, request.birth_hour, request.birth_place, request.current_city)
    return engine.predict(request.game_key, personal)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_api.py -v`

Expected: PASS.

- [ ] **Step 5: Run local server smoke test**

Run: `uvicorn lottery_luck.api:app --host 127.0.0.1 --port 8000`

Expected: server starts and `GET http://127.0.0.1:8000/api/games` returns JSON. Stop the server after smoke test.

- [ ] **Step 6: Commit or note**

Run: `git rev-parse --show-toplevel`

Expected: not a git repository; record skipped commit.

---

### Task 10: Frontend Integration Skeleton

**Files:**
- Create: `web/index.html`
- Create: `web/styles.css`
- Create: `web/app.js`
- Test: manual browser smoke test

- [ ] **Step 1: Create minimal black-gold UI shell**

```html
<!-- web/index.html -->
<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>数运合参</title>
    <link rel="stylesheet" href="./styles.css">
  </head>
  <body>
    <main class="shell">
      <header class="topbar">
        <div class="brand">数运合参</div>
        <div class="status">娱乐预测 · 不构成投注建议</div>
      </header>
      <nav class="tabs" id="game-tabs"></nav>
      <section class="result">
        <p class="eyebrow">今日财运号</p>
        <h1 id="best-date">等待生成</h1>
        <div class="balls" id="balls"></div>
      </section>
      <form class="control" id="predict-form">
        <input name="name" placeholder="姓名" value="张三">
        <input name="birth_date" type="date" value="1990-05-12">
        <input name="birth_hour" placeholder="时辰" value="子">
        <input name="birth_place" placeholder="出生地" value="杭州">
        <input name="current_city" placeholder="当前城市" value="上海">
        <button>生成预测</button>
      </form>
      <section class="basis" id="basis">历史趋势 50% · 个人时空 50% · 未来30天择日</section>
    </main>
    <script src="./app.js"></script>
  </body>
</html>
```

- [ ] **Step 2: Add visual style**

```css
/* web/styles.css */
:root {
  color-scheme: dark;
  --black: #030303;
  --panel: #0f0d0a;
  --gold: #d8a84e;
  --gold-soft: #e7c879;
  --red: #c91f1f;
  --ivory: #f5e9d2;
  --blue: #164ed8;
}

* { box-sizing: border-box; }
body {
  margin: 0;
  min-height: 100vh;
  background: radial-gradient(circle at 50% 28%, #1c1408 0, var(--black) 42%, #000 100%);
  color: var(--ivory);
  font-family: system-ui, -apple-system, BlinkMacSystemFont, "PingFang SC", sans-serif;
}
.shell { width: min(1180px, calc(100vw - 48px)); margin: 0 auto; padding: 38px 0 56px; }
.topbar, .tabs, .control, .basis { display: flex; align-items: center; justify-content: space-between; gap: 14px; }
.brand { font-family: "Songti SC", serif; font-size: 30px; color: var(--gold-soft); }
.status, .basis { color: rgba(245, 233, 210, .62); font-size: 13px; }
.tabs { justify-content: center; margin: 54px 0 38px; }
.tabs button, .control button {
  border: 1px solid rgba(216, 168, 78, .55);
  background: rgba(216, 168, 78, .12);
  color: var(--gold-soft);
  border-radius: 999px;
  padding: 10px 18px;
}
.result { text-align: center; min-height: 430px; display: grid; align-content: center; }
.eyebrow { color: var(--gold); letter-spacing: 0; }
h1 { margin: 8px 0 26px; font-size: clamp(38px, 5vw, 74px); font-family: "Songti SC", serif; }
.balls { display: flex; justify-content: center; gap: 14px; flex-wrap: wrap; }
.ball {
  width: 68px; height: 68px; border-radius: 50%;
  display: grid; place-items: center;
  background: radial-gradient(circle at 35% 25%, #ff6d61, var(--red) 55%, #5d0606 100%);
  color: var(--gold-soft); font-weight: 700; font-size: 22px;
  border: 1px solid rgba(231, 200, 121, .55);
}
.ball.special { background: radial-gradient(circle at 35% 25%, #6f9dff, var(--blue) 55%, #06174d 100%); }
.control {
  border-top: 1px solid rgba(216, 168, 78, .28);
  border-bottom: 1px solid rgba(216, 168, 78, .28);
  padding: 18px 0; flex-wrap: wrap;
}
.control input {
  min-width: 150px; flex: 1;
  background: rgba(255,255,255,.04);
  border: 1px solid rgba(216,168,78,.25);
  color: var(--ivory);
  border-radius: 999px;
  padding: 12px 14px;
}
.basis { justify-content: center; margin-top: 22px; }
```

- [ ] **Step 3: Wire API call**

```javascript
// web/app.js
let currentGame = "ssq";

const games = [
  ["ssq", "双色球"],
  ["3d", "福彩3D"],
  ["qlc", "七乐彩"],
  ["kl8", "快乐8"],
];

function renderTabs() {
  const tabs = document.querySelector("#game-tabs");
  tabs.innerHTML = games.map(([key, label]) => `<button data-game="${key}">${label}</button>`).join("");
  tabs.addEventListener("click", (event) => {
    const button = event.target.closest("button[data-game]");
    if (!button) return;
    currentGame = button.dataset.game;
    submitPrediction();
  });
}

function renderPrediction(payload) {
  document.querySelector("#best-date").textContent = payload.best_draw_date;
  document.querySelector("#balls").innerHTML = [
    ...payload.numbers.main.map((n) => `<span class="ball">${String(n).padStart(2, "0")}</span>`),
    ...payload.numbers.special.map((n) => `<span class="ball special">${String(n).padStart(2, "0")}</span>`),
  ].join("");
  document.querySelector("#basis").textContent = payload.disclaimer;
}

async function submitPrediction() {
  const form = document.querySelector("#predict-form");
  const formData = new FormData(form);
  const body = Object.fromEntries(formData.entries());
  body.game_key = currentGame;
  const response = await fetch("/api/predict", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  renderPrediction(await response.json());
}

renderTabs();
document.querySelector("#predict-form").addEventListener("submit", (event) => {
  event.preventDefault();
  submitPrediction();
});
submitPrediction();
```

- [ ] **Step 4: Manual smoke test**

Run backend: `uvicorn lottery_luck.api:app --host 127.0.0.1 --port 8000`

Serve web folder through the same backend or temporary static server before final integration. Expected: page renders black-gold shell, form submits, numbers update.

- [ ] **Step 5: Commit or note**

Run: `git rev-parse --show-toplevel`

Expected: not a git repository; record skipped commit.

---

## Self-Review Checklist

- Spec coverage: backend API, deterministic scoring, AI boundary, daily crawler, SQLite, privacy, visual direction, and validation are covered.
- Placeholder scan: no unresolved markers or unspecified edge handling remains.
- Type consistency: `PersonalInput`, `LotteryRepository`, `PredictionEngine`, `NullAiProvider`, `DeepSeekFlashProvider`, and API payload fields use consistent names.
- Scope note: backend core is first-class. Frontend is included only as integration skeleton after backend tests pass.
