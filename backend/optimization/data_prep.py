import asyncio
from backend.database.database import db_session
from backend.database.models import Group
from backend.database.models.transfer import Transfer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload


@db_session
async def get_all_transfers_with_pending_status(db: AsyncSession) -> None:
    result = await db.execute(
        select(Transfer)
        .where(Transfer.status == 'pending')
    )
    transfers = result.scalars().all()
    print(transfers)


@db_session
async def get_all_groups_and_students(db: AsyncSession) -> None:
    result = await db.execute(
        select(Group)
        .options(
            selectinload(Group.students)
        ))
    group_and_students = result.scalars().all()
    print(group_and_students)


async def main() -> None:
    await get_all_transfers_with_pending_status()
    await get_all_groups_and_students()


if __name__ == '__main__':
    asyncio.run(main())
