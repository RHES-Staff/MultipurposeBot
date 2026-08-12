"""Systems Cog - For use of the Systems Department."""

from __future__ import annotations

import logging
import re
import time
from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

from database.department import set_department_config, set_department_server
from database.staff import has_staff_admin_perms

if TYPE_CHECKING:
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
        start: int | float = time.monotonic()
        await interaction.response.send_message("Pinging...", ephemeral=True)
        end: int | float = time.monotonic()
        roundtrip: int | float = (end - start) * 1000

        await interaction.edit_original_response(content=f"Pong!\n\nRoundtrip: `{roundtrip:.2f}ms`\nWebsocket: `{interaction.client.latency * 1000:.2f}ms`")

    configure = app_commands.Group(name="configure", description="Configure ")

    @configure.command(name="server", description="Configure the Servers to register")
    @app_commands.choices(operation=[app_commands.Choice(name="Add", value=1), app_commands.Choice(name="Remove", value=0)])
    async def config_server(self, interaction: discord.Interaction, department: str, server_id: int, operation: app_commands.Choice[int]) -> None:
        """Adds/Removes servers of a Department. Running on a server will add all of the departments command on the said server."""
        # TODO: logging
        if not await has_staff_admin_perms(discord_id=interaction.user.id):
            await interaction.response.send_message("You are not permitted.", ephemeral=True)
            return

        await set_department_server(department, server_id, add=bool(operation.value))

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

        if not await set_department_config(department, key, value):
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
