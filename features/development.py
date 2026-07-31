"""Development Cog - For use of the Development Department and Testing Team."""

import asyncio
import logging
from typing import Any, Self, cast

import discord
import discord.utils
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
        log.debug("message doesn't have media attached", extra={"attachments": message.attachments})
        return
    if not await database.staff.get_staff_by_discord_user(message.author):
        log.warning("Member is not registered.", extra={"member": message.author})
        await database.staff.register_staff(message.author)
    db = database.Database()
    await db.execute(bug_report_register_query, {"message_id": message.id, "author_id": message.author.id, "content": message.content})

    await message.add_reaction("✅")
    await message.add_reaction("❌")

    log.info(
        "Bug Registered.",
        extra={
            "author": message.author.display_name,
            "channel": message.channel.name,
            "id": message.id,
            "content": message.content,
            "attachments": message.attachments,
        },
    )


async def get_tester_stats(member: discord.Member | None = None):
    stat_lookup_query = f"""
    SELECT
        author,
        SUM(CASE WHEN decision = 1 THEN 1 ELSE 0 END) AS accepted,
        SUM(CASE WHEN decision = -1 THEN 1 ELSE 0 END) AS rejected,
        SUM(CASE WHEN decision = 0 THEN 1 ELSE 0 END) AS pending
    FROM department_tester_reports r
    {"JOIN staff_staff s ON s.staff_id = r.author WHERE s.discord_id = :id" if member else ""}
    GROUP BY r.author;
    """
    params: dict[str, Any] = {}
    db = database.Database()
    if member:
        params["id"] = member.id
        return await db.fetchone(stat_lookup_query, params)
    else:
        return await db.fetchall(stat_lookup_query, params)


async def decide_report(decision: discord.PartialEmoji, decider: discord.Member, message: discord.Message) -> None:
    """Decide if a Bug Report is Accepted or not."""
    assert Development.instance, "This function can only be called with Development Cog loaded."
    if message.guild != Development.instance.testing_guild:
        log.debug("reaction not made in testing server.", extra={"guild": message.guild})
        return
    if message.channel not in Development.instance.bug_report_channels:
        log.debug("reaction not made in a bug report channel.", extra={"channel": message.channel})
        return
    if decider.roles not in Development.instance.admin_role_ids:
        log.debug("reaction not made by an admin.", extra={"user": decider, "roles": decider.roles})
        return

    is_accepted = 0
    if decision.name == "✅":
        is_accepted = 1
    elif decision.name == "❌":
        is_accepted = -1
    else:
        log.debug("uhhhh", extra={"reaction": decision})
        return

    query = """
    UPDATE department_tester_reports
    SET decision=:decision, fixer=(SELECT s.staff_id FROM staff_staff s WHERE s.discord_id = :fixer_account_id), fixed_at=CURRENT_TIMESTAMP
    WHERE id=:bug_id
    """
    db = database.Database()
    await db.execute(query, {"decision": is_accepted, "fixer_account_id": decider.id, "bug_id": message.id})

    log.info("Bug Decided.", extra={"author": message.author.display_name, "decider": decider.display_name, "decision": is_accepted})


class Development(commands.Cog):
    """Development Cog: Contains Bug Logger."""

    instance: Self | None = None
    testing_guild: discord.Guild
    bug_report_channels: list[discord.TextChannel]
    admin_role_ids: list[discord.Role]
    minimum_report_quota: int
    leaderboard_channel: discord.TextChannel
    leaderboard_message: discord.Message
    logging_channel: discord.TextChannel
    start_of_week: int

    def __init__(self, bot: MultipurposeBot) -> None:
        Development.instance = self
        self.bot: MultipurposeBot = bot

        for guild in self.bot.departments["qa"]["servers"]:
            pass
            # self.bot.tree.add_command(self.qaCommands, guild=guild)

    async def cog_load(self) -> None:
        """Configure internal variables needed by the cog."""
        config: dict[str, Any] = self.bot.departments["dev"]["configuration"]

        testing_guild: discord.Guild | None = await self.bot.cached_fetch_guild(config["testing_guild"])
        if not isinstance(testing_guild, discord.Guild):
            raise TypeError("Configured Testing Guild is not supported")
        self.testing_guild: discord.Guild = testing_guild

        bug_report_channels: list[Any | None] = [await self.bot.cached_fetch_channel(cast(int, channel)) for channel in config["bug_report_channels"]]
        if not all(isinstance(ch, discord.TextChannel) for ch in bug_report_channels):
            raise TypeError("All bug_report_channels must be discord.TextChannel")
        self.bug_report_channels: list[discord.TextChannel] = cast(list[discord.TextChannel], bug_report_channels)

        admin_role_ids: list[discord.Role | None] = [testing_guild.get_role(role_id) for role_id in config["admin_role_ids"]]
        if not all(isinstance(id, discord.Role) for id in admin_role_ids):
            raise TypeError("One configured Admin Role ID is invalid.")
        self.admin_role_ids: list[discord.Role] = cast(list[discord.Role], admin_role_ids)

        self.minimum_report_quota: int = config["minimum_report_quota"]

        leaderboard_channel: Any = await self.bot.cached_fetch_channel(config["leaderboard_channel"])
        if not isinstance(leaderboard_channel, discord.TextChannel):
            raise TypeError("Configured Leaderboard Channel Type is not supported")
        self.leaderboard_channel: discord.TextChannel = leaderboard_channel

        leaderboard_message: discord.Message | None = await self.bot.cached_fetch_message(self.leaderboard_channel, config["leaderboard_message"])
        if not leaderboard_message:
            leaderboard_message: discord.Message = await leaderboard_channel.send("Leaderboard")  # TODO: replace w/ a real leaderboard
        self.leaderboard_message: discord.Message = leaderboard_message

        logging_channel: Any = await self.bot.cached_fetch_channel(config["logging_channel"])
        if not isinstance(logging_channel, discord.TextChannel):
            raise TypeError("Configured Logging Channel Type is not supported")
        self.logging_channel: discord.TextChannel = logging_channel

        self.start_of_week: int = config["start_of_week"]

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        """Listen for Messages sent in a Bug Report."""
        if message.author == self.bot.user:
            log.debug("message from bot")
            return
        if message.channel not in self.bug_report_channels:
            log.debug("message not in bugreports", extra={"channel": message.channel, "bugreportchannel": self.bug_report_channels})
            return
        await register_report(message)

    @commands.Cog.listener()
    async def on_raw_message_delete(self, payload: discord.RawMessageDeleteEvent) -> None:
        """Listen for Bug Report manual deletes."""

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent) -> None:
        """Listen for a Reaction on Bug Reports."""
        if not payload.member or payload.member.bot:
            log.debug(
                "Reaction is sent by someone in DMs, or the bot itself.",
                extra={"user": payload.user_id, "is_itself": payload.user_id == self.bot.user.id},  # ty: ignore[unresolved-attribute]
            )
            return

        channel = await self.bot.cached_fetch_channel(payload.channel_id)
        if not isinstance(channel, (discord.TextChannel, discord.Thread)):
            log.debug("Reaction is sent on a deliberately ignored channel.", extra={"channel": channel})
            return
        message: discord.Message | None = await self.bot.cached_fetch_message(channel, payload.message_id)
        log.debug('aaa', extra={"payload": payload, "channel": channel, "bug_message": message})
        await decide_report(payload.emoji, payload.member, message)


async def setup(bot: MultipurposeBot) -> None:  # noqa: D103
    await bot.add_cog(Development(bot))
