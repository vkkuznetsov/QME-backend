import logging.config
from fastapi import FastAPI

from backend.api.auth.api import API
from backend.api.healthcheck.healthcheck import router as healthcheck_router
from fastapi.middleware.cors import CORSMiddleware
from backend.config import settings

origins = settings.CORS.origins
class App:

    def __init__(self):
        self.app = FastAPI()
        self.init_logging()
        self._add_middleware()
        self.connect_api()

    @staticmethod
    def init_logging():
        logging.config.dictConfig(settings.LOGGING)

    def _add_middleware(self) -> None:
        """Подключения middleware."""
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=origins,
            allow_credentials=True,
            allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "HEAD"],
            allow_headers=["*"],
        )
    def connect_api(self):
        api = API()
        self.app.include_router(api.router)
        self.app.include_router(healthcheck_router)

app = App().app
