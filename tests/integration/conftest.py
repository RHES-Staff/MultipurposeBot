"""Sets up Discord Testing and seeds Database."""

from __future__ import annotations

import json
import logging
import logging.config
from typing import TYPE_CHECKING, Any, cast
from unittest.mock import AsyncMock

import discord
import discord.ext.test as dpytest
import pytest
import pytest_asyncio
from discord.ext.test import backend

import database
import main
from features.development import Development

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from pytest_mock import MockerFixture


log: logging.Logger = logging.getLogger(f"App.{__name__}")


async def fake_fetch_member(self: discord.Guild, member_id: int) -> discord.Member | None:
    """Mock of discord.Guild.fetch_member() to return the cached version instead."""
    return self.get_member(member_id)


async def fake_fetch_roles(self: discord.Guild, role_id: int) -> discord.Role | None:
    """Mock of discord.Guild.fetch_member() to return the cached version instead."""
    return self.get_role(role_id)


def fake_content_type_getter(self: discord.Attachment) -> str | None:
    """Mock discord.Attachment.content_type."""
    ext: str = self.filename.rsplit(".", 1)[-1].lower()
    return {
        "png": "image/png",
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "mp4": "video/mp4",
        "mov": "video/quicktime",
    }.get(ext)


def fake_content_type_setter(self, value) -> None:  # noqa
    """Mocker that ignores content_type d.py assigns to a File."""


async def _teardown_bot(bot: main.MultipurposeBot, request: pytest.FixtureRequest) -> None:
    """Tear down a bot fixture after a test finishes.

    Removes all loaded cogs, closes the database, drains the dpytest message queue, and resets cog-level singletons.

    Args:
        bot: The bot instance to tear down.
        request: The pytest request object for the current test, used for
            outcome logging.
    """
    for cog_name in list(bot.cogs.keys()):
        await bot.remove_cog(cog_name)
    await database.Database().close()
    await dpytest.empty_queue()
    Development.instance = None
    result: Any | None = getattr(request.node, "rep_call", None)
    if result:
        log.info(
            "Test finished.",
            extra={
                "test": request.node.name,
                "outcome": result.outcome,  # 'passed', 'failed', 'skipped'
            },
        )


def fake_content_type_setter(self, value) -> None:  # noqa
    """Mocker that ignores content_type d.py assigns to a File."""


async def _teardown_bot(bot: main.MultipurposeBot, request: pytest.FixtureRequest) -> None:
    """Tear down a bot fixture after a test finishes.

    Removes all loaded cogs, closes the database, drains the dpytest message queue, and resets cog-level singletons.

    Args:
        bot: The bot instance to tear down.
        request: The pytest request object for the current test, used for
            outcome logging.
    """
    for cog_name in list(bot.cogs.keys()):
        await bot.remove_cog(cog_name)
    await database.Database().close()
    await dpytest.empty_queue()
    Development.instance = None
    result: Any | None = getattr(request.node, "rep_call", None)
    if result:
        log.info(
            "Test finished.",
            extra={
                "test": request.node.name,
                "outcome": result.outcome,  # 'passed', 'failed', 'skipped'
            },
        )


async def _set_department(db: database.Database, key: str, *, config: dict[str, Any], servers: list[int]) -> None:
    """Overwrite a department's configuration and server list.

    Args:
        db: The connected database instance to write to.
        key: The `staff_department.key` of the department to update.
        config: The configuration dict to store as JSON.
        servers: The list of Discord server IDs to associate with the department.
    """
    query = "UPDATE staff_department SET configuration = jsonb(:config), servers = jsonb(:servers) WHERE key = :key;"
    await db.execute(query, {"key": key, "config": json.dumps(config), "servers": json.dumps(servers)})


