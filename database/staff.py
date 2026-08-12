"""Common Staff Operations on Database."""

import logging
from sqlite3 import IntegrityError, OperationalError, Row
from typing import cast, overload

import aiosqlite

from .core import Database

log: logging.Logger = logging.getLogger(f"App.{__name__}")


# Create functions
async def add_staff_to_department(staff_id: int, department_key: str) -> None:
    """Add a staff member to a department if they are not already associated with it.

    Args:
        staff_id: The internal `staff_staff.staff_id` ID of the staff member.
        department_key: The internal `staff_department.key` of the department staff should join to.
    """
    query = "INSERT OR IGNORE INTO staff_staff_department (staff_id, department_key) VALUES (:staff_id, :department_key);"
    db = Database()
    await db.execute(query, {"staff_id": staff_id, "department_key": department_key})


async def register_staff(discord_id: int, name: str, department_keys: list[str]) -> int:  # TODO: refactor
    """Register a Discord user as a staff member and assign them to one or more departments.

    If the user is already registered, existing records are kept and any missing department
    assignments are added.

    Args:
        discord_id: The Discord user ID of the staff member.
        name: The name/display name of the staff member.
        department_keys: List of department keys to assign to the staff member.

    Returns:
        int: The internal database `staff_id` for the registered staff member.

    Raises:
        sqlite3.OperationalError: If database queries return unexpected empty results or fail integrity checks during resolution.
    """
    insert_staff_query = "INSERT INTO staff_staff (name, discord_id) VALUES (:name, :id) RETURNING *;"
    db = Database()
    log.warning("Staff Registration is not yet fully implemented, proceed with caution.")
    try:
        results: Row | None = await db.fetchone(insert_staff_query, {"name": name, "id": discord_id})
    except IntegrityError as e:
        if "UNIQUE constraint failed: staff_staff.discord_id" in str(e):
            staff: Row | None = await get_staff(discord_id=discord_id)
            if not staff:
                raise OperationalError("A supposed duplicate entry did not return its duplicate.")
            log.debug("Attempted staff registration on an already-registered staff.", extra={"discord_id": discord_id, "staff": dict(staff)})
            for department_key in department_keys:
                await add_staff_to_department(staff["staff_id"], department_key)
            return staff["staff_id"]
        raise
    if not results:
        raise OperationalError("An expected return from a query did not return.")
    for department_key in department_keys:
        await add_staff_to_department(results["staff_id"], department_key)
    log.info("Staff registered.", extra={"id": results["staff_id"], "staff_name": results["name"], "discord_id": results["discord_id"]})
    return results["staff_id"]


# Read functions
@overload
async def get_staff(*, staff_id: int) -> aiosqlite.Row | None: ...
@overload
async def get_staff(*, discord_id: int) -> aiosqlite.Row | None: ...
async def get_staff(*, staff_id: int | None = None, discord_id: int | None = None) -> aiosqlite.Row | None:
    """Get a staff member by internal Staff ID or Discord ID.

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

    id_lookup: str = "staff_id" if staff_id else "discord_id"
    search_staff_query = f"SELECT * FROM staff_staff WHERE {id_lookup} = :id LIMIT 1;"
    id: int = cast(int, staff_id or discord_id)

    db = Database()
    params: dict[str, int] = {"id": id}
    results: Row | None = await db.fetchone(search_staff_query, params)
    return results


@overload
async def has_staff_admin_perms(*, staff_id: int) -> bool: ...
@overload
async def has_staff_admin_perms(*, discord_id: int) -> bool: ...
async def has_staff_admin_perms(*, staff_id: int | None = None, discord_id: int | None = None) -> bool:
    """Check if a staff is either a Dept. Head, or part of Systems Dept.

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

    id_lookup: str = "staff_id" if staff_id else "discord_id"
    query: str = f"""
    SELECT (
        EXISTS (SELECT 1 FROM staff_department d WHERE d.head = s.staff_id)
        OR EXISTS (
            SELECT 1 FROM staff_staff_department sd
            WHERE sd.staff_id = s.staff_id
            AND sd.department_key = 'sys'
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


# Delete
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


@overload
async def resign_staff_department(*, staff_id: int, department_key: str) -> None: ...
@overload
async def resign_staff_department(*, discord_id: int, department_key: str) -> None: ...
async def resign_staff_department(*, staff_id: int | None = None, discord_id: int | None = None, department_key: str) -> None:
    """Set a staff member's membership in a single department to inactive.

    Args:
        staff_id: Internal `staff_staff.staff_id` to look up. Mutually exclusive with `discord_id`.
        discord_id: Discord user ID to look up. Mutually exclusive with `staff_id`.
        department_key: Internal `staff_department.key` to look up.

    Returns:
        The matching `staff_staff` row, or `None` if no staff member is found.

    Raises:
        ValueError: If neither `staff_id` nor `discord_id` is provided, or if both are provided.
    """
    if not ((staff_id is None) ^ (discord_id is None)):
        raise ValueError("Only pass one parameter.")

    if staff_id:
        staff: Row | None = await get_staff(staff_id=staff_id)
    elif discord_id:
        staff: Row | None = await get_staff(discord_id=discord_id)
    if staff is None:
        raise ValueError("Staff not found.")

    db = Database()
    result = await db.execute(
        "UPDATE staff_staff_department SET is_active = 0 WHERE staff_id = :id AND department_key = :dept;",
        {"id": staff["staff_id"], "dept": department_key},
    )
    if result.rowcount == 0:
        raise ValueError("Staff is not a member of that department.")
