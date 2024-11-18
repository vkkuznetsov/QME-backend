import logging.config
from fastapi import FastAPI

from backend.views.api import API
from backend.config import settings


class App:

    def __init__(self):
        self.app = FastAPI()
        # self.init_logging()
        self.connect_api()

    @staticmethod
    def init_logging():
        logging.config.dictConfig(settings.LOGGING)

    def connect_api(self):
        api = API()
        self.app.include_router(api.router)


app = App().app
