from typing import List

from sqlalchemy import ForeignKey

from backend.database.database import Base
from sqlalchemy.orm import Mapped, mapped_column, relationship


class Group(Base):
    __tablename__ = 'group'

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str]
    type: Mapped[str]
    capacity: Mapped[int]

    elective_id: Mapped[int] = mapped_column(ForeignKey("elective.id"))
    elective: Mapped["Elective"] = relationship(
        back_populates="groups"
    )

    students: Mapped[List["Student"]] = relationship(
        back_populates="groups", secondary="student_group"
    )

    def __str__(self):
        return f'{self.id} - {self.name} - {self.type}'
