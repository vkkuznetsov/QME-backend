from datetime import datetime
from sqlalchemy.orm import Mapped, mapped_column
from backend.database.database import Base
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.sql import func

class Report(Base):
    __tablename__ = 'reports'

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    report_type: Mapped[str]  # тип отчета (student_transfers, elective_statistics, manager_actions)
    status: Mapped[str]  # generating, completed, failed
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        nullable=False
    )
    download_url: Mapped[str | None]  # URL для скачивания отчета 