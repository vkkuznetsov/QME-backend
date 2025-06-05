from typing import List

from backend.database.database import Base
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import Table, Column, Integer, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB

from backend.database.models.group import Group


class Elective(Base):
    __tablename__ = 'elective'

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str]
    modeus_link: Mapped[str] = mapped_column(nullable=True)
    description: Mapped[str] = mapped_column(nullable=True)
    text: Mapped[str] = mapped_column(nullable=True)
    questions: Mapped[str] = mapped_column(nullable=True)
    cluster: Mapped[str] = mapped_column(nullable=True)
    
    text_embed: Mapped[list[float]] = mapped_column(
        JSONB,
        nullable=True,
        comment="эмбеддинг описания курса (JSON-массив чисел)"
    )

    groups: Mapped[List["Group"]] = relationship(
        "Group",
        back_populates="elective",
    )

    def __str__(self):
        return f'{self.id} - {self.name}'

    def __repr__(self):
        return self.__str__()