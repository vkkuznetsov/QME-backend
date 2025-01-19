from fastapi import APIRouter

from backend.logic.services.healthcheck.alchemy import PostgresHealthcheckService

router = APIRouter(tags=['healthcheks'], prefix='/healthcheck')


@router.get('')
async def database_healthcheck():
    response_data = await PostgresHealthcheckService().check()
    return response_data
