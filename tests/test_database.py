"""Unit Testing for the App."""

import logging
import random
import unittest
from unittest.mock import AsyncMock, MagicMock

import discord

import database

log = logging.getLogger(f"test.{__name__}")


def make_mock_role(name: str, id: int | None = None, permissions: discord.Permissions | None = None) -> discord.Role:
    """Create a Mock Discord Role."""
    role: discord.Role = MagicMock(spec=discord.Role)
    role.id = id or random.randint(10**17, 10**18 - 1)
    role.name = name
    role.mention = f"<@&{id}>"
    role.permissions = permissions or discord.Permissions.none()
    return role


def make_mock_guild(name: str, id: int | None = None, member_count: int = 1) -> discord.Guild:
    """Create a Mock Discord Guild."""
    guild = MagicMock(spec=discord.Guild)
    guild.id = id or random.randint(10**17, 10**18 - 1)
    guild.name = name
    guild.member_count = member_count
    guild.default_role = MagicMock(spec=discord.Role)
    guild.roles = [guild.default_role]
    guild.members = []
    guild.owner = None
    guild.get_role = MagicMock(side_effect=lambda rid: next((r for r in guild.roles if r.id == rid), None))
    guild.get_member = MagicMock(side_effect=lambda mid: next((m for m in guild.members if m.id == mid), None))
    guild.fetch_member = AsyncMock()
    guild.create_role = AsyncMock()
    guild.ban = AsyncMock()
    guild.kick = AsyncMock()
    return guild


def make_mock_member(
    name: str, guild: discord.Guild, id: int | None = None, roles: list[discord.Role] | None = None, permissions: discord.Permissions | None = None
) -> discord.Member:
    """Create a Mock Discord Server."""
    member = MagicMock(spec=discord.Member)
    member.id = id or random.randint(10**17, 10**18 - 1)
    member.name = name
    member.display_name = name
    member.mention = f"<@{id}>"
    member.bot = False
    member.guild = guild
    member.roles = roles or [guild.default_role]
    member.guild_permissions = permissions or discord.Permissions.none()
    member.send = AsyncMock()
    member.kick = AsyncMock()
    member.ban = AsyncMock()
    member.edit = AsyncMock()
    member.add_roles = AsyncMock()
    member.remove_roles = AsyncMock()
    guild.members.append(member)  # ty: ignore[unresolved-attribute], this is just a mock
    return member


class TestDatabase(unittest.IsolatedAsyncioTestCase):
    """Test every functions that involves a Database."""

    async def asyncSetUp(self) -> None:
        """Set up the Database, and the mock Servers and Relationships."""
        # database setup
        self.db = database.Database()
        await self.db.connect(path=":memory:")

        self.devServer = make_mock_guild("Development Server")
        self.dev_developer_role = make_mock_role("Developer")
        self.dev_tester_sup_role = make_mock_role("Head of Testing")
        self.dev_tester_role = make_mock_role("Tester")
        self.devServer.roles.extend([self.dev_developer_role, self.dev_tester_sup_role, self.dev_tester_role])  # ty: ignore[unresolved-attribute], this is just a mock
        self.dev_developer = make_mock_member(
            name="isaac",
            guild=self.devServer,
            roles=[self.devServer.default_role, self.dev_developer_role],
        )
        self.dev_tester_sup = make_mock_member(
            name="bonnybonnybon",
            guild=self.devServer,
            roles=[
                self.devServer.default_role,
                self.dev_tester_sup_role,
                self.dev_tester_role,
            ],
        )
        self.dev_tester = make_mock_member(
            name="sleppn",
            guild=self.devServer,
            roles=[self.devServer.default_role, self.dev_tester_role],
        )

        self.instructorServer = make_mock_guild("Instruction Server")
        self.inst_head_instructor_role = make_mock_role("Head Instructor")
        self.inst_instructor_requests_role = make_mock_role("Instruction Requests")
        self.inst_instructor_role = make_mock_role("Instructor")
        self.instructorServer.roles.extend( # ty: ignore[unresolved-attribute], this is just a mock
            [
                self.inst_head_instructor_role,
                self.inst_instructor_requests_role,
                self.inst_instructor_role,
            ]
        )
        self.inst_head_instructor = make_mock_member(
            name="visadow",
            guild=self.instructorServer,
            roles=[self.instructorServer.default_role, self.inst_head_instructor_role],
        )
        self.inst_instructor_requests = make_mock_member(
            name="yumiii",
            guild=self.instructorServer,
            roles=[
                self.instructorServer.default_role,
                self.inst_instructor_requests_role,
            ],
        )
        self.inst_instructor = make_mock_member(
            name="foxy",
            guild=self.instructorServer,
            roles=[self.instructorServer.default_role, self.inst_instructor_role],
        )

        log.debug("mock servers wired")

    async def asyncTearDown(self) -> None:
        """Close the Database."""
        await self.db.close()
