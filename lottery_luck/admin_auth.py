from __future__ import annotations

import os
import secrets
from typing import Annotated

from fastapi import Header, HTTPException


AUTH_DETAIL = "admin authorization required"
AUTH_SCHEME = "LotteryAdmin"
ADMIN_TOKEN_HEADER = "X-Lottery-Admin-Token"


def _unauthorized() -> HTTPException:
    return HTTPException(
        status_code=401,
        detail=AUTH_DETAIL,
        headers={"WWW-Authenticate": AUTH_SCHEME},
    )


def admin_token_is_valid(supplied_token: str | None, expected_token: str | None = None) -> bool:
    expected = (
        os.getenv("LOTTERY_LUCK_ADMIN_TOKEN", "")
        if expected_token is None
        else expected_token
    ).strip()
    supplied = (supplied_token or "").strip()
    if not expected or not supplied:
        return False
    return secrets.compare_digest(expected, supplied)


def require_admin(
    x_lottery_admin_token: Annotated[
        str | None,
        Header(alias=ADMIN_TOKEN_HEADER),
    ] = None,
) -> None:
    if not admin_token_is_valid(x_lottery_admin_token):
        raise _unauthorized()
