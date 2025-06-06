from datetime import datetime
from backend.database.database import Base

from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import TIMESTAMP


class Manager(Base):
    __tablename__ = 'manager'

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(nullable=False)
    status: Mapped[str] = mapped_column(nullable=False)
   
    email: Mapped[str] = mapped_column(nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        nullable=False
    )

    transfers = relationship("Transfer", back_populates="manager")

    def __str__(self):
        return f'{self.id} - {self.created_at}'

    def __repr__(self):
        return self.__str__()