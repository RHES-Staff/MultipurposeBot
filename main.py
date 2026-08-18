"""Multipurpose Bot."""

from __future__ import annotations

import asyncio
import importlib
import json
import logging
import logging.config
import os
import pkgutil
import sys
from itertools import chain
from pathlib import Path
from typing import TYPE_CHECKING, Any

import aiofiles
import discord
import uvicorn
from discord.ext import commands
from dotenv import load_dotenv
from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware

import database
from database.models import Department

if TYPE_CHECKING:
    from collections.abc import Coroutine
    from types import ModuleType

log: logging.Logger = logging.getLogger(f"App.{__name__}")
load_dotenv()

TOKEN: str = os.getenv("TOKEN") or ""
API_HOST: str = os.getenv("API_HOST") or "0.0.0.0"
API_PORT: str = os.getenv("TOKAPI_PORTEN") or "8000"


class ConsoleFormatter(logging.Formatter):
    """Formatter Module for Logs."""

    STANDARD_FIELDS: set[str] = set(logging.LogRecord("", 0, "", 0, "", (), None).__dict__) | {"message", "asctime"}

    def format(self, record: logging.LogRecord) -> str:  # noqa: D102
        base: str = super().format(record)
        extras: dict[str, object] = {k: v for k, v in record.__dict__.items() if k not in self.STANDARD_FIELDS}
        if extras:
            base += " " + str(extras)
        return base


class MultipurposeBot(commands.Bot):
    """Multipurpose Bot."""

    departments: list[Department]
    _queue: asyncio.Queue[Coroutine] = asyncio.Queue()
    _worker_task: asyncio.Task | None = None

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
        """Fetches a user, checking local cache before querying Discord.

        Args:
            user_id: The ID of the user to fetch.

        Returns:
            The user if found, or None if they do not exist.
        """
        return self.get_user(user_id) or await self.fetch_user(user_id)

    async def cached_fetch_member(self, guild: discord.Guild, member_id: int) -> discord.Member | None:
        """Fetches a guild member, checking local cache before querying Discord.

        Args:
            guild: The guild to search within.
            member_id: The ID of the member to fetch.

        Returns:
            The member if found, or None if they do not exist.
        """
        return guild.get_member(member_id) or await guild.fetch_member(member_id)

    async def cached_fetch_guild(self, guild_id: int) -> discord.Guild | None:
        """Fetches a guild, checking local cache before querying Discord.

        Args:
            guild_id: The ID of the guild to fetch.

        Returns:
            The guild if found, or None if it does not exist.
        """
        return self.get_guild(guild_id) or await self.fetch_guild(guild_id)

    async def cached_fetch_channel(self, channel_id: int) -> discord.abc.GuildChannel | discord.abc.PrivateChannel | discord.Thread | None:
        """Fetches a channel, checking local cache before querying Discord.

        Args:
            channel_id: The ID of the channel to fetch.

        Returns:
            The channel if found, or None if it does not exist.
        """
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
        """Fetches a message, checking local cache before querying Discord.

        Args:
            channel: The channel containing the message.
            message_id: The ID of the message to fetch.

        Returns:
            The message if found, or None if it was not found.
        """
        cached_msg: discord.Message | None = discord.utils.get(self.cached_messages, id=message_id)
        if cached_msg:
            return cached_msg
        try:
            return await channel.fetch_message(message_id)
        except discord.NotFound:
            return None

    # helper functions for fire-and-forget funcs
    @classmethod
    def start_worker(cls) -> None:
        """Starts the background Async Queue worker task if it is not running."""
        if cls._worker_task is None:
            cls._worker_task: asyncio.Task[None] = asyncio.create_task(cls._worker())

    @classmethod
    async def _worker(cls) -> None:
        while True:
            coro: Coroutine = await cls._queue.get()
            try:
                await coro
            except Exception:
                log.exception("Background task failed")
            finally:
                cls._queue.task_done()

    def fire_and_forget(self, coro: Coroutine) -> None:
        """Enqueues a coroutine to run sequentially on the background worker.

        Args:
            coro: The coroutine to execute.
        """
        self._queue.put_nowait(coro)

    async def reload_command(self) -> None:
        """Reloads Commands on the Command Tree."""
        self.tree.clear_commands(guild=None)
        for server in chain.from_iterable([dept.servers for dept in self.departments]):
            self.tree.clear_commands(guild=discord.Object(server))

        await self.reload_cogs()

        await self.tree.sync()
        for server in chain.from_iterable([dept.servers for dept in self.departments]):
            await self.tree.sync(guild=discord.Object(server))

    async def reload_cogs(self) -> None:
        """Reloads Cogs."""
        for ext in list(self.extensions.keys()):
            await self.reload_extension(ext)

    async def setup_hook(self) -> None:
        """Load all cogs and setup dependencies."""
        self.departments: list[Department] = await database.department.get_all_departments()
        self.start_worker()
        # load all discord handlers automatically
        cogs_dir: str = os.path.join(os.path.dirname(__file__), "features")
        for filename in os.listdir(cogs_dir):
            if not filename.endswith(".py") or filename == "__init__.py":
                continue
            await self.load_extension(f"features.{filename[:-3]}")
            log.debug(f"Loaded Feature: {filename}")

        # await self.tree.sync()  # needed for dm commands, so that we don't get locked out if ever we need to call reload commands <3

        log.info("Finished Bot Bootstrapping")

    async def on_ready(self) -> None:
        """Fire Login Things."""
        log.info(f"Logged in as {self.user}")


