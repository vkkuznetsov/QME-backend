from fastapi import APIRouter

from .auth import router as auth_router
from .elective import router as elective_router
from .health import router as health_router
from .journal import router as journal_router
from .optimal import router as optimal_router
from .recomendation import router as recommendation_router
from .student import router as student_router
from .transfer import router as transfer_router
from .upload import router as upload_router
from .logs import router as logs_router
from .manager import router as manager_router
from .reports import router as report_router

api_router = APIRouter()

api_router.include_router(student_router)
api_router.include_router(elective_router)
api_router.include_router(transfer_router)
api_router.include_router(upload_router)
api_router.include_router(manager_router)
api_router.include_router(auth_router)
api_router.include_router(recommendation_router)
api_router.include_router(optimal_router)
api_router.include_router(report_router)
api_router.include_router(journal_router)
api_router.include_router(logs_router)
api_router.include_router(health_router)
