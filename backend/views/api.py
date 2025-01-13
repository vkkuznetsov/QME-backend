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
        self.router.add_api_route("/student", self.get_student, methods=["GET"])
        self.router.add_api_route("/upload/student-choices", self.handle_student_choices, methods=["POST"])

    async def get_student(self, email: str):
        return email

    async def handle_student_choices(self, file: UploadFile = File(...)):
        log.info("Получен файл")
        return {"filename": file.filename}
