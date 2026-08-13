"""Testing Global Database Calls."""

import asyncio
import sqlite3
from typing import TYPE_CHECKING, Any

import discord
import pytest
import pytest_mock

import database.department
import database.staff
from database.core import Database
from database.models import StaffMember
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
        staff_id: int = await database.staff.register_staff(member.id, member.name, ["qa"])

        row: Row | None = await db.fetchone("SELECT * FROM staff_staff WHERE staff_id = :id;", {"id": staff_id})
        assert row
        assert row["discord_id"] == member.id
        assert row["name"] == member.name

    async def test_register_staff_duplicate_raises(self, bot_test: tuple[MultipurposeBot, dict[str, Any], pytest_mock.MockerFixture]) -> None:
        """Check if register_staff can handle duplicates."""
        _, ctx, _ = bot_test
        member: discord.Member = ctx["dev"]["users"]["tester"]

        insert1: int = await database.staff.register_staff(member.id, member.name, ["qa"])
        insert2: int = await database.staff.register_staff(member.id, member.name, ["qa"])
        assert insert1 == insert2


class TestGetStaffByDiscordUser:
    """Tests the Fetching Logic of Database."""

    async def test_found(self, bot_test: tuple[MultipurposeBot, dict[str, Any], pytest_mock.MockerFixture]) -> None:
        """Check if get_staff_by_discord_user can properly handle finding staffs."""
        _, ctx, _ = bot_test
        member: discord.Member = ctx["dev"]["users"]["tester"]
        await database.staff.register_staff(member.id, member.name, ["qa"])

        result: Row | None = await database.staff.get_staff(discord_id=member.id)
        assert result
        assert result["discord_id"] == member.id

    async def test_not_found(self, bot_test: tuple[MultipurposeBot, dict[str, Any], pytest_mock.MockerFixture]) -> None:
        """Check if has_staff_admin_perms can properly recognize staff."""
        _, ctx, _ = bot_test
        outsider: discord.Member = ctx["none"]["users"]["none1"]

        result: Row | None = await database.staff.get_staff(discord_id=outsider.id)
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

        assert await database.staff.has_staff_admin_perms(discord_id=user_dept_head.id) is True
        assert await database.staff.has_staff_admin_perms(discord_id=user_sys_active.id) is True
        assert await database.staff.has_staff_admin_perms(discord_id=user_sys_inactive.id) is False
        assert await database.staff.has_staff_admin_perms(discord_id=user_no_record.id) is False


class TestResignStaff:
    async def test_resign_staff_by_staff_id(self, bot_test):
        db = Database()
        await db.execute("INSERT INTO staff_staff (staff_id, name, discord_id) VALUES (1, 'test', 111);")
        await db.execute("INSERT INTO staff_staff_department (staff_id, department_key) VALUES (1, 'qa');")

        await database.staff.resign_staff(staff_id=1)

        staff: Row | None = await db.fetchone("SELECT is_active FROM staff_staff WHERE staff_id = 1;")
        dept: Row | None = await db.fetchone("SELECT is_active FROM staff_staff_department WHERE staff_id = 1;")
        assert staff and staff["is_active"] == 0
        assert dept and dept["is_active"] == 0

    async def test_resign_staff_by_discord_id(self, bot_test):
        db = Database()
        await db.execute("INSERT INTO staff_staff (staff_id, name, discord_id) VALUES (2, 'test2', 222);")

        await database.staff.resign_staff(discord_id=222)

        staff: Row | None = await db.fetchone("SELECT is_active FROM staff_staff WHERE staff_id = 2;")
        assert staff and staff["is_active"] == 0

    async def test_resign_staff_not_found_raises(self, bot_test):
        with pytest.raises(ValueError):
            await database.staff.resign_staff(staff_id=9999)


class TestResignStaffDepartment:
    async def test_resign_staff_department_by_staff_id(self, bot_test):
        db = Database()
        await db.execute("INSERT INTO staff_staff (staff_id, name, discord_id) VALUES (3, 'test3', 333);")
        await db.execute("INSERT INTO staff_staff_department (staff_id, department_key) VALUES (3, 'qa'), (3, 'dev');")

        await database.department.resign_staff_department(staff_id=3, department_key="qa")

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

        await database.department.resign_staff_department(discord_id=444, department_key="ad")

        dept: Row | None = await db.fetchone("SELECT is_active FROM staff_staff_department WHERE staff_id = 4 AND department_key = 'ad';")
        assert dept and dept["is_active"] == 0

    async def test_resign_staff_department_not_member_raises(self, bot_test):
        db = Database()
        await db.execute("INSERT INTO staff_staff (staff_id, name, discord_id) VALUES (5, 'test5', 555);")

        with pytest.raises(ValueError):
            await database.department.resign_staff_department(staff_id=5, department_key="qa")

    async def test_resign_staff_department_staff_not_found_raises(self, bot_test):
        with pytest.raises(ValueError):
            await database.department.resign_staff_department(staff_id=9999, department_key="qa")


