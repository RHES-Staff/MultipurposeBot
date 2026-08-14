"""/api/board/* Handlers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated, Any, ClassVar

from aiosqlite import Row
from fastapi import APIRouter, Depends

from database import department, staff
from database.cookies import get_current_user
from database.models import Department, StaffMember

router = APIRouter(prefix="/board")


@dataclass
class DepartmentResponse:
    key: str
    name: str
    head: int


@dataclass
class NotesResponse:
    id: int
    staff_id: int
    author_id: int
    text: str


@dataclass
class StaffResponse:
    staff_id: int
    discord_id: str  # str due to js overflow
    name: str
    is_active: bool
    tags: list[str]
    notesList: list[NotesResponse]  # noqa: N815
    tasks: ClassVar[list] = []
    title: str | None = None
    timezone: str | None = None


@dataclass
class StaffMembershipsResponse:
    staff_id: int
    department_key: str
    is_active: str


@dataclass
class BoardResponse:
    departments: list[DepartmentResponse]
    staff: list[StaffResponse]
    memberships: list[StaffMembershipsResponse]


@router.get("")
async def get_board(user: Annotated[Row, Depends(get_current_user)]):
    """Get a full snapshot of staff, departments, and their relationships.

    Returns:
        BoardResponse: The board state needed to hydrate the frontend.
    """
    departments: list[Department] = await department.get_all_departments()
    staffs: list[StaffMember] = await staff.get_all_staff()
    memberships: list[dict[str, Any]] = await department.get_all_department_staffs()
    return BoardResponse(
        departments=[DepartmentResponse(dept.key, dept.name, dept.head.staff_id) for dept in departments],
        staff=[StaffResponse(staff.staff_id, str(staff.discord_id), staff.name, bool(staff.is_active), [], []) for staff in staffs],
        memberships=[StaffMembershipsResponse(member["staff_id"], member["department_key"], member["is_active"]) for member in memberships],
    )
