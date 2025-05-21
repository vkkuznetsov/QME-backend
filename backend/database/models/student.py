from typing import List

from backend.database.database import Base
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import Table, Column, Integer, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from pgvector.sqlalchemy import Vector

from backend.database.models.group import Group


class Student(Base):
    __tablename__ = 'student'

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    fio: Mapped[str]
    email: Mapped[str]
    sp_code: Mapped[str]
    sp_profile: Mapped[str]
    potok: Mapped[str]

    competencies: Mapped[list[float]] = mapped_column(
        Vector(7),
        nullable=True,
        comment="h1–h8 в предсказуемом порядке"
    )

    diagnostics: Mapped[dict] = mapped_column(
        JSONB,
        nullable=True,
        comment="три балла из листа «Контингент»"
    )

    text_embed: Mapped[list[float]] = mapped_column(
        Vector(384),
        nullable=True,
        comment="общий профиль студента"
    )

    groups: Mapped[List["Group"]] = relationship(
        "Group",
        back_populates="students",
        secondary="student_group"
    )
    transfers: Mapped[List["Transfer"]] = relationship(
        "Transfer",
        back_populates="student"
    )

    def __str__(self):
        return f'{self.id} - {self.fio} - {self.email}'

    def __repr__(self):
        return self.__str__()


student_group = Table(
    'student_group',
    Base.metadata,
    Column('student_id', Integer, ForeignKey('student.id'), primary_key=True),
    Column('group_id', Integer, ForeignKey('group.id'), primary_key=True),
)