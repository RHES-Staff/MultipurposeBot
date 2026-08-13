"""/api/staff/* Handlers."""

from typing import Annotated

from aiosqlite import Row
from fastapi import APIRouter, Depends
from pydantic import BaseModel

import database
from database.cookies import get_current_user
from database.models import StaffMember

router = APIRouter()


class DepartmentOut(BaseModel):
    """Lightweight department representation for API responses."""

    key: str
    name: str


class StaffOut(BaseModel):
    """Staff member representation for API responses."""

    staff_id: int
    name: str
    title: str | None
    timezone: str | None
    discord_id: str
    is_active: bool
    is_blacklisted: bool
    departments: list[DepartmentOut]


@router.get("/staff")
async def get_all_staff(user: Annotated[Row, Depends(get_current_user)]) -> list[StaffOut]:
    """Get all staff members with their department keys and names.

    Returns:
        list[StaffOut]: All staff members, each with lightweight departments populated.
    """
    members: list[StaffMember] = await database.staff.get_all_staff_with_departments()
    return [
        StaffOut(
            **{f: getattr(m, f) for f in ("staff_id", "name", "title", "timezone", "is_active", "is_blacklisted")},
            discord_id=str(m.discord_id),
            departments=[DepartmentOut(key=d.key, name=d.name) for d in m.departments],
        )
        for m in members
    ]


class UpdateStaffRequest(BaseModel):
    discord_id: str
    name: str
    department_ids: list[int]
    tags: list[str] = []


class PatchStaffRequest(BaseModel):
    notes: str | None = None
    tags: list[str] | None = None
    tasks: list[dict] | None = None  # not sent by current UI, but supported by Api.patchStaff
