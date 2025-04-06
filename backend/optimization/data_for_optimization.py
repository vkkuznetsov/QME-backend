from dataclasses import dataclass
from typing import Sequence

import pandas as pd
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.database import db_session
from backend.database.models import Group
from backend.database.models.transfer import GroupRole, Transfer, transfer_group


@dataclass
class DataGetter:

    async def __call__(self):
        transfers = await self.get_all_transfers_with_pending_status()
        transfer_groups = await self.get_transfer_groups()
        groups = await self.get_groups()
        group_info, list_of_requests = self.prepare_request_structs_db(transfers,transfer_groups, groups)
        return group_info, list_of_requests

    # ------------------------- Запросы к БД -------------------------
    @db_session
    async def get_all_transfers_with_pending_status(self, db: AsyncSession) -> Sequence[Transfer]:
        result = await db.execute(
            select(Transfer)
            .where(Transfer.status == 'pending')
        )
        transfers = result.scalars().all()
        return transfers

    @db_session
    async def get_transfer_groups(self, db: AsyncSession) -> Sequence:
        """
        Ожидается, что transfer_group – это таблица-связка с колонками:
          request_id, group_id, group_role
        """
        result = await db.execute(
            select(
                transfer_group.c.transfer_id,
                transfer_group.c.group_id,
                transfer_group.c.group_role
            )
        )
        transfer_groups = result.all()
        return transfer_groups

    @db_session
    async def get_groups(self, db: AsyncSession) -> Sequence[Group]:
        result = await db.execute(
            select(Group)
        )
        groups = result.scalars().all()
        return groups

    # ------------------------- Подготовка структур -------------------------
    def prepare_request_structs_db(
            self,
            transfers: Sequence[Transfer],
            transfer_groups: Sequence,
            groups: Sequence[Group]
    ):
        """
        Формирует структуры:
          1) group_info[group_id] = {
               'elective_id': ...,
               'name': ...,
               'capacity': ...,
               'init_usage': ...
             }
          2) Список заявок (list_of_requests), где каждая заявка – dict:
             {
               'r_id': int,
               'student_id': int,
               'from_elective_id': int,
               'to_elective_id': int,
               'priority': int,
               'created_at': pd.Timestamp,
               'from_groups': [list of group_ids],
               'to_groups':   [list of group_ids]
             }
        """
        # 1) Формируем словарь групп
        group_info = {}
        for group in groups:
            group_info[group.id] = {
                'elective_id': int(group.elective_id),
                'name': str(group.name),
                'capacity': int(group.capacity),
                'init_usage': int(getattr(group, 'init_usage', 0))
            }

        # 2) Строим словари связей для каждой заявки
        from_dict = {}
        to_dict = {}
        for row in transfer_groups:
            r_id = row.request_id if hasattr(row, 'request_id') else row.transfer_id
            g_id = row.group_id if hasattr(row, 'group_id') else row.group_id
            role = row.group_role if hasattr(row, 'group_role') else row.group_role
            if role == GroupRole.FROM:
                from_dict.setdefault(r_id, []).append(g_id)
            elif role == GroupRole.TO:
                to_dict.setdefault(r_id, []).append(g_id)

        list_of_requests = []
        for transfer in transfers:
            rid = transfer.id
            list_of_requests.append({
                'r_id': rid,
                'student_id': int(transfer.student_id),
                'from_elective_id': int(transfer.from_elective_id),
                'to_elective_id': int(transfer.to_elective_id),
                'priority': int(transfer.priority),
                'created_at': pd.to_datetime(transfer.created_at),
                'from_groups': from_dict.get(rid, []),
                'to_groups': to_dict.get(rid, [])
            })

        return group_info, list_of_requests
