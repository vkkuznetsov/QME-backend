from pydantic import BaseModel
from typing import List, Optional


class StudentSchema(BaseModel):
    id: int
    fio: str

    class Config:
        orm_mode = True


class GroupSchema(BaseModel):
    id: int
    name: str
    type: str
    capacity: int
    day: Optional[str]
    time_interval: Optional[str]
    free_spots: Optional[int]
    init_usage: Optional[int]
    students: List[StudentSchema]

    class Config:
        orm_mode = True


class ElectiveSchema(BaseModel):
    id: int
    name: str
    modeus_link: Optional[str]
    description: Optional[str]
    text: Optional[str]
    questions: Optional[str]
    cluster: Optional[str]
    groups: List[GroupSchema]

    class Config:
        orm_mode = True
        fields = {
            'text_embed': {'exclude': True}
        }