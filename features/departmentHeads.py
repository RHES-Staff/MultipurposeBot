"""Development Cog - For use of the Development Department and Testing Team"""

import logging

import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

from database import Database, staff

log = logging.getLogger(f"App.{__name__}")
load_dotenv()


async def createBaseStaffFromAccount(name, user):
    staffInsertQuery = """
        INSERT INTO staff_staff (name)
            VALUES (?)
        RETURNING staff_id;
    """
    accountInsertQuery = """
        INSERT INTO staff_accounts (account_id, username, platform, staff_id)
            VALUES (?, ?, 'discord', ?);
    """
    db = Database()
    staffId = (await db.fetchone(staffInsertQuery, (name,)))["staff_id"]
    await db.execute(accountInsertQuery, (user.id, user.name, staffId))
    return staffId


async def registerStaffOnDepartment(staffId, key):
    departmentInsertQuery = """
        INSERT INTO staff_staff_departments (staff_id, department_key)
            VALUES (?, ?)
    """
    db = Database()
    await db.execute(departmentInsertQuery, (staffId, key))


async def setDepartmentHead(key, head):
    # head is expecting a discord user
    query = """
        UPDATE staff_department
        SET head = ? WHERE key = ?
        RETURNING *;
    """
    db = Database()
    return await db.fetchone(
        query, ((await staff.getStaffFromDiscordAccount(head))["staff_id"], key)
    )
    # TODO: throw an exception if head is not a member of their org


async def getDepartmentHandles(user):
    supervisorQuery = """
        SELECT
            dept.key, dept.name
        FROM
            staff_department dept
            LEFT JOIN staff_accounts acct ON acct.staff_id = dept.head
        WHERE acct.account_id = ?
    """
    db = Database()
    return await db.fetchall(supervisorQuery, (user.id,))


class DepartmentHeads(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        for guild in self.bot.servers:
            self.bot.tree.add_command(self.staff, guild=guild)

    staff = app_commands.Group(name="staff", description="Staff-Related Operations")

    @staff.command(name="register", description="Register a Staff")
    async def staffRegister(self, interaction, user: discord.User, preferredName: str):
        supervisorDepts = getDepartmentHandles(interaction.user)
        # TODO: if none, throw an error, if > 2, ask user what department
        newStaffId = await createBaseStaffFromAccount(preferredName, user)
        await registerStaffOnDepartment(newStaffId, supervisorDepts[0]["key"])


async def setup(bot):
    await bot.add_cog(DepartmentHeads(bot))
