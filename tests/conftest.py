"""Unit/Integration Testing of Bot."""

import asyncio
import json
import logging
from collections.abc import AsyncGenerator
from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock

import discord
import discord.ext.test as dpytest
import pytest_asyncio
from discord.ext.test import backend
from pytest_mock import MockerFixture

import database
import main
from features.development import Development

log = logging.getLogger(f"App.  Test.{__name__}")
with open("logging.json", "r", encoding="utf-8") as f:
    config = f.read()

db_path = ":memory:"


async def fake_fetch_member(self: discord.Guild, member_id: int) -> discord.Member | None:
    """Mock of discord.Guild.fetch_member() to return the cached version instead."""
    return self.get_member(member_id)


async def fake_fetch_roles(self: discord.Guild, role_id: int) -> discord.Role | None:
    """Mock of discord.Guild.fetch_member() to return the cached version instead."""
    return self.get_role(role_id)


def fake_content_type_getter(self: discord.Attachment) -> str | None:
    """Mock discord.Attachment.content_type."""
    ext = self.filename.rsplit(".", 1)[-1].lower()
    return {
        "png": "image/png",
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "mp4": "video/mp4",
        "mov": "video/quicktime",
    }.get(ext)


def fake_content_type_setter(self, value):
    pass  # ignore whatever discord.py/dpytest tries to assign

async def wait_for_reaction(message, emoji, timeout=5.0):
    async def _poll():
        while not any(r.emoji == emoji for r in message.reactions):
            await asyncio.sleep(0.1)

    await asyncio.wait_for(_poll(), timeout=timeout)

@pytest_asyncio.fixture
async def bot_test(mocker: MockerFixture) -> AsyncGenerator:
    """Set up Bot for Testing."""
    mock_file = mocker.mock_open(read_data=config).return_value
    mock_file.read = AsyncMock(return_value=config)

    mock_open_cm = MagicMock()
    mock_open_cm.__aenter__ = AsyncMock(return_value=mock_file)
    mock_open_cm.__aexit__ = AsyncMock(return_value=None)
    mocker.patch("aiofiles.open", return_value=mock_open_cm)
    bot = main.MultipurposeBot()
    mocker.patch.object(bot.tree, "sync", new_callable=AsyncMock)
    bot.fetch_user = AsyncMock(side_effect=lambda uid: bot.get_user(uid))
    bot.fetch_guild = AsyncMock(side_effect=lambda uid: bot.get_guild(uid))
    mocker.patch.object(bot, "fetch_channel", side_effect=lambda uid: bot.get_channel(uid))
    mocker.patch.object(discord.Guild, "fetch_member", fake_fetch_member)
    mocker.patch.object(discord.Guild, "fetch_role", fake_fetch_roles)
    mocker.patch.object(discord.abc.Messageable, "fetch_message", AsyncMock(side_effect=lambda uid: discord.utils.get(bot.cached_messages, id=uid)))
    mocker.patch.object(discord.Attachment, "content_type", property(fake_content_type_getter, fake_content_type_setter))
    await bot._async_setup_hook()
    dpytest.configure(bot, guilds=0)

    devserver = backend.make_guild(name="Development Server")
    devserver_channels = {}
    for name in ("bug-reports", "leaderboards", "logs"):
        devserver_channels[name] = backend.make_text_channel(name, devserver)
    devserver_dev_role = backend.make_role("Developer", devserver)
    devserver_head_tester_role = backend.make_role("Head Tester", devserver)
    devserver_tester_role = backend.make_role("Tester", devserver)
    devserver_config: dict[str, int | list[int]] = {
        "testing_guild": devserver.id,
        "bug_report_channels": [devserver_channels["bug-reports"].id],
        "admin_role_ids": [devserver_dev_role.id, devserver_head_tester_role.id],
        "minimum_report_quota": 6,
        "leaderboard_channel": devserver_channels["leaderboards"].id,
        "leaderboard_message": 0,
        "logging_channel": devserver_channels["logs"].id,
        "start_of_week": 0,
    }

    instserver = backend.make_guild(name="Instructor Server")
    instserver_instructor_requests_channel = backend.make_text_channel("instructor-requests", instserver)
    instserver_requests_role = backend.make_role("Instructor Requests", instserver)
    instserver_instructor_role = backend.make_role("Instructor", instserver)
    instserver_config: dict[str, Any] = {}

    user_a = backend.make_user("Yeleha", "0001")
    user_b = backend.make_user("bonnyyyy", "0003")
    user_c = backend.make_user("Yumiiii", "0002")
    developer = backend.make_member(user_a, devserver, roles=[devserver_dev_role])
    head_tester = backend.make_member(user_b, devserver, roles=[devserver_head_tester_role, devserver_tester_role])
    tester = backend.make_member(user_c, devserver, roles=[devserver_tester_role])
    inst_requests = backend.make_member(user_c, instserver, roles=[instserver_requests_role])
    instructor = backend.make_member(user_a, instserver, roles=[instserver_instructor_role])
    backend.make_member(cast(discord.User, bot.user), devserver)
    backend.make_member(cast(discord.User, bot.user), instserver)

    db = database.Database()
    await db.connect(db_path)

    query = "UPDATE staff_department SET configuration = :config, servers = :servers WHERE key = :key;"
    await db.execute(query, {"key": "dev", "config": json.dumps(devserver_config), "servers": f"[{devserver.id}]"})
    await db.execute(query, {"key": "inst", "config": json.dumps(instserver_config), "servers": f"[{instserver.id}]"})
    await bot.setup_hook(db_path=db_path)

    new_department = await db.fetchall("SELECT * FROM staff_department;")
    for department in new_department:
        if department["key"] == "dev":
            assert json.loads(department["servers"])[0] == devserver.id
        if department["key"] == "inst":
            assert json.loads(department["servers"])[0] == instserver.id
    await bot.cached_fetch_guild(12345)
    yield (
        bot,
        {
            "dev": {
                "server": devserver,
                "roles": {"developer": devserver_dev_role, "head_tester": devserver_head_tester_role, "tester": devserver_tester_role},
                "users": {"developer": developer, "head_tester": head_tester, "tester": tester},
                "channels": devserver_channels,
                "config": devserver_config,
            },
            "inst": {
                "server": instserver,
                "roles": {"inst_requests": instserver_requests_role, "instructor": instserver_instructor_role},
                "users": {"inst_requests": inst_requests, "instructor": instructor},
                "channels": {"instructor_requests": instserver_instructor_requests_channel},
            },
        },
        mocker,
    )
    await database.Database().close()
    await dpytest.empty_queue()
    Development.instance = None
