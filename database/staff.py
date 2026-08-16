"""Common Staff Operations on Database."""

from __future__ import annotations

import logging
import sqlite3
from sqlite3 import IntegrityError, OperationalError, Row
from typing import TYPE_CHECKING, Any, Literal, cast, overload

import aiosqlite

from . import department, models
from .core import Database

if TYPE_CHECKING:
    from collections.abc import Iterable
log: logging.Logger = logging.getLogger(f"App.{__name__}")


# Create functions
async def register_staff(discord_id: int, name: str, department_keys: list[str]) -> models.StaffMember:
    """Register a Discord user as a staff member.

    Assign the staff member to one or more departments.

    Args:
        discord_id: The Discord user ID of the staff member.
        name: The name or display name of the staff member.
        department_keys: The list of department keys to assign to the staff member.

    Returns:
        models.StaffMember: The registered staff member object.

    Raises:
        ValueError: If the Discord ID is already registered.
        sqlite3.OperationalError: If the database query does not return data.
    """
    insert_staff_query = "INSERT INTO staff_staff (name, discord_id) VALUES (:name, :id) RETURNING *;"
    db = Database()
    try:
        results: Row | None = await db.fetchone(insert_staff_query, {"name": name, "id": discord_id})
    except IntegrityError as e:
        if "UNIQUE constraint failed: staff_staff.discord_id" in str(e):
            raise ValueError("Discord ID is already registered.")
        raise
    if not results:
        raise OperationalError("An expected return from a query did not return.")

    for department_key in department_keys:
        # TODO: this can error
        await department.register_staff_to_department(results["staff_id"], department_key)

    staff: models.StaffMember = await models.StaffMember.from_row(results)
    log.info("Staff registered.", extra={"staff": staff})
    return staff


# Read functions
@overload
async def get_staff(*, staff_id: int) -> models.StaffMember | None: ...
@overload
async def get_staff(*, discord_id: int) -> models.StaffMember | None: ...
async def get_staff(*, staff_id: int | None = None, discord_id: int | None = None) -> models.StaffMember | None:
    """Get a staff member by staff ID or Discord ID.

    Args:
        staff_id: The internal staff ID to look up. Mutually exclusive with `discord_id`.
        discord_id: The Discord user ID to look up. Mutually exclusive with `staff_id`.

    Returns:
        models.StaffMember | None: The matching staff member, or `None` if not found.

    Raises:
        ValueError: If you do not supply exactly one identifier.
    """
    if (staff_id is None) == (discord_id is None):
        raise ValueError("Only pass one parameter.")

    id_lookup: str = "staff_id" if staff_id is not None else "discord_id"
    search_staff_query = f"SELECT * FROM staff_staff WHERE {id_lookup} = :id LIMIT 1;"
    id: int = cast(int, staff_id if staff_id is not None else discord_id)

    db = Database()
    results: models.StaffMember | None = await models.StaffMember.from_row(await db.fetchone(search_staff_query, {"id": id}))
    return results


async def get_all_staff() -> list[models.StaffMember]:
    """Get all registered staff members.

    Returns:
        list[models.StaffMember]: A list of all staff member objects.
    """
    search_staff_query = "SELECT * FROM staff_staff;"

    db = Database()
    return [await models.StaffMember.from_row(row) for row in await db.fetchall(search_staff_query)]


