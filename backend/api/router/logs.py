from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

from backend.logic.services.log_service.orm import ORMLogService

router = APIRouter(prefix="/logs", tags=["logs"])


class LogResponse(BaseModel):
    id: int
    timestamp: datetime
    level: str
    message: str
    source: str

    class Config:
        from_attributes = True


@router.get("/", response_model=List[LogResponse])
async def get_logs(limit: int = 100, log_service: ORMLogService = Depends()):
    """Получает последние логи"""
    logs = await log_service.get_logs(limit)
    return logs


@router.get("/{level}", response_model=List[LogResponse])
async def get_logs_by_level(
    level: str, limit: int = 100, log_service: ORMLogService = Depends()
):
    """Получает логи определенного уровня"""
    logs = await log_service.get_logs_by_level(level, limit)
    return logs


@router.get("/source/{source}", response_model=List[LogResponse])
async def get_logs_by_source(
    source: str, limit: int = 100, log_service: ORMLogService = Depends()
):
    """Получает логи определенного источника"""
    logs = await log_service.get_logs_by_source(source, limit)
    return logs


@router.get("/raw/backend", summary="Чтение логов бекенда")
async def get_backend_logs() -> PlainTextResponse:
    """
    Возвращает содержимое файла logs/application.log как plain text.
    Если файл не найден — возвращает пустую строку.
    """
    try:
        with open("logs/application.log", "r", encoding="utf-8") as f:
            content: str = f.read()
    except FileNotFoundError:
        content = ""
    return PlainTextResponse(content)


@router.delete("/raw/backend", summary="Очистка логов бекенда")
async def clear_backend_logs() -> PlainTextResponse:
    """
    Очищает содержимое файла logs/application.log.
    Если файл не найден — создает пустой файл.
    """
    try:
        with open("logs/application.log", "w", encoding="utf-8") as f:
            f.write("")
        return PlainTextResponse("Логи успешно очищены")
    except Exception as e:
        return PlainTextResponse(f"Ошибка при очистке логов: {str(e)}")
