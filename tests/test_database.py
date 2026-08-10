"""Testing Global Database Calls."""

from typing import TYPE_CHECKING, Any

import discord
import pytest_mock

from database.core import Database
from database.staff import get_staff_by_discord_user, register_staff
from main import MultipurposeBot

if TYPE_CHECKING:
    from sqlite3 import Row


class TestRegisterStaff:
    """Tests the Registering Logic of Database."""

    async def test_register_staff_inserts_row(self, bot_test: tuple[MultipurposeBot, dict[str, Any], pytest_mock.MockerFixture]) -> None:
        """Check if register_staff is properly registering users."""
        _, ctx, _ = bot_test
        member: discord.Member = ctx["dev"]["users"]["tester"]
        db = Database()
        staff_id: int = await register_staff(member, ["qa"])

        row: Row | None = await db.fetchone("SELECT * FROM staff_staff WHERE staff_id = :id;", {"id": staff_id})
        assert row
        assert row["discord_id"] == member.id
        assert row["name"] == member.name

    async def test_register_staff_duplicate_raises(self, bot_test: tuple[MultipurposeBot, dict[str, Any], pytest_mock.MockerFixture]) -> None:
        """Check if register_staff can handle duplicates."""
        _, ctx, _ = bot_test
        member: discord.Member = ctx["dev"]["users"]["tester"]

        insert1: int = await register_staff(member, ["qa"])
        insert2: int = await register_staff(member, ["qa"])
        assert insert1 == insert2


class TestGetStaffByDiscordUser:
    """Tests the Fetching Logic of Database."""

    async def test_found(self, bot_test: tuple[MultipurposeBot, dict[str, Any], pytest_mock.MockerFixture]) -> None:
        """Check if get_staff_by_discord_user can properly handle finding staffs."""
        _, ctx, _ = bot_test
        member: discord.Member = ctx["dev"]["users"]["tester"]
        await register_staff(member, ["qa"])

        result: Row | None = await get_staff_by_discord_user(member)
        assert result
        assert result["discord_id"] == member.id

    async def test_not_found(self, bot_test: tuple[MultipurposeBot, dict[str, Any], pytest_mock.MockerFixture]) -> None:
        """Check if get_staff_by_discord_user can properly handle unregistered staffs."""
        _, ctx, _ = bot_test
        outsider: discord.Member = ctx["none"]["users"]["none1"]

        result: Row | None = await get_staff_by_discord_user(outsider)
        assert result is None
