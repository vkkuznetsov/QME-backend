from backend.database.database import Base
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import Integer, String


class Student(Base):
    __tablename__ = 'student'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, auto_increment=True)
    fio: Mapped[String] = mapped_column(String)
    email: Mapped[String] = mapped_column(String) # TODO под вопросом, мы оставляем что емейл строка или будем обрезать по stud0000265686@study.utmn.ru на 0000265686 и тогда можно инт юзать
    course: Mapped[String] = mapped_column(String)
