"""Common Staff Operations on Database."""

from __future__ import annotations

import logging
import sqlite3
from sqlite3 import IntegrityError, OperationalError, Row
from typing import TYPE_CHECKING, Any, cast, overload

import aiosqlite

from database.models import DepartmentSummary, StaffMember, row_to_dataclass

from . import department
from .core import Database

if TYPE_CHECKING:
    from collections.abc import Iterable
log: logging.Logger = logging.getLogger(f"App.{__name__}")


# Create functions
async def register_staff(discord_id: int, name: str, department_keys: list[str]) -> int:
    """Register a Discord user as a staff member.

    Assign the staff member to one or more departments. If the user is already registered, the function keeps the existing records. The function adds any missing department assignments.

    Args:
        discord_id: The Discord user ID of the staff member.
        name: The name or display name of the staff member.
        department_keys: A list of department keys to assign to the staff member.

    Returns:
        int: The internal database `staff_id` for the registered staff member.

    Raises:
        sqlite3.OperationalError: The database queries return unexpected empty results, or fail an integrity check during resolution.
    """
    # TODO: if a staff resigned and reactivated, throw an error and direct them to reactivation instead
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
                await department.register_staff_to_department(staff["staff_id"], department_key)
            return staff["staff_id"]
        raise
    if not results:
        raise OperationalError("An expected return from a query did not return.")
    for department_key in department_keys:
        await department.register_staff_to_department(results["staff_id"], department_key)
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
    if (staff_id is None) == (discord_id is None):
        raise ValueError("Only pass one parameter.")
    
    id_lookup: str = "staff_id" if staff_id is not None else "discord_id"
    search_staff_query = f"SELECT * FROM staff_staff WHERE {id_lookup} = :id LIMIT 1;"
    id = staff_id if staff_id is not None else discord_id

    db = Database()
    params: dict[str, int] = {"id": id}
    results: Row | None = await db.fetchone(search_staff_query, params)
    return results


async def get_all_staff_with_departments() -> list[StaffMember]:
    """Get all staff members with a lightweight list of their active departments.

    Each department in a staff member's `departments` list only has its `key` and
    `name` populated.

    Returns:
        list[StaffMember]: All staff members, each with lightweight `DepartmentSummary` placeholders.
    """
    sql = """
        SELECT s.*, d.key AS dept_key, d.name AS dept_name
        FROM staff_staff s
        LEFT JOIN staff_staff_department sd
            ON sd.staff_id = s.staff_id AND sd.is_active = 1
        LEFT JOIN staff_department d
            ON d.key = sd.department_key
        ORDER BY s.staff_id
    """
    db = Database()
    rows: Iterable[Row] = await db.fetchall(sql)

    members: dict[int, StaffMember] = {}
    for row in rows:
        member: StaffMember | None = members.get(row["staff_id"])
        if member is None:
            member = row_to_dataclass(StaffMember, row)
            members[row["staff_id"]] = member
        if row["dept_key"] is not None:
            member.departments.append(DepartmentSummary(key=row["dept_key"], name=row["dept_name"]))

    return list(members.values())


@overload
async def get_staff_departments(*, staff_id: int) -> Iterable[Row]: ...
@overload
async def get_staff_departments(*, discord_id: int) -> Iterable[Row]: ...
async def get_staff_departments(*, staff_id: int | None = None, discord_id: int | None = None) -> Iterable[Row]:
    """Get all active departments a staff member belongs to.

    Args:
        staff_id: Internal `staff_staff.staff_id` to look up. Mutually exclusive with `discord_id`.
        discord_id: Discord user ID to look up. Mutually exclusive with `staff_id`.

    Returns:
        list[aiosqlite.Row]: A list of `staff_staff_department` rows for the staff member.

    Raises:
        ValueError: If neither `staff_id` nor `discord_id` is provided, or if both are provided.
        ValueError: If no staff is found.
    """
    if (staff_id is None) == (discord_id is None):
        raise ValueError("Exactly one of `staff_id` or `discord_id` must be provided.")

    db = Database()
    
    if staff_id is not None:
        print(staff_id, discord_id)
        row: Row | None = await get_staff(staff_id=staff_id)
    elif discord_id is not None:
        row: Row | None = await get_staff(discord_id=discord_id)
    print(row)
    if row is None:
        raise ValueError("No staff found")

    return await db.fetchall(
        "SELECT * FROM staff_staff_department WHERE staff_id = :staff_id AND is_active = 1;",
        {"staff_id": staff_id},
    )


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


# Update functions
@overload
async def update_staff_profile(name: str | None = None, title: str | None = None, timezone: str | None = None, *, staff_id: int) -> aiosqlite.Row: ...
@overload
async def update_staff_profile(name: str | None = None, title: str | None = None, timezone: str | None = None, *, discord_id: int) -> aiosqlite.Row: ...
async def update_staff_profile(
    name: str | None = None, title: str | None = None, timezone: str | None = None, *, staff_id: int | None = None, discord_id: int | None = None
) -> aiosqlite.Row:
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

    query: str = f"UPDATE staff_staff SET {set_clause} WHERE {where_clause} RETURNING staff_id, {', '.join(fields)};"
    row: aiosqlite.Row | None = await db.fetchone(query, params)
    if row is None:
        raise ValueError("No staff member found matching the given identifier.")
    return row


