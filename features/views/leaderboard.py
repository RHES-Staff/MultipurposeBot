"""Leaderboard View."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from sqlite3 import Row
from typing import TYPE_CHECKING, Any

import discord

if TYPE_CHECKING:
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

    def __init__(self, devinstance: Development, member: discord.Member | discord.User, date: datetime | None = None) -> None:
        self.devinstance: Development = devinstance
        super().__init__(title="Testing Department Statistics")
        self.set_author(name="Bug Logger")
