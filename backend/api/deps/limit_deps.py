from fastapi import Query


def pagination_params(
        start: int = Query(0, ge=0, description="Смещение, откуда начинать"),
        limit: int = Query(10, ge=1, le=100, description="Сколько записей вернуть"),
) -> dict:
    return {"start": start, "limit": limit}