@overload
async def update_staff_discord_acct(new_discord_id: int, *, staff_id: int) -> aiosqlite.Row: ...
@overload
async def update_staff_discord_acct(new_discord_id: int, *, old_discord_id: int) -> aiosqlite.Row: ...
async def update_staff_discord_acct(new_discord_id: int, *, staff_id: int | None = None, old_discord_id: int | None = None) -> aiosqlite.Row:
    """Update a staff member's linked Discord account.

    Args:
        new_discord_id: The new Discord user ID to assign to the staff member.
        staff_id: Internal `staff_staff.staff_id` to look up. Mutually exclusive with `old_discord_id`.
        old_discord_id: Current Discord user ID to look up. Mutually exclusive with `staff_id`.

    Returns:
        aiosqlite.Row: A row containing `staff_id`, `old_discord_id`, and `new_discord_id`.

    Raises:
        ValueError: If neither `staff_id` nor `old_discord_id` is provided, or if both are provided,
            or if no matching staff member is found.
    """
    if (staff_id is None) == (old_discord_id is None):
        raise ValueError("Exactly one of staff_id or old_discord_id must be provided.")
    query = """
    UPDATE staff_staff SET discord_id = :new_discord_id WHERE staff_id = :staff_id
    RETURNING staff_id, :old_discord_id AS old_discord_id, discord_id AS new_discord_id;
    """

    db = Database()

    if staff_id is not None:
        row: Row | None = await get_staff(staff_id=staff_id)
    elif old_discord_id is not None:
        row: Row | None = await get_staff(discord_id=old_discord_id)

    if row is None:
        raise ValueError("No matching staff member found.")

    result: Row | None = await db.fetchone(query, {"new_discord_id": new_discord_id, "staff_id": row["staff_id"], "old_discord_id": row["discord_id"]})
    if not result:
        raise sqlite3.OperationalError("Something went wrong with the engine.")
    return result


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
        row: Row | None = await get_staff(staff_id=staff_id)
    elif discord_id is not None:
        row: Row | None = await get_staff(discord_id=discord_id)

    if row is None:
        return None
    if row["is_active"]:
        raise ValueError("Cannot blacklist an active staff member.")

    return await db.fetchone(query, {"value": value})


async def upsert_latest_note(staff_id: int, note: str, noter: int) -> aiosqlite.Row:
    """Update a staff member's most recent note, or insert one if none exists.

    Args:
        staff_id: The internal `staff_staff.staff_id` of the staff member being noted.
        note: The note text to store.
        noter: The `staff_staff.staff_id` of the staff member writing the note.

    Returns:
        aiosqlite.Row: The resulting `staff_notes` row.
    """
    db = Database()
    latest: aiosqlite.Row | None = await db.fetchone(
        "SELECT id FROM staff_notes WHERE staff_id = :staff_id ORDER BY created_at DESC LIMIT 1",
        {"staff_id": staff_id},
    )
    if latest:
        await db.execute(
            "UPDATE staff_notes SET note = :note, noter = :noter WHERE id = :id",
            {"note": note, "noter": noter, "id": latest["id"]},
        )
        return cast(aiosqlite.Row, await db.fetchone("SELECT * FROM staff_notes WHERE id = :id", {"id": latest["id"]}))
    cur: aiosqlite.Cursor = await db.execute(
        "INSERT INTO staff_notes (staff_id, note, noter) VALUES (:staff_id, :note, :noter)",
        {"staff_id": staff_id, "note": note, "noter": noter},
    )
    return cast(aiosqlite.Row, await db.fetchone("SELECT * FROM staff_notes WHERE id = :id", {"id": cur.lastrowid}))


async def sync_staff_departments(staff_id: int, department_keys: list[str]) -> None:
    """Sync a staff member's active departments to exactly match a given set.

    Adds membership to any missing department and resigns membership from any
    active department not present in `department_keys`.

    Args:
        staff_id: The internal staff_staff.staff_id of the staff member.
        department_keys: The department keys the staff member should be active in.
    """
    print(staff_id)
    current: Iterable[Row] = await get_staff_departments(staff_id=staff_id)
    current_keys: set[str] = {row["department_key"] for row in current}
    target_keys: set[str] = set(department_keys)

    for key in target_keys - current_keys:
        await department.register_staff_to_department(staff_id=staff_id, department_key=key)
    for key in current_keys - target_keys:
        await department.resign_staff_department(staff_id=staff_id, department_key=key)


async def _get_or_create_tag_id(name: str) -> int:
    """Get the ID of an asset_tags row by name, creating it if absent.

    Args:
        name: The tag name to look up or create.

    Returns:
        int: The asset_tags.id of the matching or newly created tag.
    """
    row: Row | None = await Database().fetchone("SELECT id FROM asset_tags WHERE name = :name;", {"name": name})
    if row is not None:
        return row["id"]
    cur: aiosqlite.Cursor = await Database().execute("INSERT INTO asset_tags (name) VALUES (:name);", {"name": name})
    return cast(int, cur.lastrowid)


async def sync_staff_tags(staff_id: int, tag_names: list[str], tagged_by: int) -> None:
    """Ensure a staff member has the given tags, creating tags as needed.

    Existing tag assignments are left as-is; tags not already present are added.

    Args:
        staff_id: The internal staff_staff.staff_id of the staff member being tagged.
        tag_names: The tag names to ensure are attached to the staff member.
        tagged_by: The internal staff_staff.staff_id of the staff member applying the tags.
    """
    existing: Iterable[Row] = await Database().fetchall("SELECT tag_id FROM staff_tags WHERE staff_id = :staff_id;", {"staff_id": staff_id})
    existing_ids: set[int] = {row["tag_id"] for row in existing}

    for name in tag_names:
        tag_id: int = await _get_or_create_tag_id(name)
        if tag_id in existing_ids:
            continue
        await Database().execute(
            "INSERT INTO staff_tags (staff_id, tag_id, tagged_by) VALUES (:staff_id, :tag_id, :tagged_by);",
            {"staff_id": staff_id, "tag_id": tag_id, "tagged_by": tagged_by},
        )


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
