import logging
import json

import discord

from . import Database

log = logging.getLogger(f"App.{__name__}")

async def getStaffFromDiscordAccount(user):
    # user expects a discord.Member
    query = """
        SELECT * FROM vw_staff_full
        WHERE account_id = ?;
    """
    db = Database()
    return await db.fetchone(query, (user.id,))