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

STANDARD_FIELDS = set(logging.LogRecord('', 0, '', 0, '', (), None).__dict__) | {'message', 'asctime'}
class ConsoleFormatter(logging.Formatter):
    def format(self, record):
        base = super().format(record)
        extras = {k: v for k, v in record.__dict__.items() if k not in STANDARD_FIELDS}
        if extras:
            base += " " + str(extras)
        return base

class MultipurposeBot(commands.Bot):
    """Multipurpose Bot."""

    departments: dict[str, Any]

    def __init__(self) -> None:
        intents: discord.Intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        intents.voice_states = True
        intents.guilds = True
        intents.typing = False
        super().__init__(command_prefix="&", intents=intents)

    # helper functions for caching
    async def cached_fetch_user(self, user_id: int) -> discord.User | None:
        """Check cache first for a User before checking Discord itself."""
        return self.get_user(user_id) or await self.fetch_user(user_id)

    async def cached_fetch_member(self, guild: discord.Guild, member_id: int) -> discord.Member | None:
        """Check cache first for a Guild Member before fetching from Discord."""
        return guild.get_member(member_id) or await guild.fetch_member(member_id)

    async def cached_fetch_guild(self, guild_id: int) -> discord.Guild | None:
        """Check cache first for a Guild Member before fetching from Discord."""
        return self.get_guild(guild_id) or await self.fetch_guild(guild_id)

    async def cached_fetch_channel(self, channel_id: int) -> discord.abc.GuildChannel | discord.abc.PrivateChannel | discord.Thread | None:
        """Check cache first for a Channel before fetching from Discord."""
        return self.get_channel(channel_id) or await self.fetch_channel(channel_id)

    async def cached_fetch_message(
        self,
        channel: discord.TextChannel
        | discord.VoiceChannel
        | discord.StageChannel
        | discord.Thread
        | discord.DMChannel
        | discord.GroupChannel
        | discord.PartialMessageable,
        message_id: int,
    ) -> discord.Message | None:
        """Check cache first for a Message before fetching from Discord."""
        cached_msg: discord.Message | None = discord.utils.get(self.cached_messages, id=message_id)
        if cached_msg:
            return cached_msg
        try:
            return await channel.fetch_message(message_id)
        except discord.NotFound:
            return None

    async def setup_hook(self, **kwargs: str) -> None:
        """Load all cogs and setup dependencies."""
        os.makedirs("logs", exist_ok=True)
        db = database.Database()
        await db.connect(kwargs.get("db_path", "app.db"))

        async with aiofiles.open("logging.json", "r", encoding="utf-8") as f:
            config: Any = json.loads(await f.read())
        logging.config.dictConfig(config)

        self.departments: dict[str, Any] = await database.servers.get_all_departments()

        # load all discord handlers automatically
        cogs_dir: str = os.path.join(os.path.dirname(__file__), "features")
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
    """Set up the whole app."""
    assert TOKEN != "", "Token not found."
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
