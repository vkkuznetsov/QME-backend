from dataclasses import dataclass
from backend.logic.services.healthcheck.base import IHealthCheckService


@dataclass
class CompositeHealthCheckService(IHealthCheckService):
    services: list[IHealthCheckService]

    async def check(self) -> dict[str, bool]:
        ans = dict()
        for service in self.services:
            result = await service.check()
            ans.update(result)
        return ans
