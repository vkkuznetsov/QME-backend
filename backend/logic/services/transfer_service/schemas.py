from typing import List

from pydantic import BaseModel


class TransferData(BaseModel):
    student_id: int
    from_elective_id: int
    to_elective_id: int
    groups_to_ids: List[int]


class TransferReorder(BaseModel):
    id: int
    priority: int
