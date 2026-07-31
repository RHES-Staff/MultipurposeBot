"""Testing bot functionalities."""

import asyncio
import logging
from collections import Counter
from typing import Any, cast

import aiosqlite
import discord
import discord.ext.test as dpytest
import pytest_mock

import database
from features.development import Development, get_developer_stats, get_tester_stats
from main import MultipurposeBot

from .conftest import wait_for_reaction

log = logging.getLogger(f"App.Test.{__name__}")


async def test_init(bot_test: tuple[MultipurposeBot, dict[str, Any], pytest_mock.MockerFixture]) -> None:
    """Test Proper Initialization of Bot, and its Helper Functions."""
    # test helper functions
    bot, guild_info, _ = bot_test
    assert not await bot.cached_fetch_guild(12345), "Nonexistent guild lookup returned something."
    devserver = await bot.cached_fetch_guild(guild_info["dev"]["server"].id)
    assert devserver, "Valid guild lookup did not return something"
    assert devserver == guild_info["dev"]["server"], "Guild lookup returned something else."

    assert not await bot.cached_fetch_member(devserver, 12345), "Nonexistent member lookup returned something."
    member = await bot.cached_fetch_member(devserver, guild_info["dev"]["users"]["developer"].id)
    assert member, "Valid member lookup did not return something."
    assert member == guild_info["dev"]["users"]["developer"], "Member lookup returned something else."

    assert not await bot.cached_fetch_user(12345), "Nonexistent user lookup returned something."
    user = await bot.cached_fetch_user(guild_info["dev"]["users"]["developer"].id)
    assert user, "Valid user lookup did not return something."
    assert user.id == guild_info["dev"]["users"]["developer"].id, "User lookup returned something else."

    assert not await bot.cached_fetch_channel(12345), "Nonexistent channel lookup returned something."
    channel = await bot.cached_fetch_channel(guild_info["dev"]["channels"]["logs"].id)
    assert channel, "Valid channel lookup did not return something"
    assert channel == guild_info["dev"]["channels"]["logs"], "Channel lookup returned something else"
    assert isinstance(channel, discord.TextChannel), "Channel returned a different Channel Type"

    msg: discord.Message = await dpytest.message("test", channel, guild_info["dev"]["users"]["tester"])
    fetched: discord.Message | None = await bot.cached_fetch_message(channel, msg.id)
    assert fetched, "Valid message lookup did not return something"
    assert msg == fetched, "Message lookup returned something"

    assert bot.departments, "bot.departments did not get populated."

    # Cog Testing
    dev: Development | None = cast(Development, bot.get_cog("Development"))
    assert dev, "Development bot is not loaded."

    config = guild_info["dev"]["config"]
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


