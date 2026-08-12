"""Leaderboard View."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Literal, cast

import discord

from main import MultipurposeBot

if TYPE_CHECKING:
    from sqlite3 import Row

    from features.development import Development

log: logging.Logger = logging.getLogger(f"App.{__name__}")


class BaseDevelopmentEmbed(discord.Embed):
    """Base Embed Template for Development - Bug Logger."""

    files: list[discord.File]

    def __init__(self, **kwargs: Any) -> None:  # noqa: ANN401
        super().__init__(timestamp=datetime.now(tz=timezone.utc), **kwargs)
        self.files: list[discord.File] = [discord.File("assets/development.png", filename="development.png")]
        self.set_footer(
            text="Multipurpose Bot - Development",
            icon_url="attachment://development.png",
        )


class SingleTesterStatEmbed(BaseDevelopmentEmbed):
    """Embed for seeing Leaderboard Stats of a Tester."""

    def __init__(self, devinstance: Development, member: discord.Member | discord.User, date: datetime | None = None) -> None:
        start, end = devinstance.week_bounds(date)
        self.devinstance: Development = devinstance
        super().__init__(title="Tester Statistics")
        if isinstance(member, discord.Member):
            avatar: str = member.guild_avatar.url if member.guild_avatar else member.avatar.url if member.avatar else member.default_avatar.url
        else:
            avatar: str = member.avatar.url if member.avatar else member.default_avatar.url
        self.set_author(name=member.display_name, icon_url=avatar)
        self._start: datetime = start
        self._end: datetime = end

    @classmethod
    async def create(cls, devinstance: Development, member: discord.Member | discord.User, date: datetime | None = None) -> SingleTesterStatEmbed:
        """Create an instane of the class, to get around the async problems."""
        self = cls(devinstance, member, date)
        await self.add_week_stats(member, (self._start, self._end))
        await self.add_overall_stats(member)
        return self

    async def add_week_stats(self, member: discord.Member | discord.User, week: tuple[datetime, datetime] | None) -> None:
        """Add a Week Stat Field to the Embed."""
        weekstats: Row | None = await self.devinstance.get_tester_stats(member, week=week)
        stats: dict[str, int] = {"Accepted Bugs": 0, "Rejected Bugs": 0, "Pending Bugs": 0}
        if weekstats:
            stats["Accepted Bugs"] = weekstats["accepted"]
            stats["Rejected Bugs"] = weekstats["rejected"]
            stats["Pending Bugs"] = weekstats["pending"]
        body: str = ""
        reports = 0
        for key, value in stats.items():
            body += f"**{key}**: {value}\n"
            reports += value
        body += f"**Quota**: {'✅' if reports >= self.devinstance.minimum_report_quota else '❌'}"
        self.add_field(name="Week Stats", value=body, inline=True)
        log.debug("week stats requested", extra={"stats": stats, "week-covered": week or self.devinstance.week_bounds()})

    async def add_overall_stats(self, member: discord.Member | discord.User) -> None:
        """Add a Overall Stat Field to the Embed."""
        weekstats: Row | None = await self.devinstance.get_tester_stats(member)
        stats: dict[str, int] = {"Accepted Bugs": 0, "Rejected Bugs": 0, "Pending Bugs": 0}
        if weekstats:
            stats["Accepted Bugs"] = weekstats["accepted"]
            stats["Rejected Bugs"] = weekstats["rejected"]
            stats["Pending Bugs"] = weekstats["pending"]
        body: str = ""
        reports = 0
        for key, value in stats.items():
            body += f"**{key}**: {value}\n"
            reports += value
        self.add_field(name="Overall Stats", value=body, inline=True)
        log.debug("Overall stats requested", extra={"stats": stats})


class TesterStatEmbed(BaseDevelopmentEmbed):
    """Embed for seeing Leaderboard Stats of all Testers."""

    __test__ = False  # pytest assumes this is a test. no it's not.

    def __init__(self, devinstance: Development, date: datetime | None = None) -> None:
        self.devinstance: Development = devinstance
        super().__init__(title="Testing Department Statistics")
        bot: MultipurposeBot = devinstance.bot
        if bot.user:
            avatar: str = bot.user.avatar.url if bot.user.avatar else bot.user.default_avatar.url
            self.set_author(name=bot.user.display_name, icon_url=avatar)

    @classmethod
    async def create(cls, devinstance: Development, date: datetime | None = None) -> TesterStatEmbed:
        """Create an instance of the class, to get around the async problems."""
        self = cls(devinstance, date)
        await self.add_tester_stats()
        return self

    async def add_tester_stats(self) -> None:
        """Add the Leaderboard Stat on the Embed."""
        _full_results: list[Row] = await self.devinstance.get_tester_stats()
        full_results: list[dict[str, int]] = [dict(tester) for tester in _full_results]

        _week_results: list[Row] = await self.devinstance.get_tester_stats(week=self.devinstance.week_bounds())
        week_results: list[dict[str, int | str]] = [dict(tester) for tester in _week_results]

        full_by_id: dict[int, dict[str, int]] = {row["discord_id"]: row for row in full_results}

        # sort weekly leaderboard by accepted count, descending
        week_results.sort(key=lambda r: r["accepted"], reverse=True)

        rows: list[tuple[str, str, str, str]] = []
        for row in week_results:
            full: dict[str, int] = full_by_id.get(row["discord_id"], {"accepted": 0, "rejected": 0, "pending": 0})
            name: str = cast(str, row["name"])
            accepted = f"{row['accepted']} ({full['accepted']})"
            rejected = f"{row['rejected']} ({full['rejected']})"
            pending = f"{row['pending']} ({full['pending']})"
            rows.append((name, accepted, rejected, pending))

        labels: list[str] = [f"✅ {i}. {name}" for i, (name, *_) in enumerate(rows, start=1)]

        name_width: int = max([len("      Name ")] + [len(label) for label in labels]) + 2
        accepted_width: int = max([len("Accepted")] + [len(a) for _, a, _, _ in rows])
        rejected_width: int = max([len("Rejected")] + [len(r) for _, _, r, _ in rows])

        header = f"{'      Name ':<{name_width}}{'Accepted':<{accepted_width + 2}}{'Rejected':<{rejected_width + 2}}{'Pending'}"
        labels: list[str] = []
        lines: list[str] = [header]
        for i, (name, accepted, rejected, pending) in enumerate(rows, start=1):
            full: dict[str, int] = full_by_id.get(row["discord_id"], {"accepted": 0, "rejected": 0, "pending": 0})
            # note: use rows[i-1]'s corresponding week_results entry for discord_id
            full = full_by_id.get(week_results[i - 1]["discord_id"], {"accepted": 0, "rejected": 0, "pending": 0})
            total: int = full["accepted"] + full["rejected"] + full["pending"]
            emoji: Literal["✅", "❌"] = "✅" if total >= self.devinstance.minimum_report_quota else "❌"
            label = f"{emoji} {i}. {name}"
            labels.append(label)
            lines.append(f"{label:<{name_width}}{accepted:<{accepted_width + 2}}{rejected:<{rejected_width + 2}}{pending}")

        table = "\n".join(f"`{line}`" for line in lines)

        self.add_field(name="Tester Fixes Leaderboard", value=table)


class LogsEmbed(BaseDevelopmentEmbed):
    """Embed for logging actions."""

    def __init__(self, message: discord.Message, decider: discord.Member, decision: int) -> None:
        super().__init__(
            title="Bug Fixed" if decision == 1 else "Bug Ignored",
            description=f"**From**: {message.author.mention}\n**Channel**: {message.channel.mention}\n**Content**: {message.content}",
            color=discord.Color(0x00FF00) if decision == 1 else discord.Color(0xFF0000),
        )

        if not decider:
            raise TypeError("Message must come from a guild.")

        avatar: str = decider.guild_avatar.url if decider.guild_avatar else decider.avatar.url if decider.avatar else decider.default_avatar.url
        self.set_author(name=decider.display_name, icon_url=avatar)
