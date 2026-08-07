"""Testing bot functionalities."""

from __future__ import annotations
from dataclasses import dataclass

import asyncio
import logging
from collections import Counter
from typing import TYPE_CHECKING, Any, ClassVar, cast

import discord
import discord.ext.test as dpytest
import pytest
import pytest_mock

import database
from features.development import Development
from main import MultipurposeBot

if TYPE_CHECKING:
    from sqlite3 import Row

    from _pytest.mark.structures import ParameterSet
    from discord.abc import GuildChannel, PrivateChannel
    from discord.guild import Guild
    from discord.member import Member
    from discord.threads import Thread
    from discord.user import User


log: logging.Logger = logging.getLogger(f"App.Test.{__name__}")


async def test_helpers(bot_test: tuple[MultipurposeBot, dict[str, Any], pytest_mock.MockerFixture]) -> None:
    """Test Proper Initialization of Bot, and its Helper Functions."""
    # test helper functions
    bot, guild_info, _ = bot_test
    assert not await bot.cached_fetch_guild(12345), "Nonexistent guild lookup returned something."
    devserver: Guild | None = await bot.cached_fetch_guild(guild_info["dev"]["server"].id)
    assert devserver, "Valid guild lookup did not return something"
    assert devserver == guild_info["dev"]["server"], "Guild lookup returned something else."

    assert not await bot.cached_fetch_member(devserver, 12345), "Nonexistent member lookup returned something."
    member: Member | None = await bot.cached_fetch_member(devserver, guild_info["dev"]["users"]["developer"].id)
    assert member, "Valid member lookup did not return something."
    assert member == guild_info["dev"]["users"]["developer"], "Member lookup returned something else."

    assert not await bot.cached_fetch_user(12345), "Nonexistent user lookup returned something."
    user: User | None = await bot.cached_fetch_user(guild_info["dev"]["users"]["developer"].id)
    assert user, "Valid user lookup did not return something."
    assert user.id == guild_info["dev"]["users"]["developer"].id, "User lookup returned something else."

    assert not await bot.cached_fetch_channel(12345), "Nonexistent channel lookup returned something."
    channel: GuildChannel | PrivateChannel | Thread | None = await bot.cached_fetch_channel(guild_info["dev"]["channels"]["logs"].id)
    assert channel, "Valid channel lookup did not return something"
    assert channel == guild_info["dev"]["channels"]["logs"], "Channel lookup returned something else"
    assert isinstance(channel, discord.TextChannel), "Channel returned a different Channel Type"

    assert bot.departments, "bot.departments did not get populated."


async def test_development_init(bot_test: tuple[MultipurposeBot, dict[str, Any], pytest_mock.MockerFixture]) -> None:
    """Test Development Cog and its Initialization."""
    bot, guild_info, _ = bot_test
    dev: Development | None = cast(Development, bot.get_cog("Development"))
    assert dev, "Development bot is not loaded."

    config: dict[str, Any] = guild_info["dev"]["config"]
    assert dev.testing_guild.id == config["testing_guild"], "Testing Guild did not get configured properly"
    assert [c.id for c in dev.bug_report_channels] == config["bug_report_channels"], "Bug Report Channels did not get configured properly"
    assert [r.id for r in dev.admin_role_ids] == config["admin_role_ids"], "Admin Role IDs did not get configured properly"
    assert dev.minimum_report_quota == config["minimum_report_quota"], "Minimum Report Quota did not get configured properly"
    assert dev.leaderboard_channel.id == config["leaderboard_channel"], "Leaderboard Channel did not get configured properly"
    assert dev.leaderboard_message.content == "Leaderboard", (
        "Leaderboard Message did send properly"
    )  # WARN: this can fail once the leaderbaord message got replaced w/ something real
    assert dev.logging_channel.id == config["logging_channel"], "Logging Channel did not get configured properly"
    assert dev.start_of_week == config["start_of_week"], "Start of Week did not get configured properly"


# ---------------------------------------------------------------------------
# shared helpers
# ---------------------------------------------------------------------------


def supposed_reactions(message: discord.Message, check: int = 1, x: int = 1) -> bool:
    """Compare a message's ✅/❌ reaction counts against expected values."""
    reactions: Counter[str] = Counter(str(r.emoji) for r in message.reactions for _ in range(r.count))
    return reactions["✅"] == check and reactions["❌"] == x


