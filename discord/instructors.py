""" Systems Cog - For use of the Systems Department
    Allowed 
"""

import logging

import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

import database

log = logging.getLogger(f"App.{__name__}")
load_dotenv()


class Instructor(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        for guild in self.bot.serverDepartments["inst"]["servers"]:
            self.bot.tree.add_command(self.instCommands, guild=guild)

    @app_commands.command(name="inst", description="Instructor Commands")
    async def instCommands(self, interaction):
        await interaction.response.send_message("Instructor-Specific Command", ephemeral=True)

async def setup(bot):
    await bot.add_cog(Instructor(bot))
