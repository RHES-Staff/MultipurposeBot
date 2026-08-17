from __future__ import annotations

import logging
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from discord import Object, app_commands
from discord.app_commands.commands import Command, Group

if TYPE_CHECKING:
    from database.models import Department
    from features.development import Development
    from features.systems import System

log = logging.getLogger(f"App.{__name__}")


def command_scope(*, dm: bool = False, department: bool = False) -> Callable[[app_commands.Command], app_commands.Command]:
    """Metadata only. command_load() reads this once DB data is available."""

    def deco(cmd: app_commands.Command) -> app_commands.Command:
        cmd.extras["scope"] = {"dm": dm, "department": department}
        return cmd

    return deco


async def command_load(cog: Development | System, depts: list[Department]) -> None:
    scoped: list[Group | Command[Any, (...), Any] | Command[Development, (...), Any] | Command[System, (...), Any]] = [
        c for c in cog.__cog_app_commands__ if c.extras.get("scope")
    ]
    for cmd in scoped:
        # discord.py can't auto-register what isn't in this list anymore
        cog.__cog_app_commands__.remove(cmd)  # ty: ignore[invalid-argument-type], i dont know how the fuck this worked, but it works, ty is not happy though

    guild_ids = {gid for dept in depts for gid in dept.servers}

    for cmd in scoped:
        scope = cmd.extras["scope"]
        cog.bot.tree.remove_command(cmd.name)  # defensive no-op, only matters on reload

        if scope["department"]:
            for gid in guild_ids:
                cog.bot.tree.add_command(cmd, guild=Object(id=gid))

        if scope["dm"]:
            cmd.allowed_contexts = app_commands.AppCommandContext(guild=False, dm_channel=True, private_channel=False)
            cmd.allowed_installs = app_commands.AppInstallationType(guild=True, user=False)
            cog.bot.tree.add_command(cmd)