async def sanity_check_bugreport(db: database.Database, bugreport: discord.Message) -> Row:
    """Check a report's expected behavior."""
    await asyncio.sleep(0.1)
    assert len(bugreport.reactions) == 2, "Bot did not react on a Bug Report w/o media"
    row: Row | None = await db.fetchone(
        "SELECT s.discord_id, r.content, r.decision FROM department_tester_reports r LEFT JOIN staff_staff s ON s.staff_id = r.author WHERE id=:id",
        {"id": bugreport.id},
    )
    assert row, "Did not register the bug in the database."
    assert row["discord_id"] == bugreport.author.id, "Reporting staff mismatch."
    assert row["content"] == bugreport.content, "Bug Report content mismatch."
    return row


async def check_tester_points(devinstance: Development, member: discord.Member, accepted: int, rejected: int, pending: int) -> Row:
    """Check a tester's stored points against what is stored in the database."""
    assert devinstance
    stats: Row | None = await devinstance.get_tester_stats(member)
    assert stats, "No Tester Stats found."
    assert stats["accepted"] == accepted, "Recorded Accepted bugs are not what is expected."
    assert stats["rejected"] == rejected, "Recorded Rejected bugs are not what is expected."
    assert stats["pending"] == pending, "Recorded Pending bugs are not what is expected."
    return stats


async def check_developer_points(devinstance: Development, member: discord.Member, accepted: int, rejected: int) -> Row:
    """Check a developers's stored points against what is stored in the database."""
    stats: Row | None = await devinstance.get_developer_stats(member)
    assert stats, "No Developer Stats found."
    assert stats["accepted"] == accepted, "Recorded Accepted bugs are not what is expected."
    assert stats["rejected"] == rejected, "Recorded Rejected bugs are not what is expected."
    return stats

@dataclass
class BugReport:
    """A Report Case."""
    content: str
    channel_key: str
    author_key: str
    attachments: list[str]
    valid: bool

@dataclass
class RegisteredReport:
    """A Report Case."""
    bot: MultipurposeBot
    dev: Development
    message: discord.Message
    author: discord.Member
    guild_info: dict[str, Any]
    case: BugReport

@dataclass
class DecidedReport:
    """A Report Case."""
    should_decide: bool
    still_present: discord.Message | None
    decider: discord.Member
    author: discord.Member
    devinstance: Development
    emoji: str
    case: BugReport

