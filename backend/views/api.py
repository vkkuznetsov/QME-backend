from fastapi import APIRouter
from fastapi import Response
from fastapi.responses import JSONResponse


class API:
    def __init__(self):
        self._router = APIRouter()
        self.setup_routers()

    @property
    def router(self):
        return self._router

    def setup_routers(self):
        self.router.add_api_route("/login", self.login)


    def login(self):
        return JSONResponse({"123":"123"})
