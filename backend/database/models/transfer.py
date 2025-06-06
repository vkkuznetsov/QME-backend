from datetime import datetime
from typing import List
from enum import Enum

from sqlalchemy import ForeignKey, String, DateTime, Integer, Table, Column, Enum as SAEnum, and_
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from backend.database.database import Base


class TransferStatus(str, Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"


class GroupRole(Enum):
    TO = "to"
    FROM = "from"


transfer_group = Table(
    'transfer_group',
    Base.metadata,
    Column('transfer_id', Integer, ForeignKey('transfer.id', ondelete="CASCADE"), primary_key=True),
    Column('group_id', Integer, ForeignKey('group.id'), primary_key=True),
    Column('group_role', SAEnum(GroupRole), nullable=False)
)


class Transfer(Base):
    __tablename__ = 'transfer'

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    student_id: Mapped[int] = mapped_column(ForeignKey('student.id'), nullable=False)
    manager_id: Mapped[int | None] = mapped_column(ForeignKey('manager.id'), nullable=True)

    from_elective_id: Mapped[int] = mapped_column(ForeignKey('elective.id'), nullable=False)
    to_elective_id: Mapped[int] = mapped_column(ForeignKey('elective.id'), nullable=False)

    status: Mapped[TransferStatus] = mapped_column(SAEnum(TransferStatus), default=TransferStatus.pending)
    priority: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    # Отношения
    student: Mapped['Student'] = relationship('Student', back_populates='transfers')
    manager: Mapped['Manager'] = relationship('Manager', back_populates='transfers')

    from_elective: Mapped['Elective'] = relationship('Elective', foreign_keys=[from_elective_id])
    to_elective: Mapped['Elective'] = relationship('Elective', foreign_keys=[to_elective_id])

    groups_to: Mapped[List["Group"]] = relationship(
        "Group",
        secondary=transfer_group,
        primaryjoin=and_(transfer_group.c.transfer_id == id,
                         transfer_group.c.group_role == GroupRole.TO),
        secondaryjoin="Group.id == transfer_group.c.group_id",
        viewonly=True
    )

    groups_from: Mapped[List["Group"]] = relationship(
        "Group",
        secondary=transfer_group,
        primaryjoin=and_(transfer_group.c.transfer_id == id,
                         transfer_group.c.group_role == GroupRole.FROM),
        secondaryjoin="Group.id == transfer_group.c.group_id",
        viewonly=True
    )

    def __str__(self):
        return f'{self.id} {self.student_id} {self.from_elective_id} {self.to_elective_id} {self.priority}'

    def __repr__(self):
        return f'{self.id} {self.student_id} {self.from_elective_id} {self.to_elective_id} {self.priority}'
