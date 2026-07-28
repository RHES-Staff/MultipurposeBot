"""Development Cog - For use of the Development Department and Testing Team."""

import logging

import discord
from discord.ext import commands
from dotenv import load_dotenv

import database
from main import MultipurposeBot

log = logging.getLogger(f"App.{__name__}")
load_dotenv()


async def register_report(message: discord.Message) -> None:
    """Register a Message as a Bug Report."""
    bug_report_register_query = """
    INSERT INTO department_tester_reports (id, author, content)
    VALUES (:message_id, (SELECT staff_id FROM staff_staff WHERE discord_id = :author_id), :content)
    """ 
    if not any((att.content_type and (att.content_type.startswith("image/") or att.content_type.startswith("video/"))) for att in message.attachments):
        return
    db = database.Database()
    await db.execute(bug_report_register_query, {"message_id": message.id, "author_id": message.author.id, "content": message.content})
    log.info("Bug Registered.", extra={"author": message.author.id})


async def decide_report(decision: discord.Reaction) -> None:
    """Decide if a Bug Report is Accepted or not."""
    log.info("Bug Registered.", extra={"author": decision.message.author.id})


class Development(commands.Cog):
    """Development Cog: Contains Bug Logger."""

    def __init__(self, bot: MultipurposeBot) -> None:
        self.bot = bot
        for guild in self.bot.departments["qa"]["servers"]:
            pass
            # self.bot.tree.add_command(self.qaCommands, guild=guild)

        # TODO: put this shit in config
        self.bug_report_channels = ["0"]
        self.admin_role_ids = ["0"]
        self.minimum_report_quota = 6
        self.leaderboard_channel = 0
        self.leaderboard_message = 0
        self.start_of_week = 0  # 0 = sunday, 6 = saturday

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        """Listen for Messages sent in a Bug Report."""
        if message.author == self.bot.user:
            return

        if message.channel.id not in self.bug_report_channels:
            return
        await register_report(message)

    @commands.Cog.listener()
    async def on_raw_message_delete(self, payload: discord.RawMessageDeleteEvent) -> None:
        """Listen for Bug Report manual deletes."""

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent) -> None:
        """Listen for a Reaction on Bug Reports."""
        if payload.member and payload.member.bot:
            return
        if payload.guild_id is None:
            return


async def setup(bot: MultipurposeBot) -> None:  # noqa: D103
    await bot.add_cog(Development(bot))
