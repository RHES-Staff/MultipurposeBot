"""Systems Cog - For use of the Systems Department."""

from __future__ import annotations

import logging
import re
import time
from collections.abc import Iterable
from typing import TYPE_CHECKING, Any, Self

import discord
from aiosqlite import Row
from discord import app_commands
from discord.ext import commands
from discord.guild import Guild
from discord.role import Role
from dotenv import load_dotenv

import database
from database.core import Database
from database.department import set_department_config, set_department_server
from database.models import Department, StaffMember
from database.staff import has_staff_admin_perms
from features.views.feedback import FeedbackEmbed, FeedbackModal

if TYPE_CHECKING:
    from main import MultipurposeBot

log = logging.getLogger(f"App.{__name__}")
load_dotenv()


class System(commands.Cog):
    """Systems Cog: Commands are for administration of the whole system."""

    instance: Self | None = None

    def __init__(self, bot: MultipurposeBot) -> None:
        System.instance = self
        self.bot = bot

    async def cog_load(self):
        sysdept: Department | None = await database.department.get_department("sys")
        assert sysdept, "Systems Department is not found."
        guild_ids: list[int] = sysdept.servers
        config: dict[str, Any] = sysdept.configuration

        guild: Guild | None = await self.bot.cached_fetch_guild(guild_id=guild_ids[0])
        if not guild:
            raise ValueError("Guild from Database not found.")

        trainee: Role | None = guild.get_role(config["trainee"])
        if trainee is None:
            raise ValueError("Role from Database not found.")
        self.trainee: Role = trainee

        evaluator: Role | None = guild.get_role(config["evaluator"])
        if evaluator is None:
            raise ValueError("Role from Database not found.")
        self.evaluator: Role = evaluator

    @app_commands.command(name="say", description="Say something as the Bot")
    @app_commands.guilds()
    async def say(self, interaction: discord.Interaction, message: str) -> None:
        """Say something as the bot."""
        await interaction.response.send_message("Sent message.")
        await interaction.followup.send(message)

    @app_commands.command(name="ping", description="Pong!")
    async def ping(self, interaction: discord.Interaction) -> None:
        """Test Bot Connectivity, Will give Roundtrip Statistics."""
        start: int | float = time.monotonic()
        await interaction.response.send_message("Pinging...", ephemeral=True)
        end: int | float = time.monotonic()
        roundtrip: int | float = (end - start) * 1000

        await interaction.edit_original_response(content=f"Pong!\n\nRoundtrip: `{roundtrip:.2f}ms`\nWebsocket: `{interaction.client.latency * 1000:.2f}ms`")

    configure = app_commands.Group(name="configure", description="Configure ")

    @configure.command(name="server", description="Configure the Servers to register")
    @app_commands.choices(operation=[app_commands.Choice(name="Add", value=1), app_commands.Choice(name="Remove", value=0)])
    async def config_server(self, interaction: discord.Interaction, department: str, server_id: int, operation: app_commands.Choice[int]) -> None:
        """Adds/Removes servers of a Department. Running on a server will add all of the departments command on the said server."""
        # TODO: logging
        if not await has_staff_admin_perms(discord_id=interaction.user.id):
            await interaction.response.send_message("You are not permitted.", ephemeral=True)
            return

        await set_department_server(department, server_id, add=bool(operation.value))

        await interaction.response.send_message(f"Updated. {'Added' if operation.value else 'Removed'} {server_id} to {department}")

    _KEY_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,64}$")

    @configure.command(name="department", description="Configure the Department Settings")
    async def config_department(self, interaction: discord.Interaction, department: str, key: str, value: str) -> None:
        """Sets a key/value pair in the Department's configuration."""
        if not await has_staff_admin_perms(discord_id=interaction.user.id):
            await interaction.response.send_message("You are not permitted.", ephemeral=True)
            return

        if not self._KEY_PATTERN.fullmatch(key):
            await interaction.response.send_message("Invalid key: only letters, numbers, `_` and `-` are allowed.", ephemeral=True)
            return

        if not await set_department_config(department, key, value):
            await interaction.response.send_message("Department not found.", ephemeral=True)
            return

        await interaction.response.send_message(f"Set `{key}` = `{value}` in `{department}` configuration.", ephemeral=True)

    @app_commands.command(name="reload", description="Reload command Guilds globally.")
    @app_commands.allowed_contexts(guilds=False, dms=True, private_channels=False)
    async def reload(self, interaction: discord.Interaction) -> None:
        """Reload commands."""
        await interaction.response.send_message("Refreshing... Reload Discord for commands to be registered.")
        await self.bot.reload_command()

    feedback = app_commands.Group(name="feedback", description="Give feedbacks to System Trainees ")

    @feedback.command(name="add", description="Add feedback to a Trainee")
    async def add_feedback(self, interaction: discord.Interaction, trainee: discord.Member | discord.User) -> None:
        """Adds feedback to a trainee."""
        if isinstance(interaction.user, discord.User) or isinstance(trainee, discord.User):
            await interaction.response.send_message("This command can only be used inside the Systems Guild.", ephemeral=True)
            return
        if self.evaluator not in interaction.user.roles:
            await interaction.response.send_message("This command can only be used by Evaluators.", ephemeral=True)
            return
        if self.trainee not in trainee.roles:
            await interaction.response.send_message("User must have the Systems Trainee Role.", ephemeral=True)
            return
        existing_feedback: Row | None = await self.get_feedback(trainee.id, interaction.user.id)
        existing_feedback: str | None = existing_feedback["feedback"] if existing_feedback else None

        feedback = FeedbackModal(trainee, existing_feedback)
        await interaction.response.send_modal(feedback)

    @feedback.command(name="read", description="Read feedbacks given to you.")
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=False)
    async def read_feedback(self, interaction: discord.Interaction) -> None:
        staff: StaffMember | None = await database.staff.get_staff(discord_id=interaction.user.id)
        if staff is None:
            await interaction.response.send_message("You are not registered as a staff. Contact Systems Department if this is wrong.")
            return
        if "sys" not in [dept.key for dept in staff.departments]:
            await interaction.response.send_message("You are not registered as a Systems Department Staff. Contact Systems Department if this is wrong.")
            return
        feedbacks: Iterable[Row] = await self.get_all_feedback(interaction.user.id)
        if not feedbacks:
            await interaction.response.send_message("No feedbacks found.", ephemeral=True)
            return
        embed = FeedbackEmbed(interaction.user, await self.get_all_feedback(interaction.user.id))
        await interaction.response.send_message(embed=embed, files=embed.files, ephemeral=True)

    # Database Operations
    async def get_all_feedback(self, discord_staff_id: int) -> Iterable[Row]:
        query = """
        SELECT f.feedback, s.discord_id as staff_discord_id, n.discord_id as noter_discord_id
        FROM department_systems_trainee_feedback f
        LEFT JOIN staff_staff s ON  f.staff_id = s.staff_id
        LEFT JOIN staff_staff n on f.feedback_by = n.staff_id
        WHERE s.discord_id = :discord_staff_id;
        """
        db = Database()
        res: Iterable[Row] = await db.fetchall(query, {"discord_staff_id": discord_staff_id})
        return res

    async def get_feedback(self, discord_staff_id: int, feedback_staff_id: int) -> Row | None:
        query = """
        SELECT f.feedback 
        FROM department_systems_trainee_feedback f
        LEFT JOIN staff_staff s ON  f.staff_id = s.staff_id
        LEFT JOIN staff_staff n on f.feedback_by = n.staff_id
        WHERE s.discord_id = :discord_staff_id AND n.discord_id = :feedback_staff_id;
        """
        db = Database()
        res: Row | None = await db.fetchone(query, {"discord_staff_id": discord_staff_id, "feedback_staff_id": feedback_staff_id})
        return res

    async def store_feedback(self, discord_staff_id: int, feedback: str, discord_feedback_by: int):
        query = """
        INSERT INTO
            department_systems_trainee_feedback (staff_id, feedback, feedback_by)
        VALUES
            (
                (SELECT staff_id FROM staff_staff WHERE discord_id = :discord_staff_id),
                :feedback,
                (SELECT staff_id FROM staff_staff WHERE discord_id = :feedback_by)
            )
        ON CONFLICT (staff_id, feedback_by) DO UPDATE
            SET feedback = EXCLUDED.feedback
        RETURNING *;
        """
        db = Database()
        res: Row | None = await db.fetchone(query, {"discord_staff_id": discord_staff_id, "feedback": feedback, "feedback_by": discord_feedback_by})
        if not res:
            raise ValueError("Something went wrong.")


async def setup(bot: MultipurposeBot) -> None:  # noqa: D103
    await bot.add_cog(System(bot))
