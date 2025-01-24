from datetime import datetime
from sqlalchemy import ForeignKey, String, DateTime, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from backend.database.database import Base


class Transfer(Base):
    __tablename__ = 'transfer'

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    student_id: Mapped[int] = mapped_column(ForeignKey('student.id'), nullable=False)

    to_lecture_group_id: Mapped[int] = mapped_column(ForeignKey('group.id'), nullable=True)
    to_practice_group_id: Mapped[int] = mapped_column(ForeignKey('group.id'), nullable=True)
    to_lab_group_id: Mapped[int] = mapped_column(ForeignKey('group.id'), nullable=True)
    to_consultation_group_id: Mapped[int] = mapped_column(ForeignKey('group.id'), nullable=True)

    from_elective_id: Mapped[int] = mapped_column(ForeignKey('elective.id'), nullable=False)
    to_elective_id: Mapped[int] = mapped_column(ForeignKey('elective.id'), nullable=False)

    status: Mapped[str] = mapped_column(String, default='pending')
    priority: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    # Отношения
    student: Mapped['Student'] = relationship('Student', back_populates='transfers')

    from_lecture_group: Mapped['Group'] = relationship('Group', foreign_keys=[to_lecture_group_id])
    from_practice_group: Mapped['Group'] = relationship('Group', foreign_keys=[to_practice_group_id])
    from_lab_group: Mapped['Group'] = relationship('Group', foreign_keys=[to_lab_group_id])
    from_consultation_group: Mapped['Group'] = relationship('Group', foreign_keys=[to_consultation_group_id])

    from_elective: Mapped['Elective'] = relationship('Elective', foreign_keys=[from_elective_id])
    to_elective: Mapped['Elective'] = relationship('Elective', foreign_keys=[to_elective_id])