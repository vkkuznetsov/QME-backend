from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class IHealthCheckService(ABC):
    @abstractmethod
    async def check(self): ...
