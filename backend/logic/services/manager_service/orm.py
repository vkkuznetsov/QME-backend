from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.database import db_session
from backend.database.models.manager import Manager


class ManagerService:

    @db_session
    async def get_manager_by_email(self, email: str, db: AsyncSession):
        query = select(Manager).where(Manager.email == email).limit(1)
        student: Optional[Manager] = await db.scalar(query)
        return student

    @db_session
    async def get_all(self, db: AsyncSession):
        result = await db.execute(select(Manager).order_by(Manager.id))
        return result.scalars().all()

    @db_session
    async def add_manager(self, name: str, email: str, status: str, db: AsyncSession):
        manager = Manager(
            name=name,
            email=email,
            status=status
        )
        db.add(manager)
        await db.commit()
        await db.refresh(manager)
        return manager

    @db_session
    async def update_manager(self, manager_id: int, name: str, email: str, status: str, db: AsyncSession):
        if status not in ["active", "inactive"]:
            return {"error": "Invalid status"}
        manager = await db.get(Manager, manager_id)
        if manager is None:
            return {"error": "Manager not found"}
        manager.name = name
        manager.email = email
        manager.status = status
        await db.commit()
        await db.refresh(manager)
        return manager

    @db_session
    async def delete_manager(self, manager_id: int, db: AsyncSession):
        manager = await db.get(Manager, manager_id)
        if manager is None:
            return {"error": "Manager not found"}
        await db.delete(manager)
        await db.commit()
        return {"message": "Manager deleted"}
