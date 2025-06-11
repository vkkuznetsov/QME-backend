from typing import List

from sqlalchemy import ForeignKey, and_, Table, Column

from backend.database.database import Base
from backend.database.models.transfer import transfer_group, GroupRole
from sqlalchemy.orm import Mapped, mapped_column, relationship

group_teacher = Table(
    "group_teacher",
    Base.metadata,
    Column("group_id", ForeignKey("group.id"), primary_key=True),
    Column("teacher_id", ForeignKey("teacher.id"), primary_key=True),
)


class Teacher(Base):
    __tablename__ = "teacher"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    fio: Mapped[str] = mapped_column(nullable=False)

    groups: Mapped[List["Group"]] = relationship(
        "Group", secondary=group_teacher, back_populates="teachers"
    )


class Group(Base):
    __tablename__ = "group"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str]
    type: Mapped[str] = mapped_column(nullable=True)

    teachers: Mapped[List["Teacher"]] = relationship(
        "Teacher", secondary=group_teacher, back_populates="groups"
    )

    capacity: Mapped[int] = mapped_column(nullable=True)

    day: Mapped[str] = mapped_column(nullable=True)
    time_interval: Mapped[str] = mapped_column(nullable=True)
    free_spots: Mapped[int] = mapped_column(nullable=True)
    init_usage: Mapped[int] = mapped_column(nullable=True)

    elective_id: Mapped[int] = mapped_column(ForeignKey("elective.id"), nullable=True)
    elective: Mapped["Elective"] = relationship(back_populates="groups")

    students: Mapped[List["Student"]] = relationship(
        back_populates="groups", secondary="student_group"
    )

    # Трансферы В группу
    transfers_to: Mapped[List["Transfer"]] = relationship(
        "Transfer",
        secondary=transfer_group,
        primaryjoin=and_(
            transfer_group.c.group_id == id, transfer_group.c.group_role == GroupRole.TO
        ),
        secondaryjoin="Transfer.id == transfer_group.c.transfer_id",
        viewonly=True,
    )
    # Трансферы которые ОТПИСЫВАЮТСЯ из группы
    transfers_from: Mapped[List["Transfer"]] = relationship(
        "Transfer",
        secondary=transfer_group,
        primaryjoin=and_(
            transfer_group.c.group_id == id,
            transfer_group.c.group_role == GroupRole.FROM,
        ),
        secondaryjoin="Transfer.id == transfer_group.c.transfer_id",
        viewonly=True,
    )

    def __str__(self):
        return f"{self.id} - {self.name} - {self.type} - {self.students}"

    def __repr__(self):
        return f"{self.id} - {self.name} - {self.type} - {self.students}"
