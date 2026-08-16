"""Leaderboard View."""

from __future__ import annotations

import logging
from collections.abc import Iterable
from datetime import datetime, timezone
from typing import Any

import aiosqlite
import discord
from discord.ui import Modal, TextInput

from features import systems

log: logging.Logger = logging.getLogger(f"App.{__name__}")


class FeedbackModal(Modal):
    def __init__(self, trainee: discord.Member, default: str | None = None):
        self._trainee: discord.Member = trainee
        # dealing with rogue names and to go under the 45-char limit of labels
        label = f"Feedback Form {trainee.display_name}"
        if len(label) > 45:
            label: str = label[:44] + "…"

        self.answer: TextInput = TextInput(label="Feedback", style=discord.TextStyle.paragraph, default=default)
        super().__init__(title=label)
        self.add_item(self.answer)

    
    async def on_submit(self, interaction: discord.Interaction):
        syscog: systems.System | None = systems.System.instance
        assert syscog is not None
        try:
            await syscog.store_feedback(self._trainee.id, self.answer.value, interaction.user.id)
        except ValueError:
            await interaction.response.send_message("Something went wrong.", ephemeral=True)
        await interaction.response.send_message(f"Feedback received and stored for {self._trainee.display_name}", ephemeral=True)


class FeedbackEmbed(discord.Embed):
    """Embeds for Feedbacks - System."""

    files: list[discord.File]

    def __init__(self, member: discord.Member | discord.User, result: Iterable[aiosqlite.Row], **kwargs: Any) -> None:  # noqa: ANN401
        super().__init__(timestamp=datetime.now(tz=timezone.utc), **kwargs)
        self.files: list[discord.File] = [discord.File("assets/development.png", filename="development.png")]
        self.parse_row(result)
        self.set_footer(
            text="Multipurpose Bot - Systems",
            icon_url="attachment://development.png",
        )
        if isinstance(member, discord.Member):
            avatar: str = member.guild_avatar.url if member.guild_avatar else member.avatar.url if member.avatar else member.default_avatar.url
        else:
            avatar: str = member.avatar.url if member.avatar else member.default_avatar.url
        self.set_author(name=member.display_name, icon_url=avatar)

    def parse_row(self, result: Iterable[aiosqlite.Row]) -> None:
        for i, row in enumerate(result):
            self.add_field(name=f"Feedback #{i + 1}", value=f"**From**: <@{row['noter_discord_id']}>\n{row['feedback']}", inline=False)