async def _seed_dev_guild(bot: main.MultipurposeBot, db: database.Database) -> dict[str, Any]:
    """Seed the Development-department guild, roles, members, and DB config.

    Builds the "Development Server" with its bug-report/leaderboard/logs channels, developer/head-tester/tester roles, and matching
    members, then writes the resulting configuration to the `dev` department.

    Args:
        bot: The bot instance to attach the seeded guild's bot member to.
        db: The connected database instance to write the department config to.

    Returns:
        dict[str, Any]: Seeded guild info (server, roles, users, channels, config, none_user).
    """
    devserver: discord.Guild = backend.make_guild(name="Development Server")
    devserver_channels: dict[str, discord.TextChannel] = {}
    for name in ("bug-reports", "leaderboards", "logs"):
        devserver_channels[name] = backend.make_text_channel(name, devserver)
    devserver_dev_role: discord.Role = backend.make_role("Developer", devserver)
    devserver_head_tester_role: discord.Role = backend.make_role("Head Tester", devserver)
    devserver_tester_role: discord.Role = backend.make_role("Tester", devserver)
    devserver_config: dict[str, int | list[int]] = {
        "testing_guild": devserver.id,
        "bug_report_channels": [devserver_channels["bug-reports"].id],
        "tester_role": devserver_tester_role.id,
        "head_of_tester_role": devserver_head_tester_role.id,
        "developer_role": devserver_dev_role.id,
        "minimum_report_quota": 6,
        "leaderboard_channel": devserver_channels["leaderboards"].id,
        "leaderboard_message": 0,
        "logging_channel": devserver_channels["logs"].id,
        "start_of_week": 0,
    }

    user_a: discord.User = backend.make_user("Yeleha", "0001")
    user_b: discord.User = backend.make_user("bonnyyyy", "0002")
    user_c: discord.User = backend.make_user("Yumiiii", "0003")
    user_d: discord.User = backend.make_user("Outsider", "0004")
    developer: discord.Member = backend.make_member(user_a, devserver, roles=[devserver_dev_role])
    head_tester: discord.Member = backend.make_member(user_b, devserver, roles=[devserver_head_tester_role, devserver_tester_role])
    tester: discord.Member = backend.make_member(user_c, devserver, roles=[devserver_tester_role])
    backend.make_member(cast(discord.User, bot.user), devserver)

    await _set_department(db, "dev", config=devserver_config, servers=[devserver.id])

    department = await db.fetchone("SELECT json(servers) as servers FROM staff_department WHERE key = 'dev';")
    assert department is not None, "Expected the 'dev' department row to exist after seeding."
    assert json.loads(department["servers"])[0] == devserver.id, "Expected the seeded devserver ID to be stored on the 'dev' department."

    return {
        "server": devserver,
        "roles": {"developer": devserver_dev_role, "head_tester": devserver_head_tester_role, "tester": devserver_tester_role},
        "users": {"developer": developer, "head_tester": head_tester, "tester": tester},
        "channels": devserver_channels,
        "config": devserver_config,
        "none_user": user_d,
    }


async def _seed_system_department(db: database.Database) -> dict[str, Any]:
    """Seed Systems-department configuration.

    Currently registers no guild or members, since the System cog's commands don't require them. Reserved for future scaffolding
    once Systems-cog tests need role/member context.

    Args:
        db: The connected database instance to write the department config to.

    Returns:
        dict[str, Any]: Seeded Systems department info (currently just the empty config).
    """
    sysserver: discord.Guild = backend.make_guild(name="Development Server")
    sysserver_evaluator_role: discord.Role = backend.make_role("Evaluator", sysserver)
    sysserver_trainee_role: discord.Role = backend.make_role("Trainee", sysserver)
    sys_config: dict[str, Any] = {"evaluator": sysserver_evaluator_role.id, "trainee": sysserver_trainee_role.id}
    await _set_department(db, "sys", config=sys_config, servers=[sysserver.id])
    return {"config": sys_config}


@pytest_asyncio.fixture
async def bot_test(mocker: MockerFixture, request: pytest.FixtureRequest, db_path: str) -> AsyncGenerator[dict[str, Any]]:
    """Set up a fully-seeded Bot instance for integration testing.

    Connects the database, applies the standard Discord API mocks, boots the bot's internal dpytest hook, seeds the Development
    and Systems department guilds/config, then loads cogs/departments in a single `setup_hook` call.

    Args:
        mocker: The pytest-mock fixture used to patch Discord API calls.
        request: The pytest request object for the current test.
        db_path: The database path to connect to.

    Yields:
        dict[str, Any]: Combined test context keyed by `"bot"`, `"dev"`, `"sys"`, and `"none"`.
    """
    log.info("Starting up a Test.", extra={"test": request.node.name})

    db = database.Database()
    await db.connect(db_path)

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

    dev_info: dict[str, Any] = await _seed_dev_guild(bot, db)
    sys_info: dict[str, Any] = await _seed_system_department(db)

    # single setup_hook call: loads bot.departments from the now fully-seeded DB, then loads/syncs cogs against it
    await bot.setup_hook()

    await bot.cached_fetch_guild(dev_info["server"].id)

    yield {
        "bot": bot,
        "dev": {
            "server": dev_info["server"],
            "roles": dev_info["roles"],
            "users": dev_info["users"],
            "channels": dev_info["channels"],
            "config": dev_info["config"],
        },
        "none": {"users": {"none1": dev_info["none_user"]}},
        "sys": sys_info,
    }

    await _teardown_bot(bot, request)