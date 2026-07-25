import unittest
import database
import logging
from features import departmentHeads
import discord
import random
from unittest.mock import AsyncMock, MagicMock

log = logging.getLogger(f"test.{__name__}")


def make_mock_role(name="Admin", id=None, permissions=None):
    role = MagicMock(spec=discord.Role)
    role.id = id or random.randint(10**17, 10**18 - 1)
    role.name = name
    role.mention = f"<@&{id}>"
    role.permissions = permissions or discord.Permissions.none()
    return role


def make_mock_guild(name="TestGuild", id=None, member_count=1):
    guild = MagicMock(spec=discord.Guild)
    guild.id = id or random.randint(10**17, 10**18 - 1)
    guild.name = name
    guild.member_count = member_count
    guild.default_role = MagicMock(spec=discord.Role)
    guild.roles = [guild.default_role]
    guild.members = []
    guild.owner = None
    guild.get_role = MagicMock(
        side_effect=lambda rid: next((r for r in guild.roles if r.id == rid), None)
    )
    guild.get_member = MagicMock(
        side_effect=lambda mid: next((m for m in guild.members if m.id == mid), None)
    )
    guild.fetch_member = AsyncMock()
    guild.create_role = AsyncMock()
    guild.ban = AsyncMock()
    guild.kick = AsyncMock()
    return guild


def make_mock_member(
    name="TestUser", id=None, roles=None, guild=None, permissions=None
):
    guild = guild or make_mock_guild()
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
    guild.members.append(member)
    return member


class TestDatabase(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        # database setup
        self.db = database.Database()
        await self.db.connect(path=":memory:")

        self.devServer = make_mock_guild("Development Server")
        self.dev_developer_role = make_mock_role("Developer")
        self.dev_tester_sup_role = make_mock_role("Head of Testing")
        self.dev_tester_role = make_mock_role("Tester")
        self.devServer.roles.extend(
            [self.dev_developer_role, self.dev_tester_sup_role, self.dev_tester_role]
        )
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
        self.instructorServer.roles.extend(
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

    async def asyncTearDown(self):
        await self.db.close()

    async def test_core_queries(self):
        staffId = await departmentHeads.createBaseStaffFromAccount(
            "bonny", self.dev_tester_sup
        )
        staff = await database.staff.getStaffFromDiscordAccount(self.dev_tester_sup)
        self.assertEqual(staffId, staff["staff_id"])

        nonexistentStaff = await database.staff.getStaffFromDiscordAccount(
            self.inst_head_instructor
        )
        self.assertIsNone(nonexistentStaff)

    async def test_dept_heads_queries(self):
        staffId = await departmentHeads.createBaseStaffFromAccount(
            "bonny", self.dev_tester_sup
        )
        db = await self.db.fetchone("""
            SELECT s.staff_id, s.name, a.account_id, a.username, a.platform
            FROM staff_staff s
            JOIN staff_accounts a ON a.staff_id = s.staff_id
        """)
        log.debug(f"departmentHeads.createBaseStaffFromAccount : {dict(db)}")
        self.assertEqual(db["staff_id"], staffId)
        self.assertEqual(db["name"], "bonny")
        self.assertEqual(db["account_id"], self.dev_tester_sup.id)
        self.assertEqual(db["username"], self.dev_tester_sup.name)
        self.assertEqual(db["platform"], "discord")

        department = await departmentHeads.setDepartmentHead("qa", self.dev_tester_sup)
        self.assertEqual(
            department["head"],
            (await database.staff.getStaffFromDiscordAccount(self.dev_tester_sup))[
                "staff_id"
            ],
        )
        log.debug(f"departmentHeads.setDepartmentHead : {dict(department)}")
        with self.assertRaises(TypeError):
            await departmentHeads.setDepartmentHead(
                "inst", self.inst_head_instructor
            )  # not registered as staff

        testingHandles = await departmentHeads.getDepartmentHandles(self.dev_tester_sup)
        log.debug(f"departmentHeads.getDepartmentHandles : {dict(testingHandles)}")
        self.assertEqual(len(testingHandles), 1)
        nonexistentHandles = await departmentHeads.getDepartmentHandles(
            self.inst_head_instructor
        )
        log.debug(f"departmentHeads.getDepartmentHandles : {dict(nonexistentHandles)}")
        self.assertEqual(len(nonexistentHandles), 0)

        newStaffId = await departmentHeads.createBaseStaffFromAccount(
            "sleppn", self.dev_tester
        )
        await departmentHeads.registerStaffOnDepartment(
            newStaffId, testingHandles[0]["key"]
        )
        db = await self.db.fetchone(
            """
            SELECT d.staff_id, d.department_key FROM staff_staff_departments d
            JOIN staff_staff s ON d.staff_id = s.staff_id
            WHERE d.staff_id = ?
        """,
            (newStaffId,),
        )
        log.debug(f"departmentHeads.registerStaffOnDepartment : {dict(db)}")
        self.assertEqual(db["staff_id"], newStaffId)
        self.assertEqual(db["department_key"], "qa")
