from dishka import make_async_container
from dishka.integrations.fastapi import setup_dishka


from fastapi import FastAPI

from backend.api.healthcheck.healthcheck import router as healthcheck_router
from backend.api.auth.api import API

from backend.logger.logger import init_logging
from backend.project.config import Config, get_config
from backend.project.providers.db import DBProvider
from backend.project.providers.healthcheck import HealthCheckProvider


def get_app() -> FastAPI:
    config = get_config()
    init_logging(config.logging_settings.LOGGING_LEVEL)

    fastapi_params = dict(
        title=config.app_settings.PROJECT_NAME,
        version=config.app_settings.VERSION,
        debug=config.app_settings.DEBUG
    )

    app = FastAPI(**fastapi_params)

    container = make_async_container(DBProvider(), HealthCheckProvider())
    setup_dishka(container, app)

    app.include_router(healthcheck_router)
    app.include_router(API().router)

    return app