@overload
async def get_staff_departments(*, staff_id: int, shallow: Literal[True] = True) -> list[models.DepartmentSummary]: ...
@overload
async def get_staff_departments(*, discord_id: int, shallow: Literal[True] = True) -> list[models.DepartmentSummary]: ...
@overload
async def get_staff_departments(*, staff_id: int, shallow: Literal[False] = False) -> list[models.Department]: ...
@overload
async def get_staff_departments(*, discord_id: int, shallow: Literal[False] = False) -> list[models.Department]: ...
async def get_staff_departments(*, staff_id: int | None = None, discord_id: int | None = None, shallow: Literal[True, False] = False):
    """Get all active departments for a staff member.

    Args:
        staff_id: The internal staff ID to look up. Mutually exclusive with `discord_id`.
        discord_id: The Discord user ID to look up. Mutually exclusive with `staff_id`.
        shallow: If True, return department summaries. If False, return full department models.

    Returns:
        list[models.DepartmentSummary] | list[models.Department]: A list of assigned active departments.

    Raises:
        ValueError: If you do not supply exactly one identifier.
    """
    if (staff_id is None) == (discord_id is None):
        raise ValueError("Exactly one of `staff_id` or `discord_id` must be provided.")

    query = f"""
    SELECT {"d.key, d.name" if shallow else "d.*"} 
    FROM staff_staff_department sd
    LEFT JOIN staff_department d ON sd.department_key = d.key
    WHERE sd.staff_id = :staff_id AND sd.is_active = 1;
    """

    db = Database()
    result: Iterable[Row] = await db.fetchall(query, {"staff_id": staff_id})
    if shallow:
        return [models.DepartmentSummary.from_row(dept) for dept in result]
    else:
        return [await models.Department.from_row(dept) for dept in result]


@overload
async def has_staff_admin_perms(*, staff_id: int) -> bool: ...
@overload
async def has_staff_admin_perms(*, discord_id: int) -> bool: ...
async def has_staff_admin_perms(*, staff_id: int | None = None, discord_id: int | None = None) -> bool:
    """Update profile fields for a staff member.

    Args:
        name: The new name. Set to `None` to keep the current value.
        title: The new title. Set to `None` to keep the current value.
        timezone: The new timezone. Set to `None` to keep the current value.
        staff_id: The internal staff ID to look up. Mutually exclusive with `discord_id`.
        discord_id: The Discord user ID to look up. Mutually exclusive with `staff_id`.

    Returns:
        bool: A flag if the user is an Admin.

    Raises:
        ValueError: If no staff member is found.
    """
    if not ((staff_id is None) ^ (discord_id is None)):
        raise ValueError("Only pass one parameter.")

    id_lookup: str = "staff_id" if staff_id else "discord_id"
    query: str = f"""
    SELECT (
        EXISTS (SELECT 1 FROM staff_department d WHERE d.head = s.staff_id)
        OR EXISTS (
            SELECT 1 FROM staff_staff_department sd
            WHERE sd.staff_id = s.staff_id
            AND sd.department_key IN ('bod', 'sys')
            AND sd.is_active = 1
        )) AS has_perms
    FROM staff_staff s
    WHERE s.{id_lookup} = :id;
    """
    id: int = cast(int, staff_id or discord_id)

    db = Database()
    params: dict[str, int] = {"id": id}
    results: Row | None = await db.fetchone(query, params)
    if not results:
        return False
    return bool(results["has_perms"])


