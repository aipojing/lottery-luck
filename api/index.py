import os

os.environ.setdefault("LOTTERY_LUCK_SERVE_STATIC", "false")
os.environ.setdefault("LOTTERY_LUCK_AUTO_UPDATE_ENABLED", "false")

from lottery_luck.api import app

__all__ = ["app"]
