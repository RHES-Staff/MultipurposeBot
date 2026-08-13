"""Board Aggregation Queries for the /api/board Endpoint."""

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING, Any

from .core import Database

if TYPE_CHECKING:
    from collections.abc import Iterable

    import aiosqlite


async def _get_staff_tags() -> dict[int, list[str]]:
    """Map each staff member to the names of tags assigned to them.

    Returns:
        dict[int, list[str]]: A mapping of `staff_id` to a list of tag names.
    """
    db = Database()
    rows: Iterable[aiosqlite.Row] = await db.fetchall(
        "SELECT st.staff_id, t.name FROM staff_tags st JOIN asset_tags t ON t.id = st.tag_id ORDER BY st.staff_id, st.created_at"
    )
    tags: dict[int, list[str]] = {}
    for row in rows:
        tags.setdefault(row["staff_id"], []).append(row["name"])
    return tags


async def _get_staff_latest_notes() -> dict[int, str]:
    """Map each staff member to the text of their most recently created note.

    Returns:
        dict[int, str]: A mapping of `staff_id` to the latest note text.
    """
    db = Database()
    rows: Iterable[aiosqlite.Row] = await db.fetchall(
        "SELECT staff_id, note FROM ("
        "    SELECT staff_id, note, "
        "           ROW_NUMBER() OVER (PARTITION BY staff_id ORDER BY created_at DESC, id DESC) AS rn "
        "    FROM staff_notes"
        ") WHERE rn = 1"
    )
    return {row["staff_id"]: row["note"] for row in rows}


async def get_board_staff() -> list[dict[str, Any]]:
    """Get every staff member formatted for the /api/board response.

    Returns:
        list[dict[str, Any]]: One entry per staff member. `tags` holds tag names, `notes` holds only the most recent note, and `tasks` is always empty until a tasks table exists.
    """
    db = Database()
    rows: Iterable[aiosqlite.Row] = await db.fetchall("SELECT staff_id, discord_id, name, is_active, is_blacklisted FROM staff_staff")
    tags_by_staff = await _get_staff_tags()
    notes_by_staff = await _get_staff_latest_notes()

    staff: list[dict[str, Any]] = []
    for row in rows:
        if row["is_blacklisted"]:
            status = "blacklisted"
        elif not row["is_active"]:
            status = "inactive"
        else:
            status = "active"
        staff.append(
            {
                "id": row["staff_id"],
                "discord_id": str(row["discord_id"]),
                "name": row["name"],
                "status": status,
                "tags": tags_by_staff.get(row["staff_id"], []),
                "notes": notes_by_staff.get(row["staff_id"], ""),
                "tasks": [],
            }
        )
    return staff


async def get_board_departments() -> list[dict[str, Any]]:
    """Get every department formatted for the /api/board response.

    Returns:
        list[dict[str, Any]]: One entry per department. `id` and `sort_order` both come from `staff_level`, and `slug` comes from the department's `key`.
    """
    db = Database()
    rows: Iterable[aiosqlite.Row] = await db.fetchall("SELECT key, name, staff_level FROM staff_department ORDER BY staff_level;")
    return [{"id": row["staff_level"], "name": row["name"], "slug": row["key"], "sort_order": row["staff_level"]} for row in rows]


async def get_board_memberships() -> list[dict[str, Any]]:
    """Get every active staff-to-department membership formatted for the /api/board response.

    Returns:
        list[dict[str, Any]]: One entry per active membership, with `department_id` taken from the department's `staff_level`.
    """
    db = Database()
    rows: Iterable[aiosqlite.Row] = await db.fetchall(
        "SELECT sd.staff_id, dept.staff_level AS department_id "
        "FROM staff_staff_department sd "
        "JOIN staff_department dept ON dept.key = sd.department_key "
        "WHERE sd.is_active = 1"
    )
    return [{"staff_id": row["staff_id"], "department_id": row["department_id"]} for row in rows]


async def get_board_heads() -> list[dict[str, Any]]:
    """Get every department head formatted for the /api/board response.

    Returns:
        list[dict[str, Any]]: One entry per department, pairing the head's `staff_id` with the department's `staff_level` as `department_id`.
    """
    db = Database()
    rows: Iterable[aiosqlite.Row] = await db.fetchall("SELECT head AS staff_id, staff_level AS department_id FROM staff_department")
    return [{"staff_id": row["staff_id"], "department_id": row["department_id"]} for row in rows]


async def get_next_staff_id() -> int:
    """Get the next unused staff_id for client-side optimistic creation.

    Returns:
        int: One greater than the highest existing `staff_id`, or 1 if no staff exist.
    """
    db = Database()
    row: aiosqlite.Row | None = await db.fetchone("SELECT MAX(staff_id) AS max_id FROM staff_staff")
    if row is None:
        raise sqlite3.OperationalError("Something went wrong.")
    return (row["max_id"] or 0) + 1
