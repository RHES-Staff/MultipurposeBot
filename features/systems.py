""" Systems Cog - For use of the Systems Department
    Allowed 
"""

import logging
import time

import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

log = logging.getLogger(f"App.{__name__}")
load_dotenv()


class System(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        for guild in self.bot.serverDepartments["sys"]["servers"]:
            self.bot.tree.add_command(self.say, guild=guild)
            self.bot.tree.add_command(self.ping, guild=guild)
    
    @app_commands.command(name="say", description="Say something as the Bot")
    async def say(self, interaction, message: str):
        # Says a message as the bot
        await interaction.channel.send(message)
        await interaction.response.send_message("Sent Message.", ephemeral=True)

    @app_commands.command(name="ping", description="Pong!")
    @app_commands.guilds()
    async def ping(self, interaction: discord.Interaction):
        # Test Bot Connectivity.
        start = time.monotonic()
        await interaction.response.send_message("Pinging...", ephemeral=True)
        end = time.monotonic()
        roundtrip = (end - start) * 1000

        await interaction.edit_original_response(
            content=f"Pong!\n\nRoundtrip: `{roundtrip:.2f}ms`\nWebsocket: `{interaction.client.latency*1000:.2f}ms`"
        )

async def setup(bot):
    await bot.add_cog(System(bot))
