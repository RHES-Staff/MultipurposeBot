"""Common Server Operations on Database."""

from __future__ import annotations

import json
import logging
import sqlite3
from typing import TYPE_CHECKING, Literal, overload

from aiosqlite.cursor import Cursor

from . import models, staff
from .core import Database

if TYPE_CHECKING:
    from collections.abc import Iterable
    from sqlite3 import Row

log: logging.Logger = logging.getLogger(f"App.{__name__}")


# Create
async def register_staff_to_department(staff_id: int, department_key: str) -> None:
    """Add a staff member to a department.

    Args:
        staff_id: The unique identifier for the staff member.
        department_key: The unique key for the target department.

    Raises:
        ValueError: If the staff ID or department key is invalid or not found.
    """
    query = "INSERT OR IGNORE INTO staff_staff_department (staff_id, department_key) VALUES (:staff_id, :department_key) RETURNING *;"
    db = Database()
    try:
        await db.fetchone(query, {"staff_id": staff_id, "department_key": department_key})
    except sqlite3.OperationalError:
        raise ValueError("Staff ID or Department Key not found.")


# Read
async def get_department(department_key: str) -> models.Department | None:
    """Fetch a department record by its unique key.

    Args:
        department_key: The unique key of the department to retrieve.

    Returns:
        The matching Department instance if found, or None.
    """
    department_query = """
    SELECT s.staff_id as head_id, s.name as head_name, s.discord_id as head_discord_id, json(d.configuration) AS configuration, json(d.servers) AS servers, d.*
    FROM staff_department d 
    JOIN staff_staff s
        ON d.head = s.staff_id
    WHERE d.key = :key
    """

    db = Database()
    return await models.Department.from_row(await db.fetchone(department_query, {"key": department_key}))


async def get_all_departments() -> list[models.Department]:
    """Fetch all department records ordered by staff level.

    Returns:
        A list of all Department instances.
    """
    department_query = """
    SELECT s.staff_id as head_id, s.name as head_name, s.discord_id as head_discord_id, json(d.configuration) AS configuration, json(d.servers) AS servers, d.*
    FROM staff_department d 
    JOIN staff_staff s
        ON d.head = s.staff_id
    ORDER BY staff_level ASC;
    """
    db = Database()
    return [await models.Department.from_row(dept) for dept in await db.fetchall(department_query)]


@overload
async def get_department_staffs(department_key: str, *, shallow: Literal[True] = True) -> list[models.StaffSummary]: ...
@overload
async def get_department_staffs(department_key: str, *, shallow: Literal[False] = False) -> list[models.StaffMember]: ...
async def get_department_staffs(department_key: str, *, shallow: Literal[True, False] = False):
    """Fetch active staff members registered in a department.

    Args:
        department_key: The unique key of the department to query.
        shallow: Whether to return summarized staff records instead of full
            models.

    Returns:
        A list of staff summary or full staff member models depending on the shallow flag.
    """
    if shallow:
        values = "s.staff_id, s.name, s.discord_id"
    else:
        values = "s.*"
    query = f"""
        SELECT {values} FROM staff_staff s
        JOIN staff_staff_department sd ON sd.staff_id = s.staff_id
        WHERE sd.department_key = :department_key AND sd.is_active = 1;
        """

    db = Database()
    result: Iterable[Row] = await db.fetchall(query, {"department_key": department_key})
    if shallow:
        return [models.StaffSummary.from_row(staff) for staff in result]
    else:
        return [models.StaffMember.from_row(staff) for staff in result]


async def get_all_department_staffs() -> list[dict[str, int | bool | str]]:
    """Fetch all active staff and department association records.

    Returns:
        A list of dictionaries containing raw association database fields.
    """
    query: str = "SELECT * FROM staff_staff_department WHERE is_active = 1;"

    db = Database()
    result: Iterable[Row] = await db.fetchall(query)
    return [dict(row) for row in result]


# Update
async def set_department_server(department_key: str, server_id: int, *, add: bool) -> None:
    """Add or remove a server identifier from a department configuration.

    Args:
        department_key: The unique key of the department to update.
        server_id: The Discord server identifier to manage.
        add: Whether to add the server ID if True, or remove it if False.
    """
    db = Database()
    if add:
        query = "UPDATE staff_department SET servers = jsonb_insert(servers, '$[#]', :server_id) WHERE key = :key;"
    else:
        query = "UPDATE staff_department SET servers = jsonb(COALESCE((SELECT jsonb_group_array(value) FROM json_each(servers) WHERE value != :server_id), '[]')) WHERE key = :key;"
    await db.execute(query, params={"key": department_key, "server_id": server_id})


async def set_department_config(department_key: str, key: str, value: str) -> bool:
    """Set a key and value pair in a department configuration JSON.

    Args:
        department_key: The unique key of the department to update.
        key: The configuration setting key to update.
        value: The string value or JSON payload string to assign.

    Returns:
        True if the department record was updated, or False if not found.
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


async def set_department_head(department_key: str, staff_id: int) -> None:
    """Assign a new staff head to a department.

    Args:
        department_key: The unique key of the department to update.
        staff_id: The unique identifier of the staff member.

    Raises:
        ValueError: If the department or staff member does not exist.
    """
    # TODO: dpet. heds/bod must automatically join dept. heads/bod dept if not yet joined
    query = "UPDATE staff_department SET head = :id WHERE key = :department RETURNING *"
    db = Database()
    res: Row | None = await db.fetchone(query, {"id": staff_id, "department": department_key})
    if not res:
        raise ValueError("One of the input is invalid.")


# delete
@overload
async def resign_staff_department(*, staff_id: int, department_key: str) -> models.StaffMember: ...
@overload
async def resign_staff_department(*, discord_id: int, department_key: str) -> models.StaffMember: ...
async def resign_staff_department(*, staff_id: int | None = None, discord_id: int | None = None, department_key: str) -> models.StaffMember:
    """Deactivate a staff member association with a department.

    Args:
        staff_id: The unique staff identifier. Mutually exclusive with discord_id.
        discord_id: The unique Discord account identifier. Mutually exclusive with staff_id.
        department_key: The unique key of the department to leave.

    Returns:
        The updated StaffMember instance.

    Raises:
        ValueError: If both or neither identifiers are provided, or if the deactivation query fails.
    """
    if (staff_id is None) == (discord_id is None):
        raise ValueError("Only pass one parameter.")
    query = f"""
    UPDATE staff_staff_department 
    SET is_active = 0 
    WHERE staff_id = {":id" if staff_id else "(SELECT staff_id FROM staff_staff s WHERE discord_id=:id)"}
        AND department_key = :dept
    RETURNING 1;
    """
    db = Database()
    result: Row | None = await db.fetchone(query, {"id": staff_id or discord_id, "dept": department_key})
    if not result:
        raise ValueError("Something went wrong.")
    return await staff.get_staff(staff_id=staff_id, discord_id=discord_id)  # ty: ignore[no-matching-overload]
