import asyncio
import time
import math
import random
import pandas as pd
import pulp
from typing import List, Dict, Sequence

from backend.database.database import db_session
from backend.database.models import Group
from backend.database.models.transfer import Transfer, transfer_group, GroupRole
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select


# ------------------------- Запросы к БД -------------------------
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


# ------------------------- Подготовка структур -------------------------
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


# ------------------------- ILP и Greedy (как у вас) -------------------------
def solve_ilp(group_info: Dict[int, dict], requests_list: List[dict]):
    if not requests_list:
        return {'status': 'NoRequests', 'objective': 0.0, 'accepted': [], 'time_s': 0.0}

    capacity_map = {g_id: info['capacity'] for g_id, info in group_info.items()}
    usage_map = {g_id: info['init_usage'] for g_id, info in group_info.items()}

    ctimes = [r['created_at'] for r in requests_list]
    max_date = max(ctimes) if ctimes else pd.Timestamp('2025-01-01')
    day_in_sec = 24 * 3600
    time_scale = 0.1 / day_in_sec

    model = pulp.LpProblem('Elective_Reassign_ILP', pulp.LpMaximize)
    accept_vars = {}
    for rq in requests_list:
        rid = rq['r_id']
        accept_vars[rid] = pulp.LpVariable(f'accept_{rid}', cat=pulp.LpBinary)

    obj_terms = []
    for rq in requests_list:
        rid = rq['r_id']
        p = rq['priority']
        dt_seconds = (max_date - rq['created_at']).total_seconds()
        secondary = dt_seconds * time_scale if math.isfinite(dt_seconds) else 0
        total_val = (6 - p) + secondary
        obj_terms.append(total_val * accept_vars[rid])
    model += pulp.lpSum(obj_terms), 'MaxPriorityTime'

    group_to_in_requests = {g_id: [] for g_id in group_info.keys()}
    group_to_out_requests = {g_id: [] for g_id in group_info.keys()}
    for rq in requests_list:
        rid = rq['r_id']
        for g_out in rq['from_groups']:
            group_to_out_requests.setdefault(g_out, []).append(rid)
        for g_in in rq['to_groups']:
            group_to_in_requests.setdefault(g_in, []).append(rid)
    # Определяем, какие группы реально участвуют в заявках
    groups_involved = set()
    for rq in requests_list:
        groups_involved.update(rq['from_groups'])
        groups_involved.update(rq['to_groups'])

    # Ограничения по вместимости считаем только для участвующих групп
    for g_id in groups_involved:
        init_u = usage_map[g_id]
        in_expr = pulp.lpSum([accept_vars[rid] for rid in group_to_in_requests.get(g_id, [])])
        out_expr = pulp.lpSum([accept_vars[rid] for rid in group_to_out_requests.get(g_id, [])])
        model += (init_u + in_expr - out_expr <= capacity_map[g_id]), f'Capacity_{g_id}'

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

    accepted = [rq['r_id'] for rq in requests_list if pulp.value(accept_vars[rq['r_id']]) and pulp.value(accept_vars[rq['r_id']]) > 0.5]
    return {
        'status': pulp.LpStatus[model.status],
        'objective': pulp.value(model.objective),
        'accepted': accepted,
        'time_s': (end_t - start_t)
    }


def solve_greedy(group_info: Dict[int, dict], requests_list: List[dict]):
    if not requests_list:
        return {'status': 'NoRequests', 'objective': 0.0, 'accepted': [], 'time_s': 0.0}

    def sort_key(rq):
        return (rq['priority'], rq['created_at'])
    sorted_requests = sorted(requests_list, key=sort_key)

    capacity_map = {g_id: info['capacity'] for g_id, info in group_info.items()}
    usage_map = {g_id: info['init_usage'] for g_id, info in group_info.items()}

    accepted = []
    accepted_pairs = set()
    total_priority = 0.0
    start_t = time.time()

    for rq in sorted_requests:
        pair = (rq['student_id'], rq['from_elective_id'])
        if pair in accepted_pairs:
            continue
        rid = rq['r_id']
        p = rq['priority']
        from_gr = rq['from_groups']
        to_gr = rq['to_groups']
        can_accept = True
        for g_in in to_gr:
            if usage_map.get(g_in, 0) + 1 > capacity_map.get(g_in, 0):
                can_accept = False
                break
        if can_accept:
            for g_in in to_gr:
                usage_map[g_in] = usage_map.get(g_in, 0) + 1
            for g_out in from_gr:
                usage_map[g_out] = max(usage_map.get(g_out, 0) - 1, 0)
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


