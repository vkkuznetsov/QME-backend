from backend.database.database import Base
from sqlalchemy.orm import Mapped, mapped_column


class Student(Base):
    __tablename__ = 'student'

    id: Mapped[int] = mapped_column(primary_key=True, auto_increment=True)
    fio: Mapped[str]
    email: Mapped[str]
    course: Mapped[str]
