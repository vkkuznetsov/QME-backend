from dishka.integrations.fastapi import FromDishka, inject
from fastapi import APIRouter

from backend.business_logic import IHealthCheckService


router = APIRouter(tags=['healthcheks'], prefix='/healthcheck')


@router.get('')
@inject
async def database_healthcheck(healthcheck_service: FromDishka[IHealthCheckService]):
    response_data = await healthcheck_service.check()
    return response_data