# ------------------------- Функция ремонта решения -------------------------
def repair_solution(solution: Dict[int, int], requests_list: List[dict], group_info: Dict[int, dict]) -> Dict[int, int]:
    """
    Функция корректирует решение так, чтобы:
      1. Для каждой пары (student_id, from_elective_id) оставалась только одна принятая заявка.
      2. Вместимость групп не превышалась.
    """
    # Подготовим словари для удобства
    # Копируем решение
    new_solution = solution.copy()

    # 1. Ограничение уникальности: для каждой пары оставляем заявку с наилучшей ценностью
    best_for_pair = {}
    for rq in requests_list:
        rid = rq['r_id']
        if new_solution[rid] == 1:
            key = (rq['student_id'], rq['from_elective_id'])
            # Рассчитаем вклад заявки: (6 - priority) + бонус по времени
            bonus = 0  # можно добавить бонус, если нужно
            value = (6 - rq['priority']) + bonus
            if key not in best_for_pair or value > best_for_pair[key][1]:
                best_for_pair[key] = (rid, value)
    # Оставляем только лучшую заявку для каждой пары
    for rq in requests_list:
        rid = rq['r_id']
        key = (rq['student_id'], rq['from_elective_id'])
        if new_solution[rid] == 1:
            if key in best_for_pair and best_for_pair[key][0] != rid:
                new_solution[rid] = 0

    # 2. Ограничение вместимости групп
    capacity_map = {g_id: info['capacity'] for g_id, info in group_info.items()}
    init_usage = {g_id: info['init_usage'] for g_id, info in group_info.items()}

    # Рассчитаем текущее использование групп
    usage = init_usage.copy()
    for rq in requests_list:
        if new_solution[rq['r_id']] == 1:
            for g in rq['to_groups']:
                usage[g] = usage.get(g, 0) + 1
            for g in rq['from_groups']:
                usage[g] = usage.get(g, 0) - 1

    # Для каждой группы, где использование превышает вместимость, будем отказываться от заявок
    for g_id in capacity_map:
        while usage.get(g_id, 0) > capacity_map[g_id]:
            # Среди заявок, влияющих на группу (те, что добавляют использование в g_id), выберем одну с наименьшим вкладом
            candidates = [rq for rq in requests_list if new_solution[rq['r_id']] == 1 and g_id in rq['to_groups']]
            if not candidates:
                break
            # Выбираем заявку с минимальным значением (6 - priority)
            worst = min(candidates, key=lambda rq: (6 - rq['priority']))
            new_solution[worst['r_id']] = 0
            # Обновляем использование для всех групп, затронутых этой заявкой
            for g in worst['to_groups']:
                usage[g] -= 1
            for g in worst['from_groups']:
                usage[g] += 1

    return new_solution


# ------------------------- Эвристика: Имитация отжига -------------------------
def solve_simulated_annealing(group_info: Dict[int, dict], requests_list: List[dict],
                              iterations: int = 1000, initial_temp: float = 100.0, cooling_rate: float = 0.99):
    if not requests_list:
        return {'status': 'NoRequests', 'objective': 0.0, 'accepted': [], 'time_s': 0.0}

    capacity_map = {g_id: info['capacity'] for g_id, info in group_info.items()}
    init_usage = {g_id: info['init_usage'] for g_id, info in group_info.items()}
    ctimes = [r['created_at'] for r in requests_list]
    max_date = max(ctimes) if ctimes else pd.Timestamp('2025-01-01')
    day_in_sec = 24 * 3600
    time_scale = 0.1 / day_in_sec

    def objective(solution: Dict[int, int]) -> float:
        total = 0.0
        for rq in requests_list:
            if solution[rq['r_id']] == 1:
                total += (6 - rq['priority'])
        return total

    # Начинаем с нулевого решения
    current_solution = {rq['r_id']: 0 for rq in requests_list}
    current_solution = repair_solution(current_solution, requests_list, group_info)
    current_obj = objective(current_solution)
    best_solution = current_solution.copy()
    best_obj = current_obj

    temp = initial_temp
    start_t = time.time()
    for i in range(iterations):
        new_solution = current_solution.copy()
        # Меняем состояние случайной заявки
        rq = random.choice(requests_list)
        new_solution[rq['r_id']] = 1 - new_solution[rq['r_id']]
        # Ремонтируем решение
        new_solution = repair_solution(new_solution, requests_list, group_info)
        new_obj = objective(new_solution)
        delta = new_obj - current_obj
        if delta > 0 or random.random() < math.exp(delta / temp):
            current_solution = new_solution
            current_obj = new_obj
            if new_obj > best_obj:
                best_solution = new_solution.copy()
                best_obj = new_obj
        temp *= cooling_rate
    accepted = [rid for rid, val in best_solution.items() if val == 1]
    end_t = time.time()
    return {
        'status': 'SimulatedAnnealing',
        'objective': best_obj,
        'accepted': accepted,
        'time_s': (end_t - start_t)
    }


