from fastapi import APIRouter
from fastapi.responses import PlainTextResponse
from typing import List, Dict

router = APIRouter(prefix='/logs', tags=['logs'])


@router.get(
    "/backend",
    response_model=List[Dict[str, str | int]],
    summary="Чтение логов бекенда"
)
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


@router.delete(
    "/clear",
    summary="Очистка логов бекенда"
)
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


@router.get(
    "/download",
    response_model=List[Dict[str, str | int]],
    summary="Чтение логов фронтенда"
)
async def get_frontend_logs() -> PlainTextResponse:
    """
    Возвращает содержимое файла logs/frontend.log как plain text.
    Если файл не найден — возвращает пустую строку.
    """
    try:
        with open("logs/application.log", "r", encoding="utf-8") as f:
            content: str = f.read()
    except FileNotFoundError:
        content = ""
    return PlainTextResponse(content)
