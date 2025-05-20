import logging.config
from contextlib import asynccontextmanager

from fastapi import FastAPI

from backend.api.router import api_router
from fastapi.middleware.cors import CORSMiddleware
from backend.config import settings
from backend.database.database import init_db

origins = settings.CORS.origins


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield
    pass

class App:

    def __init__(self):
        self.app = FastAPI(lifespan=lifespan)
        self.init_logging()
        self._add_middleware()
        self.connect_api()
        self.add_ignore_warnings()

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
        self.app.include_router(api_router)

    @staticmethod
    def add_ignore_warnings():
        import warnings
        warnings.filterwarnings("ignore", message="Workbook contains no default style")


app = App().app
