from typing import List

from backend.database.database import Base
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import Table, Column, Integer, ForeignKey


class Student(Base):
    __tablename__ = 'student'

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    fio: Mapped[str]
    email: Mapped[str]
    sp_code: Mapped[str]
    sp_profile: Mapped[str]
    potok: Mapped[str]

    groups: Mapped[List["Group"]] = relationship(
        back_populates="students", secondary="student_group"
    )
    transfers: Mapped[List["Transfer"]] = relationship('Transfer', back_populates='student')

    def __str__(self):
        return f'{self.id} - {self.fio} - {self.email}'

    def __repr__(self):
        return f'{self.id} - {self.fio} - {self.email}'


student_group = Table(
    'student_group',
    Base.metadata,
    Column('student_id', Integer, ForeignKey('student.id'), primary_key=True),
    Column('group_id', Integer, ForeignKey('group.id'), primary_key=True),
)