# Update functions
@overload
async def update_staff_profile(name: str | None = None, title: str | None = None, timezone: str | None = None, *, staff_id: int) -> models.StaffMember: ...
@overload
async def update_staff_profile(name: str | None = None, title: str | None = None, timezone: str | None = None, *, discord_id: int) -> models.StaffMember: ...
async def update_staff_profile(
    name: str | None = None, title: str | None = None, timezone: str | None = None, *, staff_id: int | None = None, discord_id: int | None = None
) -> models.StaffMember:
    """Update one or more profile fields for a staff member.

    Args:
        name: New name for the staff member. Omit to leave unchanged.
        title: New title for the staff member. Omit to leave unchanged.
        timezone: New timezone for the staff member. Omit to leave unchanged.
        staff_id: Internal `staff_staff.staff_id` to look up. Mutually exclusive with `discord_id`.
        discord_id: Discord user ID to look up. Mutually exclusive with `staff_id`.

    Returns:
        aiosqlite.Row: The updated `staff_staff` row, containing `staff_id` and the updated fields.

    Raises:
        ValueError: If neither `staff_id` nor `discord_id` is provided, or if both are provided, or if none of `name`, `title`, or `timezone` are provided.
    """
    if (staff_id is None) == (discord_id is None):
        raise ValueError("Exactly one of staff_id or discord_id must be provided.")

    fields: dict[str, str] = {}
    if name is not None:
        fields["name"] = name
    if title is not None:
        fields["title"] = title
    if timezone is not None:
        fields["timezone"] = timezone
    if not fields:
        raise ValueError("At least one of name, title, or timezone must be provided.")

    db = Database()
    set_clause: str = ", ".join(f"{col} = :{col}" for col in fields)
    where_clause: str = "staff_id = :lookup" if staff_id is not None else "discord_id = :lookup"
    params: dict[str, Any] = {**fields, "lookup": staff_id if staff_id is not None else discord_id}

    query: str = f"UPDATE staff_staff SET {set_clause} WHERE {where_clause} RETURNING *;"
    row: aiosqlite.Row | None = await db.fetchone(query, params)
    if row is None:
        raise ValueError("No staff member found matching the given identifier.")
    return await models.StaffMember.from_row(row)


@overload
async def update_staff_discord_acct(new_discord_id: int, *, staff_id: int) -> aiosqlite.Row: ...
@overload
async def update_staff_discord_acct(new_discord_id: int, *, old_discord_id: int) -> aiosqlite.Row: ...
async def update_staff_discord_acct(new_discord_id: int, *, staff_id: int | None = None, old_discord_id: int | None = None) -> aiosqlite.Row:
    """Update the linked Discord account for a staff member.

    Args:
        new_discord_id: The new Discord user ID to assign.
        staff_id: The internal staff ID to look up. Mutually exclusive with `old_discord_id`.
        old_discord_id: The current Discord user ID to look up. Mutually exclusive with `staff_id`.

    Returns:
        aiosqlite.Row: A database row containing `staff_id`, `old_discord_id`, and `new_discord_id`.

    Raises:
        ValueError: If you do not supply exactly one identifier, or if no matching staff member is found.
        sqlite3.OperationalError: If the database update query fails to return data.
    """
    if (staff_id is None) == (old_discord_id is None):
        raise ValueError("Exactly one of staff_id or old_discord_id must be provided.")
    query = """
    UPDATE staff_staff SET discord_id = :new_discord_id WHERE staff_id = :staff_id
    RETURNING staff_id, :old_discord_id AS old_discord_id, discord_id AS new_discord_id;
    """

    db = Database()

    if staff_id is not None:
        row: models.StaffMember | None = await get_staff(staff_id=staff_id)
    elif old_discord_id is not None:
        row: models.StaffMember | None = await get_staff(discord_id=old_discord_id)

    if row is None:
        raise ValueError("No matching staff member found.")

    result: Row | None = await db.fetchone(query, {"new_discord_id": new_discord_id, "staff_id": row.staff_id, "old_discord_id": row.discord_id})
    if not result:
        raise sqlite3.OperationalError("Something went wrong with the engine.")
    return result


async def sync_staff_departments(staff_id: int, department_keys: list[str]) -> models.StaffMember:
    """Sync active department memberships for a staff member.

    Activates all department keys in the list and deactivates any active keys not in the list.

    Args:
        staff_id: The internal staff ID to update.
        department_keys: The list of active department keys to set.

    Returns:
        models.StaffMember: The updated staff member object.

    Raises:
        ValueError: If the staff member is not found after syncing.
    """
    insert_new_dept = """
    INSERT INTO staff_staff_department (staff_id, department_key, is_active)
        SELECT :staff_id, je.value, 1
            FROM json_each(:department_keys) AS je
        JOIN staff_department ON staff_department.key = je.value
    ON CONFLICT (staff_id, department_key) DO UPDATE SET is_active = 1
    """
    deactivate_old_dept = """
    UPDATE staff_staff_department
    SET is_active = 0
    WHERE staff_id = :staff_id
        AND is_active = 1
        AND department_key NOT IN (SELECT value FROM json_each(:department_keys))
        """
    db = Database()
    await db.execute(insert_new_dept, {"staff_id": staff_id, "department_keys": str(department_keys)})
    await db.execute(deactivate_old_dept, {"staff_id": staff_id, "department_keys": str(department_keys)})
    staff: models.StaffMember | None = await get_staff(staff_id=staff_id)
    if not staff:
        raise ValueError("Something went wrong.")
    return staff


