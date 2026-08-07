import logging
from sqlite3 import OperationalError, Row, IntegrityError

import aiosqlite
import discord

from .core import Database

log = logging.getLogger(f"App.{__name__}")


async def register_staff(member: discord.User | discord.Member) -> aiosqlite.Row:
    """Register a given staff."""
    insert_staff_query = "INSERT INTO staff_staff (name, discord_id) VALUES (:name, :id) RETURNING *;"
    db = Database()
    log.warning("Staff Registration is not yet fully implemented, proceed with caution.")
    try:
        results: Row | None = await db.fetchone(insert_staff_query, {"name": member.name, "id": member.id})
    except IntegrityError as e:
        if "UNIQUE constraint failed: staff_staff.discord_id" in str(e):
            staff: Row | None = await get_staff_by_discord_user(member)
            if not staff:
                raise OperationalError("A supposed duplicate entry did not return its duplicate.")
            log.debug("Attempted staff registration on an already-registered staff.", extra={"member": member, "staff": dict(staff)})
            return staff["staff_id"]
    if not results:
        raise OperationalError("An expected return from a query did not return.")
    log.info("Staff registered.", extra={"id": results["staff_id"], "staff_name": results["name"], "discord_id": results["discord_id"]})
    return results["staff_id"]


async def get_staff_by_discord_user(member: discord.User | discord.Member) -> aiosqlite.Row | None:
    """Get a staff from a Discord Member/User object."""
    search_staff_query = "SELECT * FROM staff_staff WHERE discord_id = :id LIMIT 1;"
    db = Database()
    results: Row | None = await db.fetchone(search_staff_query, {"id": member.id})
    return results
