import json
import logging
from typing import Any

import discord

from .core import Database

log = logging.getLogger(f"App.{__name__}")


async def get_all_departments() -> dict[str, Any]:
    """Get all department details stored inside."""
    department_query = "SELECT key, name, configuration, servers FROM staff_department;"
    db = Database()
    results = await db.fetchall(department_query)
    departments: dict[str, Any] = {}
    for department in results:
        departments[department["key"]] = {"name": department["name"], "configuration": json.loads(department["configuration"]),  "servers": json.loads(department["servers"])}
    return departments
