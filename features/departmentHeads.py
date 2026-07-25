""" Development Cog - For use of the Development Department and Testing Team 
"""

import logging

import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

from database import Database


log = logging.getLogger(f"App.{__name__}")
load_dotenv()

async def createBaseStaffFromAccount(name, user):
    staffInsertQuery = """
        INSERT INTO
            staff_staff (name)
        VALUES
            (?) RETURNING staff_id;
    """
    accountInsertQuery = """
        INSERT INTO staff_accounts (account_id, username, platform, staff_id)
            VALUES (?, ?, 'discord', ?);
    """
    db = Database()
    staffId = (await db.fetchone(staffInsertQuery, (name,)))["staff_id"]
    await db.execute(accountInsertQuery, (user.id, user.name, staffId))
    return staffId
async def createDepartment(name, key, head):
    # head is expecting a discord user
    query = """
        INSERT INTO staff_department (name, key, head)
            VALUES (?, ?, ?);
    """
    

async def getDepartmentHandles(user):
    supervisorQuery = """
        WITH
            staff AS (
                SELECT
                    staff_staff.staff_id as id
                FROM
                    staff_accounts
                    LEFT JOIN staff_staff_accounts ON staff_staff_accounts.account_id = staff_accounts.account_id
                    LEFT JOIN staff_staff ON staff_staff.staff_id = staff_staff_accounts.staff_id
                WHERE
                    staff_accounts.account_id = ?
            )
        SELECT
            *
        FROM
            staff_department
            LEFT JOIN staff ON staff.id = staff_department.head
        WHERE staff_department.head = staff.id
    """
    db = Database()
    staffId = db.fetchall(supervisorQuery, (user.id,))
    return staffId

class DepartmentHeads(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        for guild in self.bot.servers:
            self.bot.tree.add_command(self.staff, guild=guild)

    staff = app_commands.Group(name="staff", description="Staff-Related Operations")

    @staff.command(name="register", description="Register a Staff")
    async def staffRegister(self, interaction, user: discord.User, preferredName: str):
        supervisor = interaction.user
        # TODO: check if the supervisor is really a supervisor

        


async def setup(bot):
    await bot.add_cog(DepartmentHeads(bot))