"""Development Cog - For use of the Development Department and Testing Team."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any, Self, cast, overload

import discord
from discord.ext import commands
from dotenv import load_dotenv

import database
from features.views.leaderboard import SingleTesterStatEmbed

if TYPE_CHECKING:
    import aiosqlite
    from discord.abc import GuildChannel, PrivateChannel
    from discord.threads import Thread

    from main import MultipurposeBot

log: logging.Logger = logging.getLogger(f"App.{__name__}")
load_dotenv()


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

        for guild in self.bot.departments["dev"]["servers"]:
            self.bot.tree.add_command(self.stats, guild=guild)


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

        try:
            leaderboard_message: discord.Message | None = await self.bot.cached_fetch_message(self.leaderboard_channel, config["leaderboard_message"])
            if not leaderboard_message:
                raise ValueError("Missing Leaderboard Message")
        except (ValueError, discord.errors.Forbidden):
            leaderboard_message: discord.Message = await leaderboard_channel.send("Leaderboard")  # TODO: replace w/ a real leaderboard
        self.leaderboard_message: discord.Message = leaderboard_message

        logging_channel: Any = await self.bot.cached_fetch_channel(config["logging_channel"])
        if not isinstance(logging_channel, discord.TextChannel):
            raise TypeError("Configured Logging Channel Type is not supported")
        self.logging_channel: discord.TextChannel = logging_channel

        self.start_of_week: int = config["start_of_week"]

    @discord.app_commands.command(name="stats", description="Check your Stats for Bug Reports.")
    async def stats(self, interaction: discord.Interaction) -> None:
        """Command Listener for /stats."""
        log.debug("command received", extra={"command": "/stats", "interaction": interaction})
        tester_stats: SingleTesterStatEmbed = SingleTesterStatEmbed(self, interaction.user)
        await interaction.response.send_message(embed=tester_stats, files=tester_stats.files)

    # Event Listeners
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        """Listen for Messages sent in a Bug Report."""
        if message.author == self.bot.user:
            log.debug("message from bot")
            return
        log.debug("message received.", extra={"message_obj": message})
        if discord.Object(message.author.guild.id) in self.bot.departments["dev"]["servers"]:
            # this means author is somehow a staff. the question is what dept?
            log.warning("Member is not registered.", extra={"id": message.author.id, "username": message.author.name})
            await database.staff.register_staff(message.author)
        await self.register_report(message)

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

        channel: GuildChannel | PrivateChannel | Thread | None = await self.bot.cached_fetch_channel(payload.channel_id)
        if not isinstance(channel, (discord.TextChannel, discord.Thread)):
            log.debug("Reaction is sent on a deliberately ignored channel.", extra={"channel": channel})
            return
        message: discord.Message | None = await self.bot.cached_fetch_message(channel, payload.message_id)
        if not message:
            log.warning("for some reason the reacted message returned a nil.", extra={"reaction": payload, "channel": channel})
            return
        if message.author in self.bot.departments["dev"]["servers"]:
            # this means author is somehow a staff. the question is what dept?
            log.warning("Member is not registered.", extra={"member": message.author})
            await database.staff.register_staff(message.author)
        await self.fix_report(payload.emoji, payload.member, message)

    # Business Logic
    async def register_report(self, message: discord.Message) -> None:
        """Register a Message as a Bug Report."""
        if message.channel not in self.bug_report_channels:
            log.debug("message not in bugreports", extra={"channel": message.channel, "bugreportchannel": self.bug_report_channels})
            return
        if not any((att.content_type and (att.content_type.startswith("image/") or att.content_type.startswith("video/"))) for att in message.attachments):
            log.debug("message doesn't have media attached", extra={"attachments": message.attachments})
            return

        bug_report_register_query = """
        INSERT INTO department_tester_reports (id, author, content)
        VALUES (:message_id, (SELECT staff_id FROM staff_staff WHERE discord_id = :author_id), :content)
        """
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

    async def fix_report(self, decision: discord.PartialEmoji, decider: discord.Member, message: discord.Message) -> None:
        """Indicate that a Bug Report is Fixed or ignored."""
        if message.guild != self.testing_guild:
            log.debug("reaction not made in testing server.", extra={"guild": message.guild})
            return
        if message.channel not in self.bug_report_channels:
            log.debug("reaction not made in a bug report channel.", extra={"channel": message.channel})
            return
        if not any(role in self.admin_role_ids for role in decider.roles):
            log.debug("reaction not made by an admin.", extra={"user": decider, "roles": decider.roles})
            await message.remove_reaction(decision, decider)
            return
        if (is_accepted := {"✅": 1, "❌": -1}.get(decision.name)) is None:
            log.debug("reaction is not a valid decision", extra={"user": decider, "reaction": decision})
            return
        if not await self.get_bug(message):
            log.debug("message is not registered as a bug", extra={"message_object": message})
            return
        if not await database.staff.get_staff_by_discord_user(decider):
            log.warning("Member is not registered.", extra={"member": decider})
            await database.staff.register_staff(decider)

        query = """
        UPDATE department_tester_reports
        SET decision=:decision, fixer=(SELECT s.staff_id FROM staff_staff s WHERE s.discord_id = :fixer_account_id), fixed_at=CURRENT_TIMESTAMP
        WHERE id=:bug_id
        """
        db = database.Database()
        await db.execute(query, {"decision": is_accepted, "fixer_account_id": decider.id, "bug_id": message.id})
        await message.delete()  # TODO: wait for 3-5 seconds before deleting the bug report

        log.info("Bug Decided.", extra={"author": message.author.display_name, "decider": decider.display_name, "id": message.id, "decision": is_accepted})

    # Database Lookups
    def week_bounds(self, date: datetime | None = None, start_of_week: int | None = None) -> tuple[datetime, datetime]:
        """Get the start/end of a week based on a date. Defaults to today if no week is given."""
        date: datetime = date or datetime.now(tz=timezone.utc)
        start_of_week: int = start_of_week or self.start_of_week or 0
        dow: int = (date.weekday() + 1) % 7  # convert to 0=Sunday
        start: datetime = date - timedelta(days=(dow - start_of_week) % 7)
        start = datetime(start.year, start.month, start.day, tzinfo=date.tzinfo)
        end: datetime = start + timedelta(days=6, hours=23, minutes=59, seconds=59)
        return start, end

    async def get_bug(self, message: discord.Message) -> aiosqlite.Row | None:
        """Get a registered bug from the database."""
        bug_lookup_query = "SELECT * FROM department_tester_reports r WHERE id = :id"
        db = database.Database()
        return await db.fetchone(bug_lookup_query, {"id": message.id})

    @overload
    async def get_tester_stats(self, *, week: datetime | None = None) -> list[aiosqlite.Row]: ...
    @overload
    async def get_tester_stats(self, member: discord.Member | discord.User, *, week: datetime | None = None) -> aiosqlite.Row | None: ...
    async def get_tester_stats(self, member: discord.Member | discord.User | None = None, *, week: datetime | None = None):
        """Get a testers statistics from the database."""
        stat_lookup_query = f"""
        SELECT
            s.staff_id AS author,
            COALESCE(SUM(CASE WHEN r.decision = 1 THEN 1 ELSE 0 END), 0) AS accepted,
            COALESCE(SUM(CASE WHEN r.decision = -1 THEN 1 ELSE 0 END), 0) AS rejected,
            COALESCE(SUM(CASE WHEN r.decision = 0 THEN 1 ELSE 0 END), 0) AS pending
        FROM staff_staff s
        LEFT JOIN department_tester_reports r ON r.author = s.staff_id
        {"WHERE s.discord_id = :id" if member else ""}
        GROUP BY s.staff_id;
        """
        params: dict[str, Any] = {}
        db = database.Database()
        if member:
            params["id"] = member.id
            return await db.fetchone(stat_lookup_query, params)
        else:
            return await db.fetchall(stat_lookup_query, params)

    @overload
    async def get_developer_stats(self) -> list[aiosqlite.Row]: ...
    @overload
    async def get_developer_stats(self, member: discord.Member) -> aiosqlite.Row | None: ...
    async def get_developer_stats(self, member: discord.Member | None = None):
        """Get a developers statistics from the database."""
        stat_lookup_query = f"""
        SELECT
            fixer,
            SUM(CASE WHEN decision = 1 THEN 1 ELSE 0 END) AS accepted,
            SUM(CASE WHEN decision = -1 THEN 1 ELSE 0 END) AS rejected
        FROM department_tester_reports r
        {"JOIN staff_staff s ON s.staff_id = r.fixer WHERE s.discord_id = :id" if member else ""}
        GROUP BY r.fixer;
        """
        params: dict[str, Any] = {}
        db = database.Database()
        if member:
            params["id"] = member.id
            return await db.fetchone(stat_lookup_query, params)
        else:
            return await db.fetchall(stat_lookup_query, params)


async def setup(bot: MultipurposeBot) -> None:  # noqa: D103
    await bot.add_cog(Development(bot))
