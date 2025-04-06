import math
from dataclasses import dataclass

import pulp
import pandas as pd

from typing import List, Dict

@dataclass
class ILPSolver:
    group_info: Dict[int,dict]
    requests_list: List[dict]

    def __call__(self):
        if not self.requests_list:
            return []

        capacity_map = {g_id: info['capacity'] for g_id, info in self.group_info.items()}
        usage_map = {g_id: info['init_usage'] for g_id, info in self.group_info.items()}

        ctimes = [r['created_at'] for r in self.requests_list]
        max_date = max(ctimes) if ctimes else pd.Timestamp('2025-01-01')
        day_in_sec = 24 * 3600
        time_scale = 0.1 / day_in_sec

        model = pulp.LpProblem('Elective_Reassign_ILP', pulp.LpMaximize)
        accept_vars = {}
        for rq in self.requests_list:
            rid = rq['r_id']
            accept_vars[rid] = pulp.LpVariable(f'accept_{rid}', cat=pulp.LpBinary)

        obj_terms = []
        for rq in self.requests_list:
            rid = rq['r_id']
            p = rq['priority']
            dt_seconds = (max_date - rq['created_at']).total_seconds()
            secondary = dt_seconds * time_scale if math.isfinite(dt_seconds) else 0
            total_val = (6 - p) + secondary
            obj_terms.append(total_val * accept_vars[rid])
        model += pulp.lpSum(obj_terms), 'MaxPriorityTime'

        group_to_in_requests = {g_id: [] for g_id in self.group_info.keys()}
        group_to_out_requests = {g_id: [] for g_id in self.group_info.keys()}
        for rq in self.requests_list:
            rid = rq['r_id']
            for g_out in rq['from_groups']:
                group_to_out_requests.setdefault(g_out, []).append(rid)
            for g_in in rq['to_groups']:
                group_to_in_requests.setdefault(g_in, []).append(rid)
        # Определяем, какие группы реально участвуют в заявках
        groups_involved = set()
        for rq in self.requests_list:
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
        for rq in self.requests_list:
            key = (rq['student_id'], rq['from_elective_id'])
            student_elective_requests[key].append(rq['r_id'])
        for key, rids in student_elective_requests.items():
            model += pulp.lpSum([accept_vars[rid] for rid in rids]) <= 1, \
                     f"UniqueRequest_student_{key[0]}_elective_{key[1]}"

        model.solve(pulp.PULP_CBC_CMD(msg=0))

        accepted = [rq['r_id'] for rq in self.requests_list if pulp.value(accept_vars[rq['r_id']]) and pulp.value(accept_vars[rq['r_id']]) > 0.5]
        return accepted
