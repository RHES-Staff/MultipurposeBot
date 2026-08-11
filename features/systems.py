"""Systems Cog - For use of the Systems Department."""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

if TYPE_CHECKING:
    from main import MultipurposeBot

log = logging.getLogger(f"App.{__name__}")
load_dotenv()


class System(commands.Cog):
    """Systems Cog: Commands are for administration of the whole system."""

    def __init__(self, bot: MultipurposeBot) -> None:
        self.bot = bot
        # for guild in self.bot.departments["sys"]["servers"]: # for temp purposes everyone has access to the commands specified
        self.bot.tree.add_command(self.say)
        self.bot.tree.add_command(self.ping)

    @app_commands.command(name="say", description="Say something as the Bot")
    async def say(self, interaction: discord.Interaction, message: str) -> None:
        """Say something as the bot."""
        await interaction.response.send_message("Sent message.")
        await interaction.followup.send(message)

    @app_commands.command(name="ping", description="Pong!")
    @app_commands.guilds()
    async def ping(self, interaction: discord.Interaction) -> None:
        """Test Bot Connectivity, Will give Roundtrip Statistics."""
        start = time.monotonic()
        await interaction.response.send_message("Pinging...", ephemeral=True)
        end = time.monotonic()
        roundtrip = (end - start) * 1000

        await interaction.edit_original_response(content=f"Pong!\n\nRoundtrip: `{roundtrip:.2f}ms`\nWebsocket: `{interaction.client.latency * 1000:.2f}ms`")

    @app_commands.command(name="configure", description="Configure the Servers you have")
    async def configure(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_message("TODO", ephemeral=True)


async def setup(bot: MultipurposeBot) -> None:  # noqa: D103
    await bot.add_cog(System(bot))
