from typing import List

from backend.database.database import Base
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database.models.group import Group


class Elective(Base):
    __tablename__ = 'elective'

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str]
    groups: Mapped[List["Group"]] = relationship(
        back_populates="elective"
    )

    def __str__(self):
        return f'{self.id} - {self.name}'
