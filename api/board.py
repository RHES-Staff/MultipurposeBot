"""/api/board/* Handlers."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

import database

router = APIRouter(prefix="/board")


class TaskSchema(BaseModel):
    """Schema for one task assigned to a staff member."""

    id: int
    title: str
    done: bool


class StaffSchema(BaseModel):
    """Schema for one staff member on the board."""

    id: int
    discord_id: str
    name: str
    status: str = "active"
    tags: list[str] = []
    notes: str | None = ""
    tasks: list[TaskSchema] = []


class DepartmentSchema(BaseModel):
    """Schema for one department on the board."""

    id: int
    name: str
    slug: str
    sort_order: int


class MembershipSchema(BaseModel):
    """Schema linking a staff member to a department."""

    staff_id: int
    department_id: int


class HeadSchema(BaseModel):
    """Schema linking a department to its head staff member."""

    staff_id: int
    department_id: int


class BoardResponse(BaseModel):
    """Schema for the full /api/board snapshot."""

    nextStaffId: int
    nextTaskId: int
    staff: list[StaffSchema]
    departments: list[DepartmentSchema]
    memberships: list[MembershipSchema]
    heads: list[HeadSchema]


@router.get("", response_model=BoardResponse)
async def get_board() -> BoardResponse:
    """Get a full snapshot of staff, departments, and their relationships.

    Returns:
        BoardResponse: The board state needed to hydrate the frontend.
    """
    return BoardResponse(
        nextStaffId=await database.board.get_next_staff_id(),
        nextTaskId=1,
        staff=await database.board.get_board_staff(),
        departments=await database.board.get_board_departments(),
        memberships=await database.board.get_board_memberships(),
        heads=await database.board.get_board_heads(),
    )
