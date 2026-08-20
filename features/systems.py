"""Systems Cog - For use of the Systems Department."""

from __future__ import annotations

import logging
import re
import time
from typing import TYPE_CHECKING, Any, Self
from typing import TYPE_CHECKING, Any, Self

import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

import database
import features
from database.core import Database
from database.department import set_department_config, set_department_server
from database.models import Department, StaffMember
from database.models import Department, StaffMember
from database.staff import has_staff_admin_perms
from features.views.feedback import FeedbackEmbed, FeedbackModal
from features.views.feedback import FeedbackEmbed, FeedbackModal

if TYPE_CHECKING:
    from collections.abc import Iterable

    from aiosqlite import Row
    from discord.guild import Guild
    from discord.role import Role

    from collections.abc import Iterable

    from aiosqlite import Row
    from discord.guild import Guild
    from discord.role import Role

    from main import MultipurposeBot

log: logging.Logger = logging.getLogger(f"App.{__name__}")
log: logging.Logger = logging.getLogger(f"App.{__name__}")
load_dotenv()


class System(commands.Cog):
    """Systems Cog: Commands are for administration of the whole system."""

    instance: Self | None = None

    instance: Self | None = None

    def __init__(self, bot: MultipurposeBot) -> None:
        System.instance = self
        self.bot: MultipurposeBot = bot

    async def cog_load(self) -> None:
        """Configures this cog."""
        sysdept: Department | None = await database.department.get_department("sys")
        assert sysdept, "Systems Department is not found."
        guild_ids: list[int] = sysdept.servers
        config: dict[str, Any] = sysdept.configuration

        guild: Guild | None = await self.bot.cached_fetch_guild(guild_id=guild_ids[0])
        if guild is None:
            raise ValueError("Guild from Database not found.")
        trainee: Role | None = guild.get_role(config["trainee"])
        if trainee is None:
            raise ValueError("Role from Database not found.")
        self.trainee: Role = trainee

        evaluator: Role | None = guild.get_role(config["evaluator"])
        if evaluator is None:
            raise ValueError("Role from Database not found.")
        self.evaluator: Role = evaluator
        await features.command_load(self, [sysdept])

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

    configure = app_commands.Group(name="configure", description="Configure ", extras={"scope": {"dm": True, "department": False}})

    @app_commands.allowed_contexts(guilds=False, dms=True, private_channels=False)
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

    @app_commands.allowed_contexts(guilds=False, dms=True, private_channels=False)
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
        if not await has_staff_admin_perms(discord_id=interaction.user.id):
            await interaction.response.send_message("You are not permitted.", ephemeral=True)
            return

        await interaction.response.send_message("Refreshing... Reload Discord for commands to be registered.")
        await self.bot.reload_command()

    feedback = app_commands.Group(name="feedback", description="Give feedbacks to System Trainees ", extras={"scope": {"dm": False, "department": True}})

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
    async def read_feedback(self, interaction: discord.Interaction) -> None:  # if there is a way to put this function on dms too, that would be awesome
        """Show the calling staff member all feedback submitted to them.

        Args:
            interaction: The interaction that triggered this command.
        """
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
        """Get all feedback entries recorded for a staff member.

        Args:
            discord_staff_id: The Discord user ID of the staff trainee to look up.

        Returns:
            Iterable[Row]: Rows containing feedback text and the Discord IDs of the staff and noter.
        """
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
        """Get a single feedback entry given to one staff member by another.

        Args:
            discord_staff_id: The Discord user ID of the staff member the feedback is about.
            feedback_staff_id: The Discord user ID of the staff member who gave the feedback.

        Returns:
            Row | None: The matching feedback row, or None if not found.
        """
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

    async def store_feedback(self, discord_staff_id: int, feedback: str, discord_feedback_by: int) -> None:
        """Upsert a feedback entry for a staff member.

        Args:
            discord_staff_id: The Discord user ID of the staff member the feedback is about.
            feedback: The feedback text content.
            discord_feedback_by: The Discord user ID of the staff member giving the feedback.

        Raises:
            ValueError: If the insert/update query does not return a row.
        """
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
