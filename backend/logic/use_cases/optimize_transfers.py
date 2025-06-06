from dataclasses import dataclass

from backend.optimization.data_for_optimization import DataGetter
from backend.optimization.ilp_method import ILPSolver


@dataclass
class OptimizeTransfers:
    solver: ILPSolver
    data_getter: DataGetter

    async def execute(self):
        dg = self.data_getter()
        group_info, list_of_requests = await dg()
        solution = self.solver(group_info, list_of_requests)
        results = solution()
        return results
