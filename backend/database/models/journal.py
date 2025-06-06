from datetime import datetime

from backend.database.database import Base
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import TIMESTAMP


class Journal(Base):
    __tablename__ = "journal"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    status: Mapped[str]
    type: Mapped[str]
    message: Mapped[str]
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )

    def __str__(self):
        return f"{self.id} - {self.created_at}"

    def __repr__(self):
        return self.__str__()
