"""Development Cog - For use of the Development Department and Testing Team."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any, Self, cast, overload

import discord
from discord.ext import commands

import database
from database.department import set_department_config
from database.models import Department
from features.views.leaderboard import LogsEmbed, SingleTesterStatEmbed, TesterStatEmbed

if TYPE_CHECKING:
    import aiosqlite

    from main import MultipurposeBot

log: logging.Logger = logging.getLogger(f"App.{__name__}")


class Development(commands.Cog):
    """Development Cog: Contains Bug Logger."""

    instance: Self | None = None
    testing_guild: discord.Guild
    bug_report_channels: list[discord.TextChannel]
    minimum_report_quota: int
    leaderboard_channel: discord.TextChannel
    _leaderboard_message: discord.Message
    logging_channel: discord.TextChannel
    start_of_week: int
    tester_role: discord.Role
    head_of_tester_role: discord.Role
    developer_role: discord.Role

    _config: dict[str, Any]
    _servers: list[int]

    def __init__(self, bot: MultipurposeBot) -> None:
        Development.instance = self
        self.bot: MultipurposeBot = bot

    @property
    def leaderboard_message(self) -> discord.Message:  # noqa: D102
        return self._leaderboard_message

    @leaderboard_message.setter
    def leaderboard_message(self, message: discord.Message) -> None:
        """Set the active leaderboard message and asynchronously update the database config.

        Args:
            message: The Discord message object representing the new leaderboard.
        """
        asyncio.create_task(set_department_config("dev", "leaderboard_message", str(message.id)))
        self._leaderboard_message: discord.Message = message

    async def cog_load(self) -> None:
        """Configure internal variables needed by the cog."""
        devdept: Department | None = await database.department.get_department("dev")
        if not devdept:
            raise ValueError("Development Configuration cannot be found.")
        config: dict[str, Any] = devdept.configuration
        self._config: dict[str, Any] = config
        self._servers: list[discord.Object] = [discord.Object(id=id) for id in devdept.servers]

        testing_guild: discord.Guild | None = await self.bot.cached_fetch_guild(config["testing_guild"])
        if not isinstance(testing_guild, discord.Guild):
            raise TypeError("Configured Testing Guild is not supported")
        self.testing_guild: discord.Guild = testing_guild

        bug_report_channels: list[Any | None] = [await self.bot.cached_fetch_channel(cast(int, channel)) for channel in config["bug_report_channels"]]
        if not all(isinstance(ch, discord.TextChannel) for ch in bug_report_channels):
            raise TypeError("All bug_report_channels must be discord.TextChannel")
        self.bug_report_channels: list[discord.TextChannel] = cast(list[discord.TextChannel], bug_report_channels)

        tester_role: discord.Role | None = testing_guild.get_role(config["tester_role"])
        if not tester_role:
            raise TypeError("No Tester Role found.")
        self.tester_role: discord.Role = tester_role
        head_of_tester_role: discord.Role | None = testing_guild.get_role(config["head_of_tester_role"])
        if not head_of_tester_role:
            raise TypeError("No Head of Testing Role found.")
        self.head_of_tester_role: discord.Role = head_of_tester_role
        developer_role: discord.Role | None = testing_guild.get_role(config["developer_role"])
        if not developer_role:
            raise TypeError("No Developer Role found.")
        self.developer_role: discord.Role = developer_role

        self.minimum_report_quota: int = config["minimum_report_quota"]

        leaderboard_channel: Any = await self.bot.cached_fetch_channel(config["leaderboard_channel"])
        if not isinstance(leaderboard_channel, discord.TextChannel):
            raise TypeError("Configured Leaderboard Channel Type is not supported")
        self.leaderboard_channel: discord.TextChannel = leaderboard_channel

        self.start_of_week: int = config["start_of_week"]

        self.bot.fire_and_forget(self.refresh_leaderboard())

        logging_channel: Any = await self.bot.cached_fetch_channel(config["logging_channel"])
        if not isinstance(logging_channel, discord.TextChannel):
            raise TypeError("Configured Logging Channel Type is not supported")
        self.logging_channel: discord.TextChannel = logging_channel

        for guild in devdept.servers:
            self.bot.tree.add_command(self.stats, guild=discord.Object(guild))

    @discord.app_commands.command(name="stats", description="Check your Stats for Bug Reports.")
    async def stats(self, interaction: discord.Interaction) -> None:
        """Command Listener for /stats."""
        log.debug("command received", extra={"command": "/stats", "interaction": interaction})
        tester_stats: SingleTesterStatEmbed = await SingleTesterStatEmbed.create(self, interaction.user)
        await interaction.response.send_message(embed=tester_stats, files=tester_stats.files, ephemeral=True)

    # Event Listeners
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        """Listen for Messages sent in a Bug Report."""
        if message.author == self.bot.user:
            log.debug("message from bot")
            return
        log.debug("message received.", extra={"message_obj": message})
        await self.check_if_staff(message.author)
        await self.validate_new_bug_report(message)

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
        log.debug(
            "Reaction made",
            extra={"user": payload.user_id, "is_itself": payload.user_id == self.bot.user.id},  # ty: ignore[unresolved-attribute]
        )
        await self.fix_report(payload)

    async def refresh_leaderboard(self) -> None:
        """Helper function to automatically refresh Leaderboard View."""
        message_id: int = self._config["leaderboard_message"]
        if not hasattr(self, "_leaderboard_channel"):
            try:
                leaderboard_message: discord.Message | None = await self.bot.cached_fetch_message(self.leaderboard_channel, message_id)
                if not leaderboard_message:
                    raise ValueError("Missing Leaderboard Message")
            except (ValueError, discord.errors.Forbidden) as e:
                log.debug("Controlled Exception occured.", extra={"error": e, "supposed_id": message_id})
                leaderboard_message: discord.Message = await self.leaderboard_channel.send("Refreshing Leaderboard...")
                log.info("Sent new Leaderboard Message", extra={"new_id": leaderboard_message})
            self.leaderboard_message: discord.Message = leaderboard_message

        tester_leaderboard: TesterStatEmbed = await TesterStatEmbed.create(self)
        await self.leaderboard_message.edit(content="", embed=tester_leaderboard, attachments=tester_leaderboard.files)
        log.debug("Refreshed Leaderbaord successfully")

    # Business Logic
    async def check_if_staff(self, member: discord.Member) -> None:
        """Verify if a Discord member is registered as staff.

        Check if the member belongs to a recognized server. Check if the member holds a relevant role (QA or Dev). If the member is not in the database, auto-register the member with the assigned department keys.

        Args:
            member: The Discord member to check and, if eligible, register.
        """
        # TODO: this should be an overall watcher, not a dev-specific function
        if discord.Object(member.guild.id) in self._servers and not await database.staff.get_staff(discord_id=member.id):
            # TODO: put this thing inside register_staff
            author_roles: list[discord.Role] = member.roles
            department_keys: list[str] = []
            if self.tester_role in author_roles or self.head_of_tester_role in author_roles:
                department_keys.append("qa")
            if self.developer_role in author_roles:
                department_keys.append("dev")

            if not department_keys:
                log.debug(
                    "Member is not registered and has no matching department roles.",
                    extra={"id": member.id, "username": member.name},
                )
                return
            log.warning("Member is not registered.", extra={"id": member.id, "username": member.name})

            await database.staff.register_staff(member.id, member.name, department_keys)

    async def validate_new_bug_report(self, message: discord.Message) -> None:
        """Validate an incoming message before registering it as a bug report.

        Ensure the message was posted in a monitored bug reports channel. Ensure the message contains at least one media attachment (image or video). If both checks pass, call `register_report`.

        Args:
            message: The Discord message to validate.
        """
        if message.channel not in self.bug_report_channels:
            log.debug("message not in bugreports", extra={"channel": message.channel, "bugreportchannel": self.bug_report_channels})
            return
        if not any((att.content_type and (att.content_type.startswith("image/") or att.content_type.startswith("video/"))) for att in message.attachments):
            log.debug("message doesn't have media attached", extra={"attachments": message.attachments})
            return

        await self.register_report(message)

        log.info(
            "Bug Posted.",
            extra={
                "author": message.author.display_name,
                "channel": message.channel.name,
                "id": message.id,
                "content": message.content,
                "attachments": message.attachments,
            },
        )

    async def fix_report(self, payload: discord.RawReactionActionEvent) -> None:
        """Process a reaction on a bug report to approve or reject it.

        Validate that a staff member made the reaction in a designated channel. Auto-register the report or the decider if needed. Update the decision in the database. Log the outcome to the logging channel. Delete the original message.

        Args:
            payload: The raw reaction action payload from Discord.

        Raises:
            ValueError: The target reaction message cannot be retrieved from Discord.
        """
        if not discord.utils.get(self.bug_report_channels, id=payload.channel_id):
            log.debug("reaction is not made on a bug report channel.", extra={"channel": payload.channel_id})
            return
        if not payload.member:
            return
        if not any(role in payload.member.roles for role in [self.developer_role, self.head_of_tester_role]):
            log.debug("reaction not made by an admin.", extra={"user": payload.member, "roles": payload.member.roles})
            # we're sure that there's a message here, so we won't bother w/ checking, casts are just to make ty happy
            channel: discord.TextChannel = cast(discord.TextChannel, discord.utils.get(self.bug_report_channels, id=payload.channel_id))
            message: discord.Message = cast(discord.Message, await self.bot.cached_fetch_message(channel, payload.message_id))
            await message.remove_reaction(payload.emoji, payload.member)
            return
        if not await database.staff.get_staff(discord_id=payload.member.id):
            # this means author is somehow a staff. the question is what dept?
            log.warning("Member is not registered.", extra={"member": payload.member})
            await database.staff.register_staff(payload.member.id, payload.member.name, ["dev"])
        if (is_accepted := {"✅": 1, "❌": -1}.get(payload.emoji.name)) is None:
            log.debug("reaction is not a valid decision", extra={"user": payload.member, "reaction": payload.emoji})
            return
        if not await self.get_bug(message_id=payload.message_id):
            # BUG: apparently there's a scenario wherein an old bug cant be fixed bcz it's not registered
            channel: discord.TextChannel = cast(discord.TextChannel, await self.bot.cached_fetch_channel(payload.channel_id))  # verified to not be null
            message: discord.Message | None = await self.bot.cached_fetch_message(channel, payload.message_id)
            if not message:
                raise ValueError("Message cannot be found.")
            if not any(reaction.me for reaction in message.reactions):
                log.debug("message is not registered as a bug", extra={"message_object": payload.message_id})
                return
            else:
                log.debug("bug report is an old bug", extra={"message_object": message})
                await self.check_if_staff(message.author)
                await self.register_report(message)

        query = """
        UPDATE department_tester_reports
        SET decision=:decision, fixer=(SELECT s.staff_id FROM staff_staff s WHERE s.discord_id = :fixer_account_id), fixed_at=CURRENT_TIMESTAMP
        WHERE id=:bug_id
        """
        db = database.Database()
        await db.execute(query, {"decision": is_accepted, "fixer_account_id": payload.member.id, "bug_id": payload.message_id})
        self.bot.fire_and_forget(self.refresh_leaderboard())
        channel: discord.TextChannel = cast(discord.TextChannel, discord.utils.get(self.bug_report_channels, id=payload.channel_id))
        message: discord.Message = cast(discord.Message, await self.bot.cached_fetch_message(channel, payload.message_id))
        logembed = LogsEmbed(message, payload.member, is_accepted)
        await self.logging_channel.send(embed=logembed, files=logembed.files)
        await message.forward(self.logging_channel)
        await message.delete()  # TODO: wait for 3-5 seconds before deleting the bug report

        log.info(
            "Bug Decided.", extra={"author": message.author.display_name, "decider": payload.member.display_name, "id": message.id, "decision": is_accepted}
        )

    # Database Lookups
    def week_bounds(self, date: datetime | None = None, start_of_week: int | None = None) -> tuple[datetime, datetime]:
        """Get the start/end of a week based on a date. Defaults to today if no week is given."""
        date: datetime = date or datetime.now(tz=timezone.utc)
        start_of_week: int = start_of_week or self.start_of_week or 0
        dow: int = (date.weekday() + 1) % 7  # convert to 0=Sunday
        start: datetime = date - timedelta(days=(dow - start_of_week) % 7)
        start = datetime(start.year, start.month, start.day, tzinfo=date.tzinfo)
        end: datetime = start + timedelta(days=6, hours=23, minutes=59, seconds=59)
        log.debug("week bounds fetched", extra={"date": date, "start": start, "end": end})
        return start, end

    @overload
    async def get_bug(self, *, message_id: int) -> aiosqlite.Row | None: ...
    @overload
    async def get_bug(self, *, message: discord.Message) -> aiosqlite.Row | None: ...
    async def get_bug(self, *, message_id: int | None = None, message: discord.Message | None = None) -> aiosqlite.Row | None:
        """Get a registered bug report from the database by message or message ID.

        Args:
            message_id: The Discord message ID associated with the bug report.
            message: The Discord message object associated with the bug report.

        Returns:
            aiosqlite.Row | None: The database row representing the bug report, or `None` if not found.

        Raises:
            ValueError: If neither `message_id` nor `message` is provided.
        """
        if not ((message is None) ^ (message_id is None)):
            raise ValueError("Only provide 1 parameter.")

        message_id: int = message_id or message.id  # ty: ignore[unresolved-attribute], we're sure we have message.id at this point
        bug_lookup_query = "SELECT * FROM department_tester_reports r WHERE id = :id"
        db = database.Database()
        return await db.fetchone(bug_lookup_query, {"id": message_id})

    async def register_report(self, message: discord.Message) -> None:
        """Register a Discord message as a bug report in the database and add voting reactions.

        Args:
            message: The Discord message containing the new bug report.
        """
        bug_report_register_query = """
        INSERT INTO department_tester_reports (id, author, content, created_at)
        VALUES (:message_id, (SELECT staff_id FROM staff_staff WHERE discord_id = :author_id), :content, :created_at)
        """
        db = database.Database()
        await db.execute(
            bug_report_register_query,
            {
                "message_id": message.id,
                "author_id": message.author.id,
                "content": message.content,
                "created_at": message.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            },
        )

        await asyncio.gather(message.add_reaction("✅"), message.add_reaction("❌"), self.refresh_leaderboard())

    @overload
    async def get_tester_stats(self, *, week: tuple[datetime, datetime] | None = None) -> list[aiosqlite.Row]: ...
    @overload
    async def get_tester_stats(self, member: discord.Member | discord.User, *, week: tuple[datetime, datetime] | None = None) -> aiosqlite.Row | None: ...
    async def get_tester_stats(self, member: discord.Member | discord.User | None = None, *, week: tuple[datetime, datetime] | None = None):
        """Get tester statistics from the database.

        Args:
            member: The tester to look up. If omitted, returns stats for all active testers.
            week: A tuple of `(start_datetime, end_datetime)` to filter reports by creation date.
                If omitted, includes stats across all time.

        Returns:
            aiosqlite.Row | None: Statistics row for the specified member, or `None` if non-existent.
            list[aiosqlite.Row]: List of statistics rows for all active QA testers if `member` is `None`.
        """
        member_check: str = (
            "WHERE s.discord_id = :id AND d.department_key = 'qa' AND d.is_active = 1" if member else "WHERE d.department_key = 'qa' AND d.is_active = 1"
        )
        week_check: str = "AND datetime(r.created_at) BETWEEN datetime(:week_start) AND datetime(:week_end)" if week else ""
        id_column: str = "" if member else "s.discord_id AS discord_id, s.name AS name,"

        stat_lookup_query = f"""
        SELECT
            {id_column}
            COALESCE(SUM(CASE WHEN r.decision = 1 THEN 1 ELSE 0 END), 0) AS accepted,
            COALESCE(SUM(CASE WHEN r.decision = -1 THEN 1 ELSE 0 END), 0) AS rejected,
            COALESCE(SUM(CASE WHEN r.decision = 0 THEN 1 ELSE 0 END), 0) AS pending
        FROM staff_staff s
        JOIN staff_staff_department d
            ON d.staff_id = s.staff_id
        LEFT JOIN department_tester_reports r
            ON r.author = s.staff_id
            {week_check}
        {member_check}
        GROUP BY r.author;
        """

        params: dict[str, Any] = {}
        if member:
            params["id"] = member.id
        if week:
            params["week_start"], params["week_end"] = week[0].isoformat(), week[1].isoformat()
        db = database.Database()
        if member:
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
