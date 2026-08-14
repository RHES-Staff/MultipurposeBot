"""/api/department/* Handlers."""

from dataclasses import asdict
from typing import Annotated

from aiosqlite import Row
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

import database
from database.cookies import get_current_user
from database.models import Department

router = APIRouter(prefix="/departments")


class StaffOut(BaseModel):
    """Lightweight staff member representation for API responses.

    Attributes:
        staff_id: The internal database staff ID.
        name: The display name of the staff member.
        discord_id: The Discord user ID as a string.
    """

    staff_id: int
    name: str
    discord_id: str


class DepartmentOut(BaseModel):
    """Department representation for API responses.

    Attributes:
        key: The unique key identifier of the department.
        name: The display name of the department.
        head: The department head as a lightweight staff object.
        staffs: The list of assigned staff members as lightweight staff objects.
    """

    key: str
    name: str
    head: StaffOut
    staffs: list[StaffOut]


@router.get("")
async def get_all_departments(user: Annotated[Row, Depends(get_current_user)]) -> list[DepartmentOut]:
    """Get all active departments with populated staff members.

    Args:
        user: The authenticated staff user making the request.

    Returns:
        list[DepartmentOut]: A list of all departments with head and staff records populated.
    """
    departments: list[Department] = await database.department.get_all_departments()
    print([asdict(d) for d in departments])
    return [
        DepartmentOut(
            **{f: getattr(d, f) for f in ("key", "name")},
            head=StaffOut(staff_id=d.head.staff_id, name=d.head.name, discord_id=str(d.head.discord_id)),
            staffs=[StaffOut(staff_id=s.staff_id, name=s.name, discord_id=str(s.discord_id)) for s in d.staffs],
        )
        for d in departments
    ]


class SetHeadsRequest(BaseModel):
    """Request body to set a department head.

    Attributes:
        staff_id: The internal staff ID to assign as the department head.
    """

    staff_id: int


@router.put("/{department}/head")
async def set_department_heads(department: str, body: SetHeadsRequest, user: Annotated[Row, Depends(get_current_user)]) -> dict:
    """Set the department head for a specific department.

    Args:
        department: The unique department key from the path.
        body: The request payload containing the staff ID to assign.
        user: The authenticated staff user making the request.

    Returns:
        dict: A status map with key "status" set to "ok".

    Raises:
        HTTPException: If an error occurs when updating the department head.
    """
    try:
        await database.department.set_department_head(department_key=department, staff_id=body.staff_id)
    except:  # noqa: E722
        raise HTTPException(status_code=500, detail="Something went wrong.")
    return {"status": "ok"}
