"""Multipurpose Bot."""

import asyncio
import json
import logging
import logging.config
import os
from typing import Any

import aiofiles
import discord
from discord.ext import commands
from dotenv import load_dotenv

import database

log = logging.getLogger(f"App.{__name__}")
load_dotenv()

TOKEN: str = os.getenv("TOKEN") or ""


class MultipurposeBot(commands.Bot):
    """Multipurpose Bot."""

    departments: dict[str, Any]

    def __init__(self) -> None:
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        intents.voice_states = True
        intents.guilds = True
        intents.typing = False
        super().__init__(command_prefix="&", intents=intents)

    async def cached_fetch_user(self, user_id: int) -> discord.User:
        """Check cache first for a User before checking Discord itself."""
        user = self.get_user(user_id)
        if user is None:
            user = await self.fetch_user(user_id)
        return user

    async def setup_hook(self) -> None:
        """Load all cogs and setup dependencies."""
        os.makedirs("logs", exist_ok=True)
        db = database.Database()
        await db.connect()

        async with aiofiles.open("logging.json", "r", encoding="utf-8") as f:
            config = json.loads(await f.read())
        logging.config.dictConfig(config)

        self.departments = await database.servers.get_all_departments()
        print(self.departments)
        # load all discord handlers automatically
        cogs_dir = os.path.join(os.path.dirname(__file__), "features")
        for filename in os.listdir(cogs_dir):
            if not filename.endswith(".py"):
                continue
            await self.load_extension(f"features.{filename[:-3]}")
            log.debug(f"Loaded Feature: {filename}")

        for server in {server for department in self.departments.values() for server in department["servers"]}:
            await self.tree.sync(guild=server)

        log.info("Finished Bot Bootstrapping")

    async def on_ready(self) -> None:
        """Fire Login Things."""
        log.info(f"Logged in as {self.user}")


async def main() -> None:
    """Main Function."""  # noqa: D401
    assert TOKEN != ""
    bot = MultipurposeBot()
    try:
        db = database.Database()
        async with bot:
            await bot.start(TOKEN)
    finally:
        await db.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log.warning("Keyboard Interrupt detected. Exiting...")