async def test_development(bot_test: tuple[MultipurposeBot, dict[str, Any], pytest_mock.MockerFixture]) -> None:
    """Test Development Feature."""
    bot, guild_info, _ = bot_test
    tester: discord.Member = guild_info["dev"]["users"]["tester"]
    head_tester: discord.Member = guild_info["dev"]["users"]["head_tester"]
    developer: discord.Member = guild_info["dev"]["users"]["developer"]

    bug_reports: discord.TextChannel = guild_info["dev"]["channels"]["bug-reports"]
    leaderboard: discord.TextChannel = guild_info["dev"]["channels"]["leaderboards"]
    _logs: discord.TextChannel = guild_info["dev"]["channels"]["logs"]

    photo: str = "tests/media/photo.png"
    video: str = "tests/media/video.mp4"
    file: str = "tests/media/file.txt"
    db = database.Database()

    async def sanity_check_bugreport(bugreport: discord.Message) -> aiosqlite.Row:
        """Check for all Bug Reports for standard inputs."""
        await wait_for_reaction(bugreport, "✅", timeout=0.3)
        await wait_for_reaction(bugreport, "❌", timeout=0.3)
        assert len(bugreport.reactions) == 2, "Bot did not react on a Bug Report w/o media"
        dblookup = await db.fetchone(
            "SELECT s.discord_id, r.content, r.decision FROM department_tester_reports r LEFT JOIN staff_staff s ON s.staff_id = r.author WHERE id=:id",
            {"id": bugreport.id},
        )
        assert dblookup, "Did not register the bug in the database."
        assert dblookup["discord_id"] == bugreport.author.id, "Staff that reported the bug is different than what's registered."
        assert dblookup["content"] == bugreport.content, "Bug Report Message is different than what's registered."
        return dblookup

    async def check_tester_points(member: discord.Member, accepted: int, rejected: int, pending: int) -> aiosqlite.Row:
        """Assert points of a tester against an expected value."""
        stats = await get_tester_stats(member)
        assert stats, "No Tester Stats found."
        assert stats["accepted"] == accepted, "Recorded Accepted bugs are not what is expected."
        assert stats["rejected"] == rejected, "Recorded Rejected bugs are not what is expected."
        assert stats["pending"] == pending, "Recorded Pending bugs are not what is expected."
        return stats

    async def check_developer_points(member: discord.Member, accepted: int, rejected: int) -> aiosqlite.Row:
        """Assert points of a developer against an expected value."""
        stats = await get_developer_stats(member)
        assert stats, "No Developer Stats found."
        assert stats["accepted"] == accepted, "Recorded Accepted bugs are not what is expected."
        assert stats["rejected"] == rejected, "Recorded Rejected bugs are not what is expected."
        return stats

    def supposed_reactions(message: discord.Message, check: int = 1, x: int = 1) -> bool:
        """Get Reactions of a message and compare its check and x counts against an expected value."""
        reactions: Counter[str] = Counter([str(reaction.emoji) for reaction in message.reactions for _ in range(reaction.count)])
        return reactions["✅"] == check and reactions["❌"] == x

    nomedia_bugreport: discord.Message = await dpytest.message("Nomedia Bug Report", bug_reports, tester)
    assert supposed_reactions(nomedia_bugreport, 0, 0), "Bot reacted on an invalid report"

    invalidmedia_bugreport: discord.Message = await dpytest.message("Invalid Media Bug Report", bug_reports, tester, attachments=[file])
    assert supposed_reactions(invalidmedia_bugreport, 0, 0), "Bot reacted on an invalid report"

    wrong_channel_bugreport: discord.Message = await dpytest.message("Wrong Channel Bug Report", leaderboard, tester, attachments=[photo])
    assert supposed_reactions(wrong_channel_bugreport, 0, 0), "Bot reacted on an invalid report"

    photo_bugreport: discord.Message = await dpytest.message("Photo Bug Report", bug_reports, tester, attachments=[photo])
    await check_tester_points(tester, 0, 0, 1)
    assert supposed_reactions(photo_bugreport, 1, 1), "Bot did not react on a valid report"

    video_bugreport: discord.Message = await dpytest.message("Video Bug Report", bug_reports, head_tester, attachments=[video])
    await check_tester_points(head_tester, 0, 0, 1)
    assert supposed_reactions(video_bugreport, 1, 1), "Bot did not react on a valid report"

    mixed_bugreport: discord.Message = await dpytest.message("Mixed Media Bug Report", bug_reports, tester, attachments=[photo, video, file])
    await check_tester_points(tester, 0, 0, 2)
    assert supposed_reactions(mixed_bugreport, 1, 1), "Bot did not react properly"

    # decide report
    await dpytest.add_reaction(tester, photo_bugreport, "✅")
    await asyncio.sleep(0.1)
    assert await bot.cached_fetch_message(bug_reports, photo_bugreport.id), "Bug Report is deleted."
    assert supposed_reactions(photo_bugreport, 1, 1), "Bot did not remove reaction"
    await check_tester_points(tester, 0, 0, 2)

    await dpytest.add_reaction(developer, photo_bugreport, "🖕")
    await asyncio.sleep(0.1)
    assert await bot.cached_fetch_message(bug_reports, photo_bugreport.id), "Bug Report is deleted."
    assert supposed_reactions(photo_bugreport, 1, 1), "Bot did not react properly"
    await check_tester_points(tester, 0, 0, 2)

    await dpytest.add_reaction(developer, photo_bugreport, "✅")
    await asyncio.sleep(0.1)
    assert not await bot.cached_fetch_message(bug_reports, photo_bugreport.id), "Bug Report is not deleted."
    await check_developer_points(developer, 1, 0)
    await check_tester_points(tester, 1, 0, 1)

    await dpytest.add_reaction(head_tester, video_bugreport, "❌")
    await asyncio.sleep(0.1)
    assert not await bot.cached_fetch_message(bug_reports, video_bugreport.id), "Bug Report is not deleted."
    await check_developer_points(head_tester, 0, 1)
    await check_tester_points(head_tester, 0, 1, 0)

    await dpytest.add_reaction(developer, nomedia_bugreport, "❌")
    await asyncio.sleep(0.1)
    assert await bot.cached_fetch_message(bug_reports, nomedia_bugreport.id), "Bug Report is deleted."
    await check_developer_points(developer, 1, 0)
    await check_tester_points(tester, 1, 0, 1)
