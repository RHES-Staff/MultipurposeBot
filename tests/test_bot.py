"""Testing bot functionalities."""

import asyncio
import logging
from typing import Any, cast

import aiosqlite
import discord
import discord.ext.test as dpytest
import pytest_mock

import database
from features.development import Development, get_tester_stats
from main import MultipurposeBot

from .conftest import wait_for_reaction

log = logging.getLogger(f"App.Test.{__name__}")


async def test_init(bot_test: tuple[MultipurposeBot, dict[str, Any], pytest_mock.MockerFixture]) -> None:
    """Test Proper Initialization of Bot, and its Helper Functions."""
    # test helper functions
    bot, guild_info, mocker = bot_test
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


async def test_development(bot_test: tuple[MultipurposeBot, dict[str, Any], pytest_mock.MockerFixture]) -> None:
    """Test Development Feature."""
    # Test init
    bot, guild_info, mocker = bot_test
    dev: Development | None = cast(Development, bot.get_cog("Development"))
    db = database.Database()
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

    # Test bot listening
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

    async def check_tester_points(accepted: int, rejected: int, pending: int):
        stats = await get_tester_stats(guild_info["dev"]["users"]["tester"])
        assert stats
        assert stats["accepted"] == accepted, "Recorded Accepted bugs are not what is expected."
        assert stats["rejected"] == rejected, "Recorded Rejected bugs are not what is expected."
        assert stats["pending"] == pending, "Recorded Pending bugs are not what is expected."
        return stats

    nomedia_bugreport: discord.Message = await dpytest.message(
        "Nomedia Bug Report", guild_info["dev"]["channels"]["bug-reports"], guild_info["dev"]["users"]["tester"]
    )
    await asyncio.sleep(0.1)
    assert len(nomedia_bugreport.reactions) == 0, "Bot reacted on a Bug Report w/o media"

    invalidmedia_bugreport: discord.Message = await dpytest.message(
        "Invalid Media Bug Report", guild_info["dev"]["channels"]["bug-reports"], guild_info["dev"]["users"]["tester"], attachments=["tests/media/file.txt"]
    )
    await asyncio.sleep(0.1)
    assert len(invalidmedia_bugreport.reactions) == 0, "Bot reacted on a Bug Report w/ Invalid media"

    wrong_channel_bugreport: discord.Message = await dpytest.message(
        "Wrong Channel Bug Report", guild_info["dev"]["channels"]["leaderboards"], guild_info["dev"]["users"]["tester"], attachments=["tests/media/photo.png"]
    )
    await asyncio.sleep(0.1)
    assert len(wrong_channel_bugreport.reactions) == 0, "Bot reacted on a Bug Report on the wrong channel"

    photo_bugreport: discord.Message = await dpytest.message(
        "Photo Bug Report", guild_info["dev"]["channels"]["bug-reports"], guild_info["dev"]["users"]["tester"], attachments=["tests/media/photo.png"]
    )
    photobug_result = await sanity_check_bugreport(photo_bugreport)
    await check_tester_points(0, 0, 1)
    assert photobug_result["decision"] == 0, "Bug report should not yet be decided"

    video_bugreport: discord.Message = await dpytest.message(
        "Video Bug Report", guild_info["dev"]["channels"]["bug-reports"], guild_info["dev"]["users"]["tester"], attachments=["tests/media/video.mp4"]
    )
    videobug_result = await sanity_check_bugreport(video_bugreport)
    await check_tester_points(0, 0, 2)
    assert videobug_result["decision"] == 0, "Bug report should not yet be decided"

    mixed_bugreport: discord.Message = await dpytest.message(
        "Mixed Media Bug Report",
        guild_info["dev"]["channels"]["bug-reports"],
        guild_info["dev"]["users"]["tester"],
        attachments=["tests/media/photo.png", "tests/media/video.mp4", "tests/media/file.txt"],
    )
    mixedbug_result = await sanity_check_bugreport(mixed_bugreport)
    await check_tester_points(0, 0, 3)
    assert mixedbug_result["decision"] == 0, "Bug report should not yet be decided"

    nonadmin_reaction = await dpytest.add_reaction(guild_info["dev"]["users"]["tester"], photo_bugreport, "✅")
    # await check_tester_points(0, 0, 3)
    print(nonadmin_reaction)
    await asyncio.sleep(0.1)
    admin_reaction = await dpytest.add_reaction(guild_info["inst"]["users"]["inst_requests"], photo_bugreport, "✅")
    # await check_tester_points(1, 0, 2)
    print(admin_reaction)
    await asyncio.sleep(0.1)