class TestBugReportBehavior:
    """Test for the expected Behavior of Development Cog when a bug report is posted."""

    PHOTO = "tests/media/photo.png"
    VIDEO = "tests/media/video.mp4"
    FILE = "tests/media/file.txt"

    @pytest.fixture
    async def dev_ctx(self, bot_test: tuple[MultipurposeBot, dict[str, Any], Any]) -> tuple[MultipurposeBot, Development, dict[str, Any]]:
        """Setup Bug Report Behavior Testing."""
        bot, guild_info, _ = bot_test
        devinstance: Development | None = cast(Development | None, bot.get_cog("Development"))
        assert devinstance, "Development Cog did not load."
        return bot, devinstance, guild_info

    REGISTER_CASES: ClassVar[list[ParameterSet]] = [
        pytest.param(("Nomedia Bug Report", "bug-reports", "tester", [], False), id="no-media"),
        pytest.param(("Invalid Media Bug Report", "bug-reports", "tester", [FILE], False), id="invalid-media-type"),
        pytest.param(("Wrong Channel Bug Report", "leaderboards", "tester", [PHOTO], False), id="wrong-channel"),
        pytest.param(("Photo Bug Report", "bug-reports", "tester", [PHOTO], True), id="photo"),
        pytest.param(("Video Bug Report", "bug-reports", "head_tester", [VIDEO], True), id="video"),
        pytest.param(("Mixed Media Bug Report", "bug-reports", "tester", [PHOTO, VIDEO, FILE], True), id="mixed-media"),
    ]

    @pytest.fixture(params=REGISTER_CASES)
    async def registered_report(
        self, dev_ctx: tuple[MultipurposeBot, Development, dict[str, Any]], request: pytest.FixtureRequest
    ) -> tuple[MultipurposeBot, Development, discord.Message, pytest.FixtureRequest, discord.Member, dict[str, Any]]:
        """Stage 1: post a bug report."""
        content, channel_key, author_key, attachments, _ = cast(tuple[str, str, str, list[str], bool], request.param)
        bot, devinstance, guild_info = dev_ctx

        channel: discord.TextChannel = guild_info["dev"]["channels"][channel_key]
        author: discord.Member = guild_info["dev"]["users"][author_key]

        message: discord.Message = await dpytest.message(content, channel, author, attachments=attachments)

        return bot, devinstance, message, request, author, guild_info

    async def test_register_reports(
        self,
        registered_report: tuple[MultipurposeBot, Development, discord.Message, pytest.FixtureRequest, discord.Member, dict[str, Any]],
    ) -> None:
        """Fixture performs and asserts the register_reports pass/fail behavior."""
        _, devinstance, message, request, author, _ = registered_report
        _, _, _, _, valid = cast(tuple[str, str, str, list[str], bool], request.param)
        db = database.Database()

        if valid:
            assert supposed_reactions(message, 1, 1), "Bot did not react on a valid report"
            await sanity_check_bugreport(db, message)
            await check_tester_points(devinstance, author, accepted=0, rejected=0, pending=1)
        else:
            assert supposed_reactions(message, 0, 0), "Bot reacted on an invalid report"
        assert message is not None

    DECIDER_ROLES_WITH_PERMISSION: ClassVar[set[str]] = {"head_tester", "developer"}

    DECIDE_CASES: ClassVar[list[ParameterSet]] = [
        pytest.param(("tester", "✅"), id="tester-noperms-accept"),
        pytest.param(("tester", "❌"), id="tester-noperms-reject"),
        pytest.param(("tester", "❓"), id="tester-noperms-invalid"),
        pytest.param(("developer", "✅"), id="developer-accept"),
        pytest.param(("developer", "❌"), id="developer-reject"),
        pytest.param(("developer", "❓"), id="developer-invalid"),
        pytest.param(("head_tester", "✅"), id="headtester-accept"),
        pytest.param(("head_tester", "❌"), id="headtester-reject"),
        pytest.param(("head_tester", "❓"), id="headtester-invalid"),
    ]

    @pytest.fixture(params=DECIDE_CASES)
    async def decided_report(
        self,
        registered_report: tuple[MultipurposeBot, Development, discord.Message, pytest.FixtureRequest, discord.Member, dict[str, Any]],
        request: pytest.FixtureRequest,
    ) -> tuple[Any, ...]:
        """Stage 2: react on whatever register_reports produced, assert decide_reports behavior."""
        bot, devinstance, message, registered_request, author, guild_info = registered_report
        _, _, _, _, valid = cast(tuple[str, str, str, list[str], bool], registered_request.param)
        decider_key, emoji = cast(tuple[str, str], request.param)

        channel: discord.Message = message.channel

        decider: discord.Member = guild_info["dev"]["users"][decider_key]

        has_permission: bool = decider_key in self.DECIDER_ROLES_WITH_PERMISSION
        valid_emoji: bool = emoji in ("✅", "❌")
        should_decide: bool = valid and has_permission and valid_emoji

        await dpytest.add_reaction(decider, message, emoji)
        await asyncio.sleep(0.1)

        still_present: discord.Message | None = await bot.cached_fetch_message(channel, message.id)


        return should_decide, still_present

    async def test_decide_reports(self, decided_report: tuple[bool, discord.Message]) -> None:
        """Fixture performs and asserts the decide_reports pass/fail behavior."""
        should_decide, still_present = decided_report
        if should_decide:
            assert not still_present, "Bug Report was not deleted after a valid decision."
            if emoji == "✅":
                await check_developer_points(devinstance, decider, 1, 0)
                await check_tester_points(devinstance, author, 1, 0, 0)
            else:
                await check_developer_points(devinstance, decider, 0, 1)
                await check_tester_points(devinstance, author, 0, 1, 0)
        else:
            assert still_present, "Bug Report was deleted despite an invalid decision."
            expected_pending: int = 1 if valid else 0
            await check_tester_points(devinstance, author, 0, 0, expected_pending)
        assert decided_report["message"] is not None
