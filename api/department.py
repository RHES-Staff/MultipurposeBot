"""/api/department/* Handlers."""

from dataclasses import asdict
from typing import Annotated

from aiosqlite import Row
from fastapi import APIRouter, Depends
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
