import logging.config
from fastapi import FastAPI

from backend.api.auth.api import API
from backend.api.healthcheck.healthcheck import router as healthcheck_router
from backend.config import settings


class App:

    def __init__(self):
        self.app = FastAPI()
        self.init_logging()
        self.connect_api()

    @staticmethod
    def init_logging():
        logging.config.dictConfig(settings.LOGGING)

    def connect_api(self):
        api = API()
        self.app.include_router(api.router)
        self.app.include_router(healthcheck_router)


app = App().app