class TestUpdateStaffProfile:
    """Tests for database.staff.update_staff_profile."""

    async def test_update_by_staff_id(self, db: Database) -> None:
        """Updates fields when looked up by staff_id."""
        row = await database.staff.update_staff_profile(name="Bob", staff_id=1)
        assert row["staff_id"] == 1
        assert row["name"] == "Bob"

    async def test_update_by_discord_id(self, db: database.Database) -> None:
        """Updates fields when looked up by discord_id."""
        row = await database.staff.update_staff_profile(title="Lead", discord_id=111)
        assert row["title"] == "Lead"

    async def test_update_multiple_fields(self, db: database.Database) -> None:
        """Updates several fields at once and returns them all."""
        row = await database.staff.update_staff_profile(name="Bob", title="Lead", timezone="UTC", staff_id=1)
        assert row["name"] == "Bob"
        assert row["title"] == "Lead"
        assert row["timezone"] == "UTC"

    async def test_no_fields_raises(self, db: database.Database) -> None:
        """Raises when no updatable field is given."""
        with pytest.raises(ValueError):
            await database.staff.update_staff_profile(staff_id=1)

    async def test_unknown_staff_id_raises(self, db: database.Database) -> None:
        """Raises when no matching staff member exists."""
        with pytest.raises(ValueError):
            await database.staff.update_staff_profile(name="Bob", staff_id=9999)


class TestUpdateStaffDiscordAcct:
    """Tests for database.staff.update_staff_discord_acct."""

    async def test_update_by_staff_id(self, db) -> None:
        """Updates discord_id when looked up by staff_id."""
        row = await database.staff.update_staff_discord_acct(222, staff_id=1)
        assert (row["staff_id"], row["old_discord_id"], row["new_discord_id"]) == (1, 111, 222)
        check = await db.fetchone("SELECT discord_id FROM staff_staff WHERE staff_id = :id;", {"id": 1})
        assert check["discord_id"] == 222

    async def test_update_by_old_discord_id(self, db) -> None:
        """Updates discord_id when looked up by old_discord_id."""
        row = await database.staff.update_staff_discord_acct(333, old_discord_id=111)
        assert (row["staff_id"], row["old_discord_id"], row["new_discord_id"]) == (1, 111, 333)

    async def test_staff_id_not_found_raises(self, db) -> None:
        """Raises ValueError if staff_id doesn't exist."""
        with pytest.raises(ValueError):
            await database.staff.update_staff_discord_acct(222, staff_id=999)

    async def test_old_discord_id_not_found_raises(self, db) -> None:
        """Raises ValueError if old_discord_id doesn't exist."""
        with pytest.raises(ValueError):
            await database.staff.update_staff_discord_acct(222, old_discord_id=999)

    async def test_duplicate_new_discord_id_raises(self, db) -> None:
        """Raises IntegrityError if new_discord_id is already taken."""
        await database.staff.register_staff(discord_id=444, name="Bob", department_keys=["dev"])
        with pytest.raises(sqlite3.IntegrityError):
            await database.staff.update_staff_discord_acct(444, staff_id=1)


class TestBlacklistStaff:
    """Tests for database.staff.blacklist_staff."""

    async def test_raises_if_active(self, db) -> None:
        """Should raise ValueError if staff member is still active."""
        with pytest.raises(ValueError):
            await database.staff.blacklist_staff(discord_id=111)

    async def test_returns_none_if_not_found(self, db) -> None:
        """Should return None if no matching staff member exists."""
        result = await database.staff.blacklist_staff(staff_id=9999)
        assert result is None

    async def test_blacklists_inactive_staff_by_discord_id(self, db) -> None:
        """Should blacklist and return row when staff is inactive."""
        await database.staff.resign_staff(discord_id=111)

        result = await database.staff.blacklist_staff(discord_id=111)

        assert result is not None
        assert result["discord_id"] == 111
        assert result["name"] == "Alice"

        row = await db.fetchone("SELECT is_blacklisted FROM staff_staff WHERE discord_id = 111;")
        assert row["is_blacklisted"] == 1

    async def test_blacklists_inactive_staff_by_staff_id(self, db) -> None:
        """Should blacklist and return row when looked up by staff_id."""
        staff: Row | None = await database.staff.get_staff(discord_id=111)
        assert staff
        await database.staff.resign_staff(staff_id=staff["staff_id"])

        result: Row | None = await database.staff.blacklist_staff(staff_id=staff["staff_id"])

        assert result is not None
        assert result["staff_id"] == staff["staff_id"]
