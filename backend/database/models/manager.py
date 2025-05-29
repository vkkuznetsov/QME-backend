from datetime import datetime

from backend.database.database import Base
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import DateTime, Enum
from sqlalchemy.sql import func


class Manager(Base):
    __tablename__ = 'manager'

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(nullable=False)
    status: Mapped[str] = mapped_column(Enum("active", "inactive", name="manager_status"), nullable=False)
   
    email: Mapped[str] = mapped_column(nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    def __str__(self):
        return f'{self.id} - {self.created_at}'

    def __repr__(self):
        return self.__str__()