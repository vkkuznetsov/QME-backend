from fastapi import APIRouter, UploadFile, File
from logging import getLogger

log = getLogger()


class API:
    def __init__(self):
        self._router = APIRouter()
        self._setup_routes()

    @property
    def router(self):
        return self._router

    def _setup_routes(self):
        self.router.add_api_route("/upload/data1", self.handle_txt_file, methods=["POST"])
        self.router.add_api_route('/upload/data2', self.handle_csv_file, methods=["POST"])

    async def handle_txt_file(self, file: UploadFile = File(...)):
        log.info("Получен файл")
        return {"filename": file.filename}

    async def handle_csv_file(self, file: UploadFile = File(...)):
        return {"filename": file.filename}
