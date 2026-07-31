import logging

import aiosqlite
import discord

from .core import Database

log = logging.getLogger(f"App.{__name__}")


async def register_staff(member: discord.User | discord.Member) -> aiosqlite.Row:
    """Register a given staff."""
    insert_staff_query = "INSERT INTO staff_staff (name, discord_id) VALUES (:name, :id) RETURNING *;"
    db = Database()
    log.warning("Auto Staff Registration is not yet fully implemented, proceed with caution.")
    results = await db.fetchone(insert_staff_query, {"name": member.name, "id": member.id})
    if not results:
        raise Exception("Something went wrong.")
    log.info("Staff registered.", extra={"id": results["staff_id"], "staff_name": results["name"], "discord_id": results["discord_id"]})
    return results["staff_id"]


async def get_staff_by_discord_user(member: discord.User | discord.Member) -> aiosqlite.Row | None:
    """Get a staff from a Discord Member/User object."""
    search_staff_query = "SELECT * FROM staff_staff WHERE discord_id = :id LIMIT 1;"
    db = Database()
    results = await db.fetchone(search_staff_query, {"id": member.id})
    return results
