from fastapi import FastAPI
from backend.config import settings
from backend.views.api import API


class App:
    def __init__(self) -> None:
        self.app = FastAPI()
        self._init_logger()
        self._init_api()

    @classmethod
    def _init_logger(cls) -> None:
        pass  # пока не понятно как логировать

    def _init_api(self) -> None:
        """Подключение API."""
        api = API()
        self.app.include_router(api.router)


app = App().app
