""" Development Cog - For use of the Development Department and Testing Team 
"""

import logging

import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

log = logging.getLogger(f"App.{__name__}")
load_dotenv()


class Development(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        for guild in self.bot.serverDepartments["qa"]["servers"]:
            pass
            # self.bot.tree.add_command(self.qaCommands, guild=guild)
        
        # TODO: put this shit in config
        self.bugReportChannels = ["0"]
        self.adminRoleIds = ["0"]
        self.minimumReportQuota = 6

async def setup(bot):
    await bot.add_cog(Development(bot))