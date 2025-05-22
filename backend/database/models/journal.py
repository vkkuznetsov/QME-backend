from datetime import datetime

from backend.database.database import Base
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import DateTime
from sqlalchemy.sql import func


class Journal(Base):
    __tablename__ = 'journal'

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    status: Mapped[str]
    type: Mapped[str]
    message: Mapped[str]
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    def __str__(self):
        return f'{self.id} - {self.created_at}'

    def __repr__(self):
        return self.__str__()