#!/usr/bin/env python3
"""
generate_embeddings.py

Скрипт для подсчёта эмбeддингов из текстовых полей курса
и записи их в колонку text_embed (JSONB) модели Elective.
"""

import os
import sys
import asyncio
from typing import Optional

from sentence_transformers import SentenceTransformer
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select

# импорт вашей модели
sys.path.append(os.path.abspath(os.path.dirname(__file__)))
from backend.database.database import Base, db_session  # noqa
from backend.database.models.elective import Elective  # noqa


# Используем модель all-MiniLM-L6-v2 для эмбеддингов
embedder = SentenceTransformer("all-MiniLM-L6-v2")

# --- Настройка асинхронного подключения к БД ---
def get_embedding(text: str) -> Optional[list[float]]:
    """
    Возвращает эмбеддинг текста с помощью all-MiniLM-L6-v2.
    """
    if not text.strip():
        return None
    embedding = embedder.encode(text, show_progress_bar=False)
    return embedding.tolist() if hasattr(embedding, "tolist") else list(embedding)

@db_session
async def main(db: AsyncSession):
        result = await db.execute(select(Elective))
        electives = result.scalars().all()
        print(f"Найдено курсов: {len(electives)}")
        updated = 0
        for el in electives:
            source = el.description or el.text or ""
            embedding = get_embedding(source)
            if embedding:
                el.text_embed = embedding
                updated += 1
        await db.commit()
        print(f"Обновлено эмбеддингов: {updated}")

if __name__ == "__main__":
    print("Запуск генерации эмбеддингов...")
    asyncio.run(main())