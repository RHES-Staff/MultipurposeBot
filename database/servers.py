"""Common Server Operations on Database."""

import json
import logging
from typing import TYPE_CHECKING, Any

import discord

from .core import Database

if TYPE_CHECKING:
    from collections.abc import Iterable
    from sqlite3 import Row

log: logging.Logger = logging.getLogger(f"App.{__name__}")


async def get_all_departments() -> dict[str, Any]:
    """Get all department details stored inside."""
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
