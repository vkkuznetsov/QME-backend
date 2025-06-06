from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend.logic.services.manager_service.orm import ManagerService

router = APIRouter(prefix="/manager", tags=["manager"])


class ManagerCreate(BaseModel):
    name: str
    email: str


class ManagerUpdate(BaseModel):
    name: str
    email: str
    status: str


@router.get("/all")
async def get_all_managers(manager_service: ManagerService = Depends()):
    result = await manager_service.get_all()
    return result


@router.post("/create")
async def create_manager(
    manager: ManagerCreate,
    manager_service: ManagerService = Depends(),
):
    result = await manager_service.add_manager(
        name=manager.name, status="active", email=manager.email
    )
    return result


@router.put("/{manager_id}")
async def update_manager(
    manager_id: int,
    manager_data: ManagerUpdate,
    manager_service: ManagerService = Depends(),
):
    result = await manager_service.update_manager(
        manager_id=manager_id,
        name=manager_data.name,
        email=manager_data.email,
        status=manager_data.status,
    )
    if isinstance(result, dict) and "error" in result:
        status_code = 400 if result["error"] == "Invalid status" else 404
        raise HTTPException(status_code=status_code, detail=result["error"])
    return result


@router.delete("/{manager_id}")
async def delete_manager(
    manager_id: int,
    manager_service: ManagerService = Depends(),
):
    result = await manager_service.delete_manager(manager_id=manager_id)
    if isinstance(result, dict) and "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result
