from fastapi import APIRouter
from fastapi.responses import JSONResponse
from typing import Dict

from backend.logic.services.healthcheck.alchemy import PostgresHealthcheckService, RedisHealthcheckService

router = APIRouter(prefix='/health', tags=['healthcheks'])

@router.get('/all_connection')
async def all_healthcheck() -> JSONResponse:
    results = {}
    results.update(await PostgresHealthcheckService().check())
    results.update(await RedisHealthcheckService().check())
    
    status = 200 if all(results.values()) else 503
    return JSONResponse(content=results, status_code=status)

@router.get('/status-container')
async def check_status_containers() -> JSONResponse:
    
    return JSONResponse(content='Not implemented', status_code=501)

@router.get('/database', response_model=Dict[str, bool])
async def database_healthcheck() -> Dict[str, bool]:
    response_data = await PostgresHealthcheckService().check()
    return response_data

@router.get('/redis', response_model=Dict[str, bool])
async def redis_healthcheck() -> Dict[str, bool]:
    response_data = await RedisHealthcheckService().check()
    return response_data
