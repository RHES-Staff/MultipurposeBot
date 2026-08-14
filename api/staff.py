"""/api/staff/* Handlers."""

from typing import Annotated, cast

from aiosqlite import Row
from fastapi import APIRouter, Depends
from pydantic import BaseModel

import database
from database.cookies import get_current_user
from database.models import StaffMember

router = APIRouter(prefix="/staff")


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


class UpdateStaffRequest(BaseModel):
    """Request payload to fully update a staff member profile and departments.

    Attributes:
        discord_id: The Discord user ID of the staff member as a string.
        name: The display name of the staff member.
        department_keys: The list of department keys assigned to the staff member.
        tags: The optional list of tags assigned to the staff member.
    """
    discord_id: str
    name: str
    department_keys: list[str]
    tags: list[str] = []


class PatchStaffRequest(BaseModel):
    """Request payload to partially update staff member metadata.

    Attributes:
        notes: Optional new notes for the staff member.
        tags: Optional new list of tags for the staff member.
        tasks: Optional new list of task objects for the staff member.
    """
    notes: str | None = None
    tags: list[str] | None = None
    tasks: list[dict] | None = None  # not sent by current UI, but supported by Api.patchStaff


@router.get("")
async def get_all_staff(user: Annotated[StaffMember, Depends(get_current_user)]) -> list[StaffOut]:
    """Get all staff members with their department keys and names.

    Returns:
        list[StaffOut]: All staff members, each with lightweight departments populated.
    """
    members: list[StaffMember] = await database.staff.get_all_staff()
    return [
        StaffOut(
            **{f: getattr(m, f) for f in ("staff_id", "name", "title", "timezone", "is_active", "is_blacklisted")},
            discord_id=str(m.discord_id),
            departments=[DepartmentOut(key=d.key, name=d.name) for d in m.departments],
        )
        for m in members
    ]


@router.post("")
async def upsert_staff(request: UpdateStaffRequest, user: Annotated[StaffMember, Depends(get_current_user)]) -> StaffOut:
    """Create or update a staff member, syncing their departments and tags.

    Args:
        request: The discord_id, name, department_ids, and tags to upsert.
        user: The authenticated staff member performing the upsert.

    Returns:
        StaffOut: The upserted staff member, with departments populated.
    """
    discord_id: int = int(request.discord_id)

    try:
        staff: StaffMember = await database.staff.register_staff(discord_id=discord_id, name=request.name, department_keys=request.department_keys)
    except ValueError as e:
        if not "Discord ID is already registered" in str(e):
            raise
        staff: StaffMember = cast(StaffMember, await database.staff.get_staff(discord_id=int(request.discord_id)))

        if staff.name != request.name:
            staff: StaffMember = await database.staff.update_staff_profile(name=request.name, staff_id=staff.staff_id)
        if [dept.key for dept in staff.departments] != request.department_keys:
            staff: StaffMember = await database.staff.sync_staff_departments(
                staff_id=staff.staff_id,
                department_keys=request.department_keys,
            )
    # if request.tags:
    # await database.staff.sync_staff_tags(staff_id=staff_id, tag_names=request.tags, tagged_by=user["staff_id"])

    return StaffOut(
        staff_id=staff.staff_id,
        name=staff.name,
        title=staff.title,
        timezone=staff.timezone,
        discord_id=str(staff.discord_id),
        is_active=staff.is_active,
        is_blacklisted=staff.is_blacklisted,
        departments=[DepartmentOut(key=d.key, name=d.name) for d in staff.departments],
    )


@router.patch("/{staff_id}")
async def patch_staff(staff_id: int, body: UpdateStaffRequest, user: Annotated[Row, Depends(get_current_user)]) -> StaffOut:
    """Patch a staff member's latest note.

    `tags` and `tasks` are accepted but currently ignored.

    Args:
        staff_id: The internal `staff_staff.staff_id` of the staff member to update.
        body: The fields to patch.
        user: The authenticated staff member performing the update.

    Returns:
        dict: an OK status.
    """
    staff: StaffMember = await update_staff(staff_id, body)
    return StaffOut(
        staff_id=staff.staff_id,
        name=staff.name,
        title=staff.title,
        timezone=staff.timezone,
        discord_id=str(staff.discord_id),
        is_active=staff.is_active,
        is_blacklisted=staff.is_blacklisted,
        departments=[DepartmentOut(key=d.key, name=d.name) for d in staff.departments],
    )


async def update_staff(staff_id: int, request: UpdateStaffRequest) -> StaffMember:
    """Update a staff member name and department memberships.

    Args:
        staff_id: The internal staff ID to look up. Pass 0 or None to look up by Discord ID.
        request: The update payload containing the name and department keys.

    Returns:
        StaffMember: The updated staff member object.
    """
    if staff_id:
        staff: StaffMember = cast(StaffMember, await database.staff.get_staff(staff_id=staff_id))
    else:
        staff: StaffMember = cast(StaffMember, await database.staff.get_staff(discord_id=int(request.discord_id)))

    if staff.name != request.name:
        staff: StaffMember = await database.staff.update_staff_profile(name=request.name, staff_id=staff.staff_id)
    if [dept.key for dept in staff.departments] != request.department_keys:
        staff: StaffMember = await database.staff.sync_staff_departments(
            staff_id=staff.staff_id,
            department_keys=request.department_keys,
        )
    return staff


@router.delete("/{staff_id}/departments/{department_key}")
async def remove_staff_department(staff_id: int, department_key: str, user: Annotated[StaffMember, Depends(get_current_user)]) -> StaffOut:
    """Resign a staff member from a department.

    Args:
        staff_id: The internal `staff_staff.staff_id` of the staff member.
        department_key: The internal `staff_department.key` to resign from.
        user: The authenticated staff member performing the action.

    Returns:
        dict: an OK status.
    """
    staff: StaffMember = await database.department.resign_staff_department(staff_id=staff_id, department_key=department_key)
    return StaffOut(
        staff_id=staff.staff_id,
        name=staff.name,
        title=staff.title,
        timezone=staff.timezone,
        discord_id=str(staff.discord_id),
        is_active=staff.is_active,
        is_blacklisted=staff.is_blacklisted,
        departments=[DepartmentOut(key=d.key, name=d.name) for d in staff.departments],
    )
