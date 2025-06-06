from datetime import datetime
from sqlalchemy.orm import Mapped, mapped_column
from backend.database.database import Base
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.sql import func


class Log(Base):
    __tablename__ = "logs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )
    level: Mapped[str]  # info, error, warning, debug
    message: Mapped[str]
    source: Mapped[str]  # название модуля/компонента
