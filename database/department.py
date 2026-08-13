"""Common Server Operations on Database."""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any, overload

import discord
from aiosqlite.cursor import Cursor

from . import staff
from .core import Database

if TYPE_CHECKING:
    from collections.abc import Iterable
    from sqlite3 import Row

log: logging.Logger = logging.getLogger(f"App.{__name__}")


# Create
async def register_staff_to_department(staff_id: int, department_key: str) -> None:
    """Add a staff member to a department if they are not already associated with it.

    Args:
        staff_id: The internal `staff_staff.staff_id` ID of the staff member.
        department_key: The internal `staff_department.key` of the department staff should join to.
    """
    query = "INSERT OR IGNORE INTO staff_staff_department (staff_id, department_key) VALUES (:staff_id, :department_key);"
    db = Database()
    await db.execute(query, {"staff_id": staff_id, "department_key": department_key})


# Read
async def get_all_departments() -> dict[str, Any]:
    """Retrieve all department records from the database.

    Parse the configuration and servers fields for each department.

    Returns:
        dict[str, Any]: A dictionary that maps department keys to their processed details. Each entry contains 'name', the parsed 'configuration' dict, and 'servers' as a list of `discord.Object` instances.
    """
    department_query = "SELECT key, name, json(configuration) AS configuration, json(servers) AS servers FROM staff_department;"
    db = Database()
    results: Iterable[Row] = await db.fetchall(department_query)
    departments: dict[str, Any] = {}
    for department in results:
        departments[department["key"]] = {
            "name": department["name"],
            "configuration": json.loads(department["configuration"]),
            "servers": [discord.Object(id=guild_id) for guild_id in json.loads(department["servers"])],
        }
    return departments


async def get_department_staff(department_key: str) -> Iterable[Row]:
    """Get all active staff members registered in a department.

    Args:
        department_key: The internal `staff_department.key` to look up.

    Returns:
        list[aiosqlite.Row]: A list of `staff_staff` rows belonging to the department.
    """
    query = """
        SELECT s.* FROM staff_staff s
        JOIN staff_staff_department sd ON sd.staff_id = s.staff_id
        WHERE sd.department_key = :department_key AND sd.is_active = 1;
        """
    db = Database()
    return await db.fetchall(query, {"department_key": department_key})


# Update
async def set_department_server(department_key: str, server_id: int, *, add: bool) -> None:
    """Add or remove a server from a department's registered servers list.

    Args:
        department_key: The internal `staff_department.key` of the department to update.
        server_id: The Discord server (guild) ID to add or remove.
        add: If True, adds the server; if False, removes it.
    """
    db = Database()
    if add:
        query = "UPDATE staff_department SET servers = jsonb_insert(servers, '$[#]', :server_id) WHERE key = :key;"
    else:
        query = "UPDATE staff_department SET servers = jsonb(COALESCE((SELECT jsonb_group_array(value) FROM json_each(servers) WHERE value != :server_id), '[]')) WHERE key = :key;"
    await db.execute(query, params={"key": department_key, "server_id": server_id})


async def set_department_config(department_key: str, key: str, value: str) -> bool:
    """Set a key/value pair in a department's configuration JSON.

    The function first tries to parse `value` as JSON. Numbers, booleans, and null values keep their native JSON type. If the parse fails, the function stores `value` as a plain string.

    Args:
        department_key: The internal `staff_department.key` of the department to update.
        key: The configuration key to set. Only letters, numbers, `_`, and `-` are allowed.
        value: The value to store under the given key.

    Returns:
        bool: True if the function updated a department. False if no department matched `department_key`.
    """
    db = Database()
    try:
        parsed_value = json.dumps(json.loads(value))
    except json.JSONDecodeError:
        parsed_value = json.dumps(value)

    query = """
        UPDATE staff_department
        SET configuration = jsonb_set(configuration, '$.' || :key, jsonb(:value)),
            edited_at = CURRENT_TIMESTAMP
        WHERE key = :department
    """
    result: Cursor = await db.execute(query, {"key": key, "value": parsed_value, "department": department_key})
    return result.rowcount != 0


# delete
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
        staff_object: Row | None = await staff.get_staff(staff_id=staff_id)
    elif discord_id:
        staff_object: Row | None = await staff.get_staff(discord_id=discord_id)
    if staff_object is None:
        raise ValueError("Staff not found.")

    db = Database()
    result = await db.execute(
        "UPDATE staff_staff_department SET is_active = 0 WHERE staff_id = :id AND department_key = :dept;",
        {"id": staff_object["staff_id"], "dept": department_key},
    )
    if result.rowcount == 0:
        raise ValueError("Staff is not a member of that department.")
