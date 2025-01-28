from datetime import datetime
from sqlalchemy import ForeignKey, String, DateTime, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from backend.database.database import Base


class Transfer(Base):
    __tablename__ = 'transfer'

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    student_id: Mapped[int | None] = mapped_column(ForeignKey('student.id'))

    from_elective_id: Mapped[int] = mapped_column(ForeignKey('elective.id'))
    to_elective_id: Mapped[int] = mapped_column(ForeignKey('elective.id'))

    status: Mapped[str] = mapped_column(String, default='pending')
    priority: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    # Отношения
    student: Mapped['Student'] = relationship('Student', back_populates='transfers')

    groups: Mapped[list["Group"]] = relationship(secondary="transfer_group", back_populates="transfers")

    from_elective: Mapped["Elective"] = relationship(foreign_keys="[Transfer.from_elective_id]")
    to_elective: Mapped["Elective"] = relationship(foreign_keys="[Transfer.to_elective_id]")


class TransferGroup(Base):
    __tablename__ = 'transfer_group'

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    transfer_id: Mapped[int] = mapped_column(ForeignKey('transfer.id'))
    group_id: Mapped[int] = mapped_column(ForeignKey('group.id'))
