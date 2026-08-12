"""Testing Global Database Calls."""

from typing import TYPE_CHECKING, Any

import discord
import pytest
import pytest_mock

from database.core import Database
from database.staff import get_staff, has_staff_admin_perms, register_staff, resign_staff, resign_staff_department
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
        staff_id: int = await register_staff(member.id, member.name, ["qa"])

        row: Row | None = await db.fetchone("SELECT * FROM staff_staff WHERE staff_id = :id;", {"id": staff_id})
        assert row
        assert row["discord_id"] == member.id
        assert row["name"] == member.name

    async def test_register_staff_duplicate_raises(self, bot_test: tuple[MultipurposeBot, dict[str, Any], pytest_mock.MockerFixture]) -> None:
        """Check if register_staff can handle duplicates."""
        _, ctx, _ = bot_test
        member: discord.Member = ctx["dev"]["users"]["tester"]

        insert1: int = await register_staff(member.id, member.name, ["qa"])
        insert2: int = await register_staff(member.id, member.name, ["qa"])
        assert insert1 == insert2


class TestGetStaffByDiscordUser:
    """Tests the Fetching Logic of Database."""

    async def test_found(self, bot_test: tuple[MultipurposeBot, dict[str, Any], pytest_mock.MockerFixture]) -> None:
        """Check if get_staff_by_discord_user can properly handle finding staffs."""
        _, ctx, _ = bot_test
        member: discord.Member = ctx["dev"]["users"]["tester"]
        await register_staff(member.id, member.name, ["qa"])

        result: Row | None = await get_staff(discord_id=member.id)
        assert result
        assert result["discord_id"] == member.id

    async def test_not_found(self, bot_test: tuple[MultipurposeBot, dict[str, Any], pytest_mock.MockerFixture]) -> None:
        """Check if has_staff_admin_perms can properly recognize staff."""
        _, ctx, _ = bot_test
        outsider: discord.Member = ctx["none"]["users"]["none1"]

        result: Row | None = await get_staff(discord_id=outsider.id)
        assert result is None

    async def test_has_staff_admin_perms(self, bot_test: tuple[MultipurposeBot, dict[str, Any], pytest_mock.MockerFixture]) -> None:
        """Tests the perms that a staff can have. Admins should be Dept. Heads + Systems Department."""
        _, servers, _ = bot_test
        db = Database()
        user_dept_head: discord.Member = servers["dev"]["users"]["developer"]  # any discord.Member/User
        user_sys_active: discord.Member = servers["dev"]["users"]["tester"]
        user_sys_inactive: discord.Member = servers["dev"]["users"]["head_tester"]
        user_no_record: discord.Member = servers["none"]["users"]["none1"]

        # staff rows
        await db.execute(
            "INSERT INTO staff_staff (staff_id, name, discord_id) VALUES (:id,:name,:did)",
            {"id": 1, "name": "head", "did": user_dept_head.id},
        )
        await db.execute(
            "INSERT INTO staff_staff (staff_id, name, discord_id) VALUES (:id,:name,:did)",
            {"id": 2, "name": "sys_active", "did": user_sys_active.id},
        )
        await db.execute(
            "INSERT INTO staff_staff (staff_id, name, discord_id) VALUES (:id,:name,:did)",
            {"id": 3, "name": "sys_inactive", "did": user_sys_inactive.id},
        )

        # dept head via existing 'dev' department
        await db.execute("UPDATE staff_department SET head = 1 WHERE key = 'dev'")

        # sys dept membership
        await db.execute("INSERT INTO staff_staff_department (staff_id, department_key, is_active) VALUES (2, 'sys', 1)")
        await db.execute("INSERT INTO staff_staff_department (staff_id, department_key, is_active) VALUES (3, 'sys', 0)")

        assert await has_staff_admin_perms(discord_id=user_dept_head.id) is True
        assert await has_staff_admin_perms(discord_id=user_sys_active.id) is True
        assert await has_staff_admin_perms(discord_id=user_sys_inactive.id) is False
        assert await has_staff_admin_perms(discord_id=user_no_record.id) is False


class TestResignStaff:
    async def test_resign_staff_by_staff_id(self, bot_test):
        db = Database()
        await db.execute("INSERT INTO staff_staff (staff_id, name, discord_id) VALUES (1, 'test', 111);")
        await db.execute("INSERT INTO staff_staff_department (staff_id, department_key) VALUES (1, 'qa');")

        await resign_staff(staff_id=1)

        staff: Row | None = await db.fetchone("SELECT is_active FROM staff_staff WHERE staff_id = 1;")
        dept: Row | None = await db.fetchone("SELECT is_active FROM staff_staff_department WHERE staff_id = 1;")
        assert staff and staff["is_active"] == 0
        assert dept and dept["is_active"] == 0

    async def test_resign_staff_by_discord_id(self, bot_test):
        db = Database()
        await db.execute("INSERT INTO staff_staff (staff_id, name, discord_id) VALUES (2, 'test2', 222);")

        await resign_staff(discord_id=222)

        staff: Row | None = await db.fetchone("SELECT is_active FROM staff_staff WHERE staff_id = 2;")
        assert staff and staff["is_active"] == 0

    async def test_resign_staff_not_found_raises(self, bot_test):
        with pytest.raises(ValueError):
            await resign_staff(staff_id=9999)


class TestResignStaffDepartment:
    async def test_resign_staff_department_by_staff_id(self, bot_test):
        db = Database()
        await db.execute("INSERT INTO staff_staff (staff_id, name, discord_id) VALUES (3, 'test3', 333);")
        await db.execute("INSERT INTO staff_staff_department (staff_id, department_key) VALUES (3, 'qa'), (3, 'dev');")

        await resign_staff_department(staff_id=3, department_key="qa")

        qa: Row | None = await db.fetchone("SELECT is_active FROM staff_staff_department WHERE staff_id = 3 AND department_key = 'qa';")
        dev: Row | None = await db.fetchone("SELECT is_active FROM staff_staff_department WHERE staff_id = 3 AND department_key = 'dev';")
        staff: Row | None = await db.fetchone("SELECT is_active FROM staff_staff WHERE staff_id = 3;")
        assert qa and qa["is_active"] == 0
        assert dev and dev["is_active"] == 1
        assert staff and staff["is_active"] == 1  # unaffected

    async def test_resign_staff_department_by_discord_id(self, bot_test):
        db = Database()
        await db.execute("INSERT INTO staff_staff (staff_id, name, discord_id) VALUES (4, 'test4', 444);")
        await db.execute("INSERT INTO staff_staff_department (staff_id, department_key) VALUES (4, 'ad');")

        await resign_staff_department(discord_id=444, department_key="ad")

        dept: Row | None = await db.fetchone("SELECT is_active FROM staff_staff_department WHERE staff_id = 4 AND department_key = 'ad';")
        assert dept and dept["is_active"] == 0

    async def test_resign_staff_department_not_member_raises(self, bot_test):
        db = Database()
        await db.execute("INSERT INTO staff_staff (staff_id, name, discord_id) VALUES (5, 'test5', 555);")

        with pytest.raises(ValueError):
            await resign_staff_department(staff_id=5, department_key="qa")

    async def test_resign_staff_department_staff_not_found_raises(self, bot_test):
        with pytest.raises(ValueError):
            await resign_staff_department(staff_id=9999, department_key="qa")