# ------------------------- Эвристика: Генетический алгоритм -------------------------
def solve_genetic(group_info: Dict[int, dict], requests_list: List[dict],
                  population_size: int = 50, generations: int = 100, mutation_rate: float = 0.1):
    if not requests_list:
        return {'status': 'NoRequests', 'objective': 0.0, 'accepted': [], 'time_s': 0.0}

    capacity_map = {g_id: info['capacity'] for g_id, info in group_info.items()}
    init_usage = {g_id: info['init_usage'] for g_id, info in group_info.items()}
    ctimes = [r['created_at'] for r in requests_list]
    max_date = max(ctimes) if ctimes else pd.Timestamp('2025-01-01')
    day_in_sec = 24 * 3600
    time_scale = 0.1 / day_in_sec

    def objective(solution: Dict[int, int]) -> float:
        total = 0.0
        for rq in requests_list:
            if solution[rq['r_id']] == 1:
                bonus = 0
                total += (6 - rq['priority']) + bonus
        return total

    def fitness(solution: Dict[int, int]) -> float:
        # Если решение недопустимо, возвращаем очень низкий показатель
        repaired = repair_solution(solution, requests_list, group_info)
        if repaired != solution:
            return -1e9
        return objective(solution)

    def random_solution() -> Dict[int, int]:
        sol = {rq['r_id']: random.choice([0, 1]) for rq in requests_list}
        return repair_solution(sol, requests_list, group_info)

    # Создаём начальную популяцию
    population = [random_solution() for _ in range(population_size)]
    best_solution = max(population, key=fitness)
    best_fit = fitness(best_solution)
    start_t = time.time()
    for gen in range(generations):
        pop_fitness = [max(fitness(sol), 0) for sol in population]  # используем только положительные фитнесы
        total_fit = sum(pop_fitness)
        if total_fit == 0:
            selected = random.choices(population, k=population_size)
        else:
            selected = random.choices(population, weights=pop_fitness, k=population_size)
        next_population = []
        for i in range(0, population_size, 2):
            parent1 = selected[i]
            parent2 = selected[(i+1) % population_size]
            crossover_point = random.randint(1, len(requests_list) - 1)
            keys = [rq['r_id'] for rq in requests_list]
            child1 = {}
            child2 = {}
            for j, key in enumerate(keys):
                if j < crossover_point:
                    child1[key] = parent1[key]
                    child2[key] = parent2[key]
                else:
                    child1[key] = parent2[key]
                    child2[key] = parent1[key]
            child1 = repair_solution(child1, requests_list, group_info)
            child2 = repair_solution(child2, requests_list, group_info)
            next_population.extend([child1, child2])
        # Мутация
        for sol in next_population:
            if random.random() < mutation_rate:
                key = random.choice([rq['r_id'] for rq in requests_list])
                sol[key] = 1 - sol[key]
                sol = repair_solution(sol, requests_list, group_info)
        population = next_population
        current_best = max(population, key=fitness)
        current_fit = fitness(current_best)
        if current_fit > best_fit:
            best_solution = current_best.copy()
            best_fit = current_fit
    accepted = [rid for rid, val in best_solution.items() if val == 1]
    end_t = time.time()
    return {
        'status': 'Genetic',
        'objective': best_fit,
        'accepted': accepted,
        'time_s': (end_t - start_t)
    }


# ------------------------- Сравнение методов -------------------------
def compare_methods_db(
        transfers: Sequence[Transfer],
        transfer_groups: Sequence,
        groups: Sequence[Group]
):
    print("=== Шаг 1. Подготовка структур из БД ===")
    group_info, list_of_requests = prepare_request_structs_db(transfers, transfer_groups, groups)
    print(f"Всего групп = {len(group_info)}, заявок = {len(list_of_requests)}")

    print("\n=== Шаг 2. ILP-решение ===")
    ilp_res = solve_ilp(group_info, list_of_requests)
    print("ILP Status  =", ilp_res['status'])
    print("ILP Objective =", ilp_res['objective'])
    print("ILP Time (s)  =", ilp_res['time_s'])
    print("ILP Accepted  =", ilp_res['accepted'])

    print("\n=== Шаг 3. Жадный алгоритм (Greedy) ===")
    greedy_res = solve_greedy(group_info, list_of_requests)
    print("Greedy Status  =", greedy_res['status'])
    print("Greedy Objective =", greedy_res['objective'])
    print("Greedy Time (s)  =", greedy_res['time_s'])
    print("Greedy Accepted  =", greedy_res['accepted'])

    print("\n=== Шаг 4. Имитация отжига (Simulated Annealing) ===")
    sa_res = solve_simulated_annealing(group_info, list_of_requests)
    print("SA Status     =", sa_res['status'])
    print("SA Objective  =", sa_res['objective'])
    print("SA Time (s)   =", sa_res['time_s'])
    print("SA Accepted   =", sa_res['accepted'])

    print("\n=== Шаг 5. Генетический алгоритм ===")
    ga_res = solve_genetic(group_info, list_of_requests)
    print("Genetic Status     =", ga_res['status'])
    print("Genetic Objective  =", ga_res['objective'])
    print("Genetic Time (s)   =", ga_res['time_s'])
    print("Genetic Accepted   =", ga_res['accepted'])

    return {
        'ilp': ilp_res,
        'greedy': greedy_res,
        'simulated_annealing': sa_res,
        'genetic': ga_res
    }


async def main() -> None:
    transfers = await get_all_transfers_with_pending_status()
    t_groups = await get_transfer_groups()
    groups = await get_groups()
    result = compare_methods_db(transfers, t_groups, groups)
    print("\nИтоговое сравнение:\n", result)


if __name__ == '__main__':
    asyncio.run(main())
