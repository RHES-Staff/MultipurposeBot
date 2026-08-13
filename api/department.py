"""/api/department/* Handlers."""

from dataclasses import asdict
from typing import Annotated

from aiosqlite import Row
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

import database
from database.cookies import get_current_user

router = APIRouter()


class StaffOut(BaseModel):
    """Lightweight staff member representation for API responses."""

    staff_id: int
    name: str
    discord_id: str


class DepartmentOut(BaseModel):
    """Department representation for API responses."""

    key: str
    name: str
    head: StaffOut
    staffs: list[StaffOut]


@router.get("/department")
async def get_all_departments(user: Annotated[Row, Depends(get_current_user)]) -> list[DepartmentOut]:
    """Get all departments with their active staff's IDs and names.

    Returns:
        list[DepartmentOut]: All departments, each with lightweight staff populated.
    """
    departments = await database.department.get_all_departments_with_staff()
    print([asdict(d) for d in departments])
    return [
        DepartmentOut(
            **{f: getattr(d, f) for f in ("key", "name")},
            head=StaffOut(staff_id=d.head.staff_id, name=d.head.name, discord_id=d.head.discord_id),
            staffs=[StaffOut(staff_id=s.staff_id, name=s.name, discord_id=s.discord_id) for s in d.staffs],
        )
        for d in departments
    ]

class SetHeadsRequest(BaseModel):
    """Body for setting a department's head."""
    staff_ids: list[int]


@router.put('/departments/{staff_level}/heads')
async def set_department_heads(staff_level: int, body: SetHeadsRequest, user: Annotated[Row, Depends(get_current_user)]) -> dict:
    """Set a department's head.

    Only the first entry in `staff_ids` is used; multi-head support does not exist.

    Args:
        staff_level: The `staff_department.staff_level` identifying the department.
        body: The staff IDs to assign as head. Only the first entry is used.
        user: The authenticated staff member performing the action.

    Returns:
        dict: an OK status.
        
    Raises:
        HTTPException: 400 if `staff_ids` is empty.
        HTTPException: 404 if no department matches `staff_level`.
    """
    if not body.staff_ids:
        raise HTTPException(status_code=400, detail="staff_ids must not be empty")
    dept = await database.department.set_department_head_by_level(staff_level=staff_level, staff_id=body.staff_ids[0])
    if dept is None:
        raise HTTPException(status_code=404, detail="Department not found")
    return {"status": "ok"} 