"""/api/staff/* Handlers."""

from typing import Annotated, cast

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


@router.patch("/staff/{staff_id}")
async def patch_staff(staff_id: int, body: PatchStaffRequest, user: Annotated[Row, Depends(get_current_user)]) -> dict:
    """Patch a staff member's latest note.

    `tags` and `tasks` are accepted but currently ignored.

    Args:
        staff_id: The internal `staff_staff.staff_id` of the staff member to update.
        body: The fields to patch.
        user: The authenticated staff member performing the update.

    Returns:
        dict: an OK status.
    """
    if body.notes is not None:
        await database.staff.upsert_latest_note(staff_id=staff_id, note=body.notes, noter=user["staff_id"])

    return {"status": "ok"}


@router.post("/staff")
async def upsert_staff(request: UpdateStaffRequest, user: Annotated[Row, Depends(get_current_user)]) -> StaffOut:
    """Create or update a staff member, syncing their departments and tags.

    Args:
        request: The discord_id, name, department_ids, and tags to upsert.
        user: The authenticated staff member performing the upsert.

    Returns:
        StaffOut: The upserted staff member, with departments populated.
    """
    discord_id: int = int(request.discord_id)
    department_keys: list[str] = await database.department.get_department_keys_by_levels(request.department_ids)

    existing: Row | None = await database.staff.get_staff(discord_id=discord_id)
    if existing is None:
        staff_id: int = await database.staff.register_staff(discord_id=discord_id, name=request.name, department_keys=department_keys)
    else:
        staff_id = existing["staff_id"]
        await database.staff.update_staff_profile(name=request.name, staff_id=staff_id)
        await database.staff.sync_staff_departments(staff_id=staff_id, department_keys=department_keys)

    if request.tags:
        await database.staff.sync_staff_tags(staff_id=staff_id, tag_names=request.tags, tagged_by=user["staff_id"])

    member: StaffMember = cast(StaffMember, await database.department.load_staff_with_departments(discord_id=discord_id))
    return StaffOut(
        staff_id=member.staff_id,
        name=member.name,
        title=member.title,
        timezone=member.timezone,
        discord_id=str(member.discord_id),
        is_active=member.is_active,
        is_blacklisted=member.is_blacklisted,
        departments=[DepartmentOut(key=d.key, name=d.name) for d in member.departments],
    )


@router.delete("/staff/{staff_id}/departments/{department_key}")
async def remove_staff_department(staff_id: int, department_key: str, user: Annotated[Row, Depends(get_current_user)]) -> dict:
    """Resign a staff member from a department.

    Args:
        staff_id: The internal `staff_staff.staff_id` of the staff member.
        department_key: The internal `staff_department.key` to resign from.
        user: The authenticated staff member performing the action.

    Returns:
        dict: an OK status.
    """
    await database.department.resign_staff_department(staff_id=staff_id, department_key=department_key)
    return {"status": "ok"}
