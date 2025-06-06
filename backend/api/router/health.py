from typing import Dict

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from backend.logic.services.healthcheck.alchemy import (
    PostgresHealthcheckService,
    RedisHealthcheckService,
)

router = APIRouter(prefix="/health", tags=["healthcheks"])


@router.get("/all_connection")
async def all_healthcheck() -> JSONResponse:
    services = [
        PostgresHealthcheckService().check,
        RedisHealthcheckService().check,
    ]
    results = {}
    for service in services:
        result = await service()
        results.update(result)

    return JSONResponse(content=results)


@router.get("/database", response_model=Dict[str, bool])
async def database_healthcheck() -> Dict[str, bool]:
    response_data = await PostgresHealthcheckService().check()
    return response_data


@router.get("/redis", response_model=Dict[str, bool])
async def redis_healthcheck() -> Dict[str, bool]:
    response_data = await RedisHealthcheckService().check()
    return response_data
