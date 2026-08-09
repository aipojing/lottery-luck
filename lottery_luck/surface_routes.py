from fastapi import APIRouter

from .surface_config import surface_config_payload

router = APIRouter(prefix="/api/surfaces")


@router.get("/config")
def surface_config() -> dict:
    return surface_config_payload()
