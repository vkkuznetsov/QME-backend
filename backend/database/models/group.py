from typing import List

from sqlalchemy import ForeignKey, and_

from backend.database.database import Base
from backend.database.models.transfer import transfer_group, GroupRole
from sqlalchemy.orm import Mapped, mapped_column, relationship


class Group(Base):
    __tablename__ = 'group'

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str]
    type: Mapped[str]

    capacity: Mapped[int]

    day: Mapped[str] = mapped_column(nullable=True)
    time_interval: Mapped[str] = mapped_column(nullable=True)
    free_spots: Mapped[int] = mapped_column(nullable=True)

    elective_id: Mapped[int] = mapped_column(ForeignKey("elective.id"))
    elective: Mapped["Elective"] = relationship(
        back_populates="groups"
    )

    students: Mapped[List["Student"]] = relationship(
        back_populates="groups", secondary="student_group"
    )

    # Трансферы В группу
    transfers_to: Mapped[List["Transfer"]] = relationship(
        "Transfer",
        secondary=transfer_group,
        primaryjoin=and_(transfer_group.c.group_id == id,
                         transfer_group.c.group_role == GroupRole.TO),
        secondaryjoin="Transfer.id == transfer_group.c.transfer_id",
        viewonly=True
    )
    # Трансферы которые ОТПИСЫВАЮТСЯ из группы
    transfers_from: Mapped[List["Transfer"]] = relationship(
        "Transfer",
        secondary=transfer_group,
        primaryjoin=and_(transfer_group.c.group_id == id,
                         transfer_group.c.group_role == GroupRole.FROM),
        secondaryjoin="Transfer.id == transfer_group.c.transfer_id",
        viewonly=True
    )

    def __str__(self):
        return f'{self.id} - {self.name} - {self.type} - {self.students}'

    def __repr__(self):
        return f'{self.id} - {self.name} - {self.type} - {self.students}'
