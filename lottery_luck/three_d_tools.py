from __future__ import annotations

from typing import Any

from .workbench_3d import ALLOWED_WINDOWS, recent_draw_summaries

# Every trend cell shows the drawn digit and the omission streak that digit ended, so the
# definition has to say which of the two omission readings the table carries — in the words a
# player reads it with, not in the words the code computes it with.
TREND_DEFINITION = (
    "每格是这一位当期开出的数字，下面的遗漏是它在这次开出前，已经连续多少期没有开出。"
)


def build_trend_payload(
    draws: list[dict[str, Any]],
    window: int,
) -> dict[str, Any]:
    if type(window) is not int or window not in ALLOWED_WINDOWS:
        raise ValueError("invalid 3d data")

    recent = recent_draw_summaries(draws, limit=window)
    chronological = list(reversed(recent))
    omissions = [
        {str(digit): 0 for digit in range(10)}
        for _ in range(3)
    ]
    rows: list[dict[str, Any]] = []

    for draw in chronological:
        # The streak the drawn digit ends: its omission *before* this draw resets it to 0.
        # `omissions[position][hit]` is 0 by construction afterwards, so it can never carry
        # this number — the trend cell would read 0 on every row of every draw.
        hit_omissions = {
            str(position): omissions[position][str(hit)]
            for position, hit in enumerate(draw["numbers"])
        }
        for position, hit in enumerate(draw["numbers"]):
            for digit in range(10):
                key = str(digit)
                omissions[position][key] = 0 if digit == hit else omissions[position][key] + 1
        rows.append(
            {
                "issue": draw["issue"],
                "draw_date": draw["draw_date"],
                "number_text": draw["number_text"],
                "numbers": list(draw["numbers"]),
                "hit_omissions": dict(hit_omissions),
                "omissions": {
                    str(position): dict(values)
                    for position, values in enumerate(omissions)
                },
            }
        )

    latest = chronological[-1] if chronological else None
    return {
        "window": window,
        "sample_size": len(rows),
        "latest_issue": latest["issue"] if latest else "",
        "latest_date": latest["draw_date"] if latest else "",
        "definition": TREND_DEFINITION,
        "rows": rows,
    }


__all__ = ["TREND_DEFINITION", "build_trend_payload"]
