"""/api/staff/* Handlers."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
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
    tags: list[str]


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


class CreateNoteRequest(BaseModel):
    """Request payload to creae a staff note.

    Attributes:
        note: The note put on the staff.
    """

    note: str


@router.post("")
async def create_staff(request: UpdateStaffRequest, user: Annotated[StaffMember, Depends(get_current_user)]) -> StaffOut:
    """Create a staff member, syncing their departments and tags.

    Args:
        request: The discord_id, name, department_ids, and tags to upsert.
        user: The authenticated staff member performing the upsert.

    Returns:
        StaffOut: The upserted staff member, with departments populated.
    """
    discord_id: int = int(request.discord_id)
    staff_obj: StaffMember = await database.staff.register_staff(discord_id=discord_id, name=request.name, department_keys=request.department_keys)
    return StaffOut(
        staff_id=staff_obj.staff_id,
        name=staff_obj.name,
        title=staff_obj.title,
        timezone=staff_obj.timezone,
        discord_id=str(staff_obj.discord_id),
        is_active=staff_obj.is_active,
        is_blacklisted=staff_obj.is_blacklisted,
        departments=[DepartmentOut(key=d.key, name=d.name) for d in staff_obj.departments],
        tags=[tag.name for tag in staff_obj.tags],
    )


@router.post("/{staff_id}/note")
async def create_note(staff_id: int, request: CreateNoteRequest, user: Annotated[StaffMember, Depends(get_current_user)]) -> StaffOut:
    """Creates a new note for a staff member.

    This endpoint adds a note to the specified staff profile and returns
    the updated staff details.

    Args:
        staff_id: The unique identifier of the staff member.
        request: The request payload that contains the note text.
        user: The current authenticated staff member who creates the note.

    Returns:
        A StaffOut object that contains the details of the staff member.

    Raises:
        HTTPException: Status code 404 if the staff member does not exist.
    """
    staff_obj: StaffMember | None = await database.staff.get_staff(staff_id=staff_id)
    if not staff_obj:
        raise HTTPException(status_code=404, detail="Staff not found")
    await database.notes.add_note(staff_id, request.note, user.staff_id)
    return StaffOut(
        staff_id=staff_obj.staff_id,
        name=staff_obj.name,
        title=staff_obj.title,
        timezone=staff_obj.timezone,
        discord_id=str(staff_obj.discord_id),
        is_active=staff_obj.is_active,
        is_blacklisted=staff_obj.is_blacklisted,
        departments=[DepartmentOut(key=d.key, name=d.name) for d in staff_obj.departments],
        tags=[tag.name for tag in staff_obj.tags],
    )


@router.get("")
async def get_all_staff(user: Annotated[StaffMember, Depends(get_current_user)]) -> list[StaffOut]:
    """Get all staff members with their department keys and names.

    Returns:
        list[StaffOut]: All staff members, each with lightweight departments populated.
    """
    members: list[StaffMember] = await database.staff.get_all_staff()
    return [
        StaffOut(
            **{f: getattr(m, f) for f in ("staff_id", "name", "title", "timezone", "is_active", "is_blacklisted", "tags")},
            discord_id=str(m.discord_id),
            departments=[DepartmentOut(key=d.key, name=d.name) for d in m.departments],
        )
        for m in members
    ]


@router.post("/{staff_id}")
async def update_staff(staff_id: int, request: UpdateStaffRequest, user: Annotated[StaffMember, Depends(get_current_user)]) -> StaffOut:
    """Update a staff member name and department memberships.

    Args:
        staff_id: The internal staff ID to look up. Pass 0 or None to look up by Discord ID.
        request: The update payload containing the name and department keys.
        user: The staff that called this method.

    Returns:
        StaffMember: The updated staff member object.
    """
    staff_obj: StaffMember | None = await database.staff.get_staff(staff_id=staff_id)
    if not staff_obj:
        raise HTTPException(status_code=404, detail="Staff not found")
    if staff_obj.name != request.name:
        staff_obj: StaffMember = await database.staff.update_staff_profile(name=request.name, staff_id=staff_obj.staff_id)
    if [dept.key for dept in staff_obj.departments] != request.department_keys:
        staff_obj: StaffMember = await database.staff.sync_staff_departments(
            staff_id=staff_obj.staff_id,
            department_keys=request.department_keys,
        )
    if request.tags != [tag.name for tag in staff_obj.tags]:
        print("this thing got executed")
        staff_obj: StaffMember = await database.tags.sync_staff_tags(staff_id=staff_obj.staff_id, tag_names=request.tags, tagged_by=user.staff_id)
    return StaffOut(
        staff_id=staff_obj.staff_id,
        name=staff_obj.name,
        title=staff_obj.title,
        timezone=staff_obj.timezone,
        discord_id=str(staff_obj.discord_id),
        is_active=staff_obj.is_active,
        is_blacklisted=staff_obj.is_blacklisted,
        departments=[DepartmentOut(key=d.key, name=d.name) for d in staff_obj.departments],
        tags=[tag.name for tag in staff_obj.tags],
    )


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
        tags=[tag.name for tag in staff.tags],
    )
