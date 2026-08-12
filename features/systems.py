"""Systems Cog - For use of the Systems Department."""

from __future__ import annotations

import json
import logging
import re
import time
from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

import database
from database.staff import has_staff_admin_perms

if TYPE_CHECKING:
    from aiosqlite.cursor import Cursor

    from main import MultipurposeBot

log = logging.getLogger(f"App.{__name__}")
load_dotenv()


class System(commands.Cog):
    """Systems Cog: Commands are for administration of the whole system."""

    def __init__(self, bot: MultipurposeBot) -> None:
        self.bot = bot
        # for guild in self.bot.departments["sys"]["servers"]: # for temp purposes everyone has access to the commands specified
        # self.bot.tree.add_command(self.say)
        # self.bot.tree.add_command(self.configure)

    @app_commands.command(name="say", description="Say something as the Bot")
    @app_commands.guilds()
    async def say(self, interaction: discord.Interaction, message: str) -> None:
        """Say something as the bot."""
        await interaction.response.send_message("Sent message.")
        await interaction.followup.send(message)

    @app_commands.command(name="ping", description="Pong!")
    async def ping(self, interaction: discord.Interaction) -> None:
        """Test Bot Connectivity, Will give Roundtrip Statistics."""
        start = time.monotonic()
        await interaction.response.send_message("Pinging...", ephemeral=True)
        end = time.monotonic()
        roundtrip = (end - start) * 1000

        await interaction.edit_original_response(content=f"Pong!\n\nRoundtrip: `{roundtrip:.2f}ms`\nWebsocket: `{interaction.client.latency * 1000:.2f}ms`")

    configure = app_commands.Group(name="configure", description="Configure ")

    @configure.command(name="server", description="Configure the Servers to register")
    @app_commands.choices(operation=[app_commands.Choice(name="Add", value=1), app_commands.Choice(name="Remove", value=0)])
    async def config_server(self, interaction: discord.Interaction, department: str, server_id: int, operation: app_commands.Choice[int]) -> None:
        """Adds/Removes servers of a Department. Running on a server will add all of the departments command on the said server."""
        # TODO: logging
        """Adds/Removes a Server from Registration."""
        if not await has_staff_admin_perms(discord_id=interaction.user.id):
            await interaction.response.send_message("You are not permitted.", ephemeral=True)
        query = ""
        match operation.value:
            case 1:
                query = "UPDATE staff_department SET servers = jsonb_insert(servers, '$[#]', :server_id) WHERE key = :key;"
            case 0:
                query = "UPDATE staff_department SET servers = jsonb(COALESCE((SELECT jsonb_group_array(value) FROM json_each(servers) WHERE value != :server_id), '[]')) WHERE key = :key;"
        db = database.Database()
        await db.execute(query, params={"key": department, "server_id": server_id})
        await interaction.response.send_message(f"Updated. {'Added' if operation.value else 'Removed'} {server_id} to {department}")

    _KEY_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,64}$")

    @configure.command(name="department", description="Configure the Department Settings")
    async def config_department(self, interaction: discord.Interaction, department: str, key: str, value: str) -> None:
        """Sets a key/value pair in the Department's configuration."""
        if not await has_staff_admin_perms(discord_id=interaction.user.id):
            await interaction.response.send_message("You are not permitted.", ephemeral=True)
            return

        if not self._KEY_PATTERN.fullmatch(key):
            await interaction.response.send_message("Invalid key: only letters, numbers, `_` and `-` are allowed.", ephemeral=True)
            return

        db = database.Database()

        query = """
            UPDATE staff_department
            SET configuration = jsonb_set(configuration, '$.' || :key, jsonb(:value)),
                edited_at = CURRENT_TIMESTAMP
            WHERE key = :department
        """
        # BUG: value is always stored as a str, numerical things arent being stored as numbers
        result: Cursor = await db.execute(query, {"key": key, "value": json.dumps(value), "department": department})

        if result.rowcount == 0:
            await interaction.response.send_message("Department not found.", ephemeral=True)
            return

        await interaction.response.send_message(f"Set `{key}` = `{value}` in `{department}` configuration.", ephemeral=True)

    @app_commands.command(name="reload", description="Reload command Guilds globally.")
    @app_commands.allowed_contexts(guilds=False, dms=True, private_channels=False)
    async def reload(self, interaction: discord.Interaction) -> None:
        """Reload commands."""
        await interaction.response.send_message("Refreshing... Reload Discord for commands to be registered.")
        await self.bot.reload_command()


async def setup(bot: MultipurposeBot) -> None:  # noqa: D103
    await bot.add_cog(System(bot))