@overload
async def blacklist_staff(*, staff_id: int) -> aiosqlite.Row | None: ...
@overload
async def blacklist_staff(*, discord_id: int) -> aiosqlite.Row | None: ...
async def blacklist_staff(*, staff_id: int | None = None, discord_id: int | None = None) -> aiosqlite.Row | None:
    """Blacklist a staff member by internal Staff ID or Discord ID.

    The function blacklists a staff member only if the member is currently inactive (`is_active = 0`).

    Args:
        staff_id: The internal `staff_staff.staff_id` to look up. Mutually exclusive with `discord_id`.
        discord_id: The Discord user ID to look up. Mutually exclusive with `staff_id`.

    Returns:
        aiosqlite.Row | None: A row that contains `staff_id`, `name`, and `discord_id` of the blacklisted staff member. Returns `None` if no staff member is found.

    Raises:
        ValueError: Neither `staff_id` nor `discord_id` is provided, or both are provided.
        ValueError: The matched staff member is still active.
    """
    if (staff_id is None) == (discord_id is None):
        raise ValueError("Exactly one of `staff_id` or `discord_id` must be provided.")

    db = Database()
    field: str = "staff_id" if staff_id is not None else "discord_id"
    value: int = cast(int, staff_id if staff_id is not None else discord_id)
    query = f"UPDATE staff_staff SET is_blacklisted = 1 WHERE {field} = :value RETURNING staff_id, name, discord_id;"

    if staff_id is not None:
        row: models.StaffMember | None = await get_staff(staff_id=staff_id)
    elif discord_id is not None:
        row: models.StaffMember | None = await get_staff(discord_id=discord_id)

    if row is None:
        return None
    if row.is_active:
        raise ValueError("Cannot blacklist an active staff member.")

    return await db.fetchone(query, {"value": value})


# Delete functions
@overload
async def resign_staff(*, staff_id: int) -> None: ...
@overload
async def resign_staff(*, discord_id: int) -> None: ...
async def resign_staff(*, staff_id: int | None = None, discord_id: int | None = None) -> None:
    """Set a staff member and all their department memberships to inactive.

    Args:
        staff_id: Internal `staff_staff.staff_id` to look up. Mutually exclusive with `discord_id`.
        discord_id: Discord user ID to look up. Mutually exclusive with `staff_id`.

    Returns:
        The matching `staff_staff` row, or `None` if no staff member is found.

    Raises:
        ValueError: If neither `staff_id` nor `discord_id` is provided, or if both are provided.
    """
    if not ((staff_id is None) ^ (discord_id is None)):
        raise ValueError("Only pass one parameter.")

    staff_inactive_query = "UPDATE staff_staff SET is_active = 0 WHERE staff_id = :id;"
    department_inactive_query = "UPDATE staff_staff_department SET is_active = 0 WHERE staff_id = :id;"
    db = Database()
    where: str = "staff_id = :id" if staff_id is not None else "discord_id = :id"
    ident: int = cast(int, staff_id or discord_id)

    staff: Row | None = await db.fetchone(f"SELECT staff_id FROM staff_staff WHERE {where};", {"id": ident})
    if staff is None:
        raise ValueError("Staff not found.")

    resolved_id: int = staff["staff_id"]

    await db.execute(staff_inactive_query, {"id": resolved_id})
    await db.execute(department_inactive_query, {"id": resolved_id})
