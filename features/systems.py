"""Systems Cog - For use of the Systems Department."""

import logging
import time

import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

# from database import Database
from main import MultipurposeBot

log = logging.getLogger(f"App.{__name__}")
load_dotenv()


class System(commands.Cog):
    """Systems Cog: Commands are for administration of the whole system."""

    def __init__(self, bot: MultipurposeBot) -> None:
        self.bot = bot
        for guild in self.bot.departments["sys"]["servers"]:
            self.bot.tree.add_command(self.say, guild=guild)
            self.bot.tree.add_command(self.ping, guild=guild)

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


async def setup(bot: MultipurposeBot) -> None:  # noqa: D103
    await bot.add_cog(System(bot))
