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
    draw_main_count: int | None = None
    provider: str = "cwl"

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "draw_main_count",
            self.main_count if self.draw_main_count is None else self.draw_main_count,
        )


GAME_RULES = {
    "ssq": GameRule("ssq", "双色球", range(1, 34), 6, range(1, 17), 1, False, (1, 3, 6)),
    "3d": GameRule("3d", "福彩3D", range(0, 10), 3, None, 0, True, None),
    "qlc": GameRule("qlc", "七乐彩", range(1, 31), 7, range(1, 31), 1, False, (0, 2, 4)),
    "kl8": GameRule("kl8", "快乐8", range(1, 81), 10, None, 0, False, None, 20),
    "dlt": GameRule("dlt", "大乐透", range(1, 36), 5, range(1, 13), 2, False, (0, 2, 5), None, "sports"),
    "pl3": GameRule("pl3", "排列3", range(0, 10), 3, None, 0, True, None, None, "sports"),
    "pl5": GameRule("pl5", "排列5", range(0, 10), 5, None, 0, True, None, None, "sports"),
}


FRONTEND_GAME_KEYS = ("ssq", "dlt", "3d", "pl3", "kl8")
RESERVED_GAME_RULES = {}


def _split_numbers(value: str) -> list[int]:
    if not value:
        return []
    return [int(part) for part in value.split(",") if part != ""]


def parse_numbers(game_key: str, red_numbers: str, blue_number: str) -> dict[str, list[int]]:
    """Parse stored CWL number strings; game_key is kept for call-site clarity."""
    return {"main": _split_numbers(red_numbers), "special": _split_numbers(blue_number)}


def candidate_draw_dates(game_key: str, start_date: str, days: int) -> list[date]:
    """Return candidate dates in the inclusive window starting at start_date."""
    rule = GAME_RULES[game_key]
    start = date.fromisoformat(start_date)
    result: list[date] = []
    for offset in range(days):
        current = start + timedelta(days=offset)
        if rule.draw_weekdays is None or current.weekday() in rule.draw_weekdays:
            result.append(current)
    return result