def init_api() -> FastAPI:
    """Initializes API Layer of App."""
    app = FastAPI()
    api_router = APIRouter()
    origins: list[str] = [
        "http://localhost:5173",  # for dev,
        "https://staffpanelicious.bonnybonnybonaktan.xyz",
        "https://www.hes.systems",
        "https://hes.systems"
    ]

    app.add_middleware(
        middleware_class=CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],  # BUG: create better cors whitelisting here
        allow_headers=["*"],
    )

    package = importlib.import_module("api")
    package_path: Path = Path(package.__file__).parent

    for _, module_name, is_pkg in pkgutil.iter_modules([str(package_path)]):
        if is_pkg:
            continue
        module: ModuleType = importlib.import_module(f"api.{module_name}")
        router: Any | None = getattr(module, "router", None)
        if router is not None:
            api_router.include_router(router, tags=[module_name])

    app.include_router(router=api_router, prefix="/api")
    return app


async def main() -> None:
    """Set up the whole app."""
    assert TOKEN != "", "Token not found."
    assert API_PORT.isdigit(), "Port not a valid Number"
    os.makedirs("logs", exist_ok=True)

    async with aiofiles.open("logging.json", "r", encoding="utf-8") as f:
        config: Any = json.loads(await f.read())
        if "--debug" in sys.argv:
            config["loggers"]["App"]["handlers"] = ["app_file", "console_debug"]
            config["handlers"]["console_debug"] = {"class": "logging.StreamHandler", "level": "DEBUG", "formatter": "console"}
    logging.config.dictConfig(config)

    bot = MultipurposeBot()

    db = database.Database()
    await db.connect("app.db")

    log.info("Starting API Server")
    server_config = uvicorn.Config(init_api(), host=API_HOST, port=int(API_PORT), loop="asyncio", log_level="info", log_config=None)
    server = uvicorn.Server(server_config)

    try:
        # as discord.py and uvicorn (FastAPI Server) are both async apps, API will be the Task, due to how discord.py is built
        if os.getenv("ENABLE_API") == "True":
            asyncio.create_task(server.serve())
        if os.getenv("ENABLE_BOT") == "True":
            async with bot:
                await bot.start(TOKEN)
        else:
            # in the case that the bot is disabled and api is enabled, it will exit asap. this function call prevents that fom happening
            await asyncio.Event().wait()
    finally:
        await db.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log.fatal("Keyboard Interrupt detected. Exiting...")
