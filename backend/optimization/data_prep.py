import asyncio
import time
import math
import pandas as pd
import pulp
from typing import List, Dict, Sequence

from backend.database.database import db_session
from backend.database.models import Group
from backend.database.models.transfer import Transfer, transfer_group, GroupRole
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select


# Запросы к БД, возвращающие данные для оптимизации

@db_session
async def get_all_transfers_with_pending_status(db: AsyncSession) -> Sequence[Transfer]:
    result = await db.execute(
        select(Transfer)
        .where(Transfer.status == 'pending')
    )
    transfers = result.scalars().all()
    return transfers


@db_session
async def get_transfer_groups(db: AsyncSession) -> Sequence:
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
async def get_groups(db: AsyncSession) -> Sequence[Group]:
    result = await db.execute(
        select(Group)
    )
    groups = result.scalars().all()
    return groups


# Функция для подготовки структур из данных БД, аналогичных тем, что строились из CSV
def prepare_request_structs_db(
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
           'priority': float,
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


def solve_ilp(group_info: Dict[int, dict], requests_list: List[dict]):
    """
    Решает задачу целочисленного программирования.
    Если для одной пары (student_id, from_elective_id) принимается заявка,
    то все остальные для этой пары автоматически отклоняются.
    """
    if not requests_list:
        return {
            'status': 'NoRequests',
            'objective': 0.0,
            'accepted': [],
            'time_s': 0.0
        }

    capacity_map = {}
    usage_map = {}
    for g_id, info in group_info.items():
        capacity_map[g_id] = info['capacity']
        usage_map[g_id] = info['init_usage']

    # Определяем максимальную дату создания заявок
    ctimes = [r['created_at'] for r in requests_list]
    max_date = max(ctimes) if ctimes else pd.Timestamp('2025-01-01')
    day_in_sec = 24 * 3600
    time_scale = 0.1 / day_in_sec

    model = pulp.LpProblem('Elective_Reassign_ILP', pulp.LpMaximize)

    # Переменные: accept_vars[rid] = 1, если заявка r принимается
    accept_vars = {}
    for rq in requests_list:
        rid = rq['r_id']
        accept_vars[rid] = pulp.LpVariable(f'accept_{rid}', cat=pulp.LpBinary)

    # Целевая функция
    obj_terms = []
    for rq in requests_list:
        rid = rq['r_id']
        p = rq['priority']
        dt_seconds = (max_date - rq['created_at']).total_seconds()
        secondary = dt_seconds * time_scale
        if not math.isfinite(secondary):
            secondary = 0
        if not math.isfinite(p):
            p = 0
        total_val = (6 - p) + secondary
        obj_terms.append(total_val * accept_vars[rid])
    model += pulp.lpSum(obj_terms), 'MaxPriorityTime'

    # Ограничения по вместимости групп:
    group_to_in_requests = {g_id: [] for g_id in group_info.keys()}
    group_to_out_requests = {g_id: [] for g_id in group_info.keys()}

    for rq in requests_list:
        rid = rq['r_id']
        for g_out in rq['from_groups']:
            group_to_out_requests.setdefault(g_out, []).append(rid)
        for g_in in rq['to_groups']:
            group_to_in_requests.setdefault(g_in, []).append(rid)

    for g_id in group_info.keys():
        init_u = usage_map[g_id]
        in_expr = pulp.lpSum([accept_vars[rid] for rid in group_to_in_requests.get(g_id, [])])
        out_expr = pulp.lpSum([accept_vars[rid] for rid in group_to_out_requests.get(g_id, [])])
        cap = capacity_map[g_id]
        model += (init_u + in_expr - out_expr <= cap), f'Capacity_{g_id}'

    # Дополнительное ограничение:
    # Для каждой пары (student_id, from_elective_id) суммарно может быть принято не более одной заявки.
    from collections import defaultdict
    student_elective_requests = defaultdict(list)
    for rq in requests_list:
        key = (rq['student_id'], rq['from_elective_id'])
        student_elective_requests[key].append(rq['r_id'])

    for key, rids in student_elective_requests.items():
        model += pulp.lpSum([accept_vars[rid] for rid in rids]) <= 1, \
                 f"UniqueRequest_student_{key[0]}_elective_{key[1]}"

    start_t = time.time()
    model.solve(pulp.PULP_CBC_CMD(msg=0))
    end_t = time.time()

    status = pulp.LpStatus[model.status]
    objective_val = pulp.value(model.objective)

    accepted = []
    for rq in requests_list:
        rid = rq['r_id']
        val = pulp.value(accept_vars[rid])
        if val is not None and val > 0.5:
            accepted.append(rid)

    return {
        'status': status,
        'objective': objective_val,
        'accepted': accepted,
        'time_s': (end_t - start_t)
    }



def solve_greedy(group_info: Dict[int, dict], requests_list: List[dict]):
    """
    Простейшая эвристика для выбора заявок с ограничением:
    для каждой пары (student_id, from_elective_id) можно принять не более одной заявки.
    """
    if not requests_list:
        return {
            'status': 'NoRequests',
            'objective': 0.0,
            'accepted': [],
            'time_s': 0.0
        }

    def sort_key(rq):
        return (rq['priority'], rq['created_at'])

    sorted_requests = sorted(requests_list, key=sort_key)

    capacity_map = {}
    usage_map = {}
    for g_id, info in group_info.items():
        capacity_map[g_id] = info['capacity']
        usage_map[g_id] = info['init_usage']

    accepted = []
    accepted_pairs = set()  # для хранения пар (student_id, from_elective_id)
    total_priority = 0.0
    start_t = time.time()

    for rq in sorted_requests:
        pair = (rq['student_id'], rq['from_elective_id'])
        # Если для данной пары уже принята заявка, пропускаем текущую
        if pair in accepted_pairs:
            continue

        rid = rq['r_id']
        p = rq['priority']
        from_gr = rq['from_groups']
        to_gr = rq['to_groups']

        can_accept = True
        for g_in in to_gr:
            if g_in not in capacity_map:
                continue
            new_u = usage_map[g_in] + 1
            if new_u > capacity_map[g_in]:
                can_accept = False
                break
        if can_accept:
            for g_in in to_gr:
                if g_in in usage_map:
                    usage_map[g_in] += 1
            for g_out in from_gr:
                if g_out in usage_map:
                    usage_map[g_out] -= 1
                    if usage_map[g_out] < 0:
                        usage_map[g_out] = 0
            accepted.append(rid)
            total_priority += p
            accepted_pairs.add(pair)

    end_t = time.time()
    return {
        'status': 'Heuristic',
        'objective': total_priority,
        'accepted': accepted,
        'time_s': (end_t - start_t)
    }



def compare_methods_db(
        transfers: Sequence[Transfer],
        transfer_groups: Sequence,
        groups: Sequence[Group]
):
    """
    Подготавливает структуры из БД и запускает ILP и Greedy алгоритмы.
    """
    print("=== Шаг 1. Подготовка структур из БД ===")
    group_info, list_of_requests = prepare_request_structs_db(transfers, transfer_groups, groups)
    print(f"Всего групп = {len(group_info)}, заявок = {len(list_of_requests)}")

    print("\n=== Шаг 2. ILP-решение ===")
    ilp_res = solve_ilp(group_info, list_of_requests)
    print("ILP Status  =", ilp_res['status'])
    print("ILP Objective =", ilp_res['objective'])
    print("ILP Time (s)  =", ilp_res['time_s'])
    print("ILP Accepted  =", ilp_res['accepted'])

    print("\n=== Шаг 3. Greedy ===")
    greedy_res = solve_greedy(group_info, list_of_requests)
    print("Greedy Status  =", greedy_res['status'])
    print("Greedy Objective =", greedy_res['objective'])
    print("Greedy Time (s)  =", greedy_res['time_s'])
    print("Greedy Accepted  =", greedy_res['accepted'])

    return {'ilp': ilp_res, 'greedy': greedy_res}


async def main() -> None:
    transfers = await get_all_transfers_with_pending_status()
    t_groups = await get_transfer_groups()
    groups = await get_groups()

    result = compare_methods_db(transfers, t_groups, groups)
    print("\nИтоговое сравнение:\n", result)


if __name__ == '__main__':
    asyncio.run(main())
