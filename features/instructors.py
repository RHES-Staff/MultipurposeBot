"""Instructors  Cog - For use of the Instruction Department."""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

if TYPE_CHECKING:
    from main import MultipurposeBot

log = logging.getLogger(f"App.{__name__}")
load_dotenv()


class Instructor(commands.Cog):
    """Instructor Cog: Contains Instructor Bot."""

    def __init__(self, bot: MultipurposeBot) -> None:
        self.bot: MultipurposeBot = bot
        for guild in self.bot.departments["inst"]["servers"]:
            self.bot.tree.add_command(self.inst_commands, guild=guild)

    @app_commands.command(name="inst", description="Instructor Commands")
    async def inst_commands(self, interaction: discord.Interaction) -> None:
        """Instructor-Specific Commands."""
        await interaction.response.send_message("Instructor-Specific Command", ephemeral=True)


async def setup(bot: MultipurposeBot) -> None:  # noqa: D103
    await bot.add_cog(Instructor(bot))
