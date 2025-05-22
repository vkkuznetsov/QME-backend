from fastapi import Query

from typing import Annotated

Start = Annotated[int, Query(ge=0)]
Limit = Annotated[int, Query(ge=1, le=100)]


class Pagination:
    def __init__(self, start: Start = 0, limit: Limit = 10):
        self.start = start
        self.limit = limit
