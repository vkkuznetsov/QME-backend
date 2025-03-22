from pydantic import BaseModel
from typing import List

class TransferData(BaseModel):
    student_id: int
    from_elective_id: int
    to_elective_id: int
    groups_to_ids: List[int]