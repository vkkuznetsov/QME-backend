from abc import ABC, abstractmethod


class IStudentService(ABC):
    @abstractmethod
    async def get_student_by_email(self, student_email):
        ...


if __name__ == '__main__':
    import asyncio


    async def main():
        res = await ORMStudentService().get_student_by_email('vita.201581@yandex.ru')


    asyncio.run(main())
