import discord
from discord.ext import commands
from discord import app_commands
import sqlite3
import re

TOKEN = "XXX"

TEST_GUILD_ID = 1510555103344590878


intents = discord.Intents.default()
intents.guilds = True
intents.messages = True
intents.reactions = True
intents.message_content = True  

bot = commands.Bot(command_prefix="!", intents=intents)


conn = sqlite3.connect("reactionbot.db")
cur = conn.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS config (
    guild_id INTEGER PRIMARY KEY,
    channel_id INTEGER NOT NULL,
    emoji TEXT NOT NULL
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS points (
    guild_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    points INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (guild_id, user_id)
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS message_awards (
    message_id INTEGER PRIMARY KEY,
    guild_id INTEGER NOT NULL,
    winner_user_id INTEGER NOT NULL
)
""")

conn.commit()


def set_config(guild_id: int, channel_id: int, emoji: str):
    cur.execute("""
    INSERT INTO config (guild_id, channel_id, emoji)
    VALUES (?, ?, ?)
    ON CONFLICT(guild_id) DO UPDATE SET
        channel_id=excluded.channel_id,
        emoji=excluded.emoji
    """, (guild_id, channel_id, emoji))
    conn.commit()


def get_config(guild_id: int):
    row = cur.execute(
        "SELECT channel_id, emoji FROM config WHERE guild_id = ?",
        (guild_id,)
    ).fetchone()
    return row


def add_point(guild_id: int, user_id: int):
    cur.execute("""
    INSERT INTO points (guild_id, user_id, points)
    VALUES (?, ?, 1)
    ON CONFLICT(guild_id, user_id) DO UPDATE SET
        points = points + 1
    """, (guild_id, user_id))
    conn.commit()


def get_top(guild_id: int, limit: int = 10):
    return cur.execute("""
    SELECT user_id, points
    FROM points
    WHERE guild_id = ?
    ORDER BY points DESC, user_id ASC
    LIMIT ?
    """, (guild_id, limit)).fetchall()


def try_claim_first_reactor(message_id: int, guild_id: int, user_id: int) -> bool:
    """
    Atomic claim:
    - First insert wins (returns True)
    - Later attempts fail with IntegrityError (returns False)
    """
    try:
        cur.execute("""
        INSERT INTO message_awards (message_id, guild_id, winner_user_id)
        VALUES (?, ?, ?)
        """, (message_id, guild_id, user_id))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False

CUSTOM_EMOJI_REGEX = re.compile(r"^<a?:\w+:(\d+)>$")


def normalize_emoji_input(emoji_text: str) -> str:
    """
    Accepts:
    - Unicode emoji (👍)
    - Custom emoji mention (<:name:id> or <a:name:id>)
    Stores string representation used for comparison with payload emoji.
    """
    emoji_text = emoji_text.strip()
    return emoji_text

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} ({bot.user.id})")

    try:
        if TEST_GUILD_ID and TEST_GUILD_ID != 0:
            guild_obj = discord.Object(id=TEST_GUILD_ID)
            synced = await bot.tree.sync(guild=guild_obj)
            print(f"Synced {len(synced)} guild command(s) to {TEST_GUILD_ID}.")
        else:
            synced = await bot.tree.sync()
            print(f"Synced {len(synced)} global command(s). (Can take up to 1 hour to appear)")
    except Exception as e:
        print("Command sync failed:", e)


@bot.event
async def on_message(message: discord.Message):
    if not message.guild:
        return
    if message.author.bot:
        return

    conf = get_config(message.guild.id)
    if conf is None:
        await bot.process_commands(message)
        return

    channel_id, emoji = conf

    if message.channel.id == channel_id:
        try:
            await message.add_reaction(emoji)
        except discord.HTTPException:
            pass

    await bot.process_commands(message)


@bot.event
async def on_raw_reaction_add(payload: discord.RawReactionActionEvent):
    # Ignore DMs
    if payload.guild_id is None:
        return

    # Ignore bot's own reactions
    if bot.user and payload.user_id == bot.user.id:
        return

    conf = get_config(payload.guild_id)
    if conf is None:
        return

    channel_id, target_emoji = conf

    # Only configured channel
    if payload.channel_id != channel_id:
        return

    # Compare emoji string forms
    reacted_emoji = str(payload.emoji)
    if reacted_emoji != target_emoji:
        return

    # First reactor claim
    claimed = try_claim_first_reactor(payload.message_id, payload.guild_id, payload.user_id)
    if not claimed:
        return

    add_point(payload.guild_id, payload.user_id)


def guild_only_description():
    return "This command can only be used in a server."


if TEST_GUILD_ID and TEST_GUILD_ID != 0:
    TEST_GUILD = discord.Object(id=TEST_GUILD_ID)
else:
    TEST_GUILD = None


@bot.tree.command(
    name="setup",
    description="Set the channel + emoji.",
    guild=TEST_GUILD
)
@app_commands.describe(
    channel="Channel to watch",
    emoji="Emoji to use"
)
async def setup(interaction: discord.Interaction, channel: discord.TextChannel, emoji: str):
    if interaction.guild is None:
        await interaction.response.send_message(guild_only_description(), ephemeral=True)
        return

    if not interaction.user.guild_permissions.manage_guild:
        await interaction.response.send_message(
            "You need **Manage Server** permission to use this.",
            ephemeral=True
        )
        return

    emoji = normalize_emoji_input(emoji)

    # Basic check for custom emoji format validity
    # (unicode emoji will just pass through)
    if emoji.startswith("<") and not CUSTOM_EMOJI_REGEX.match(emoji):
        await interaction.response.send_message(
            "That custom emoji format looks invalid. Use format like `<:name:id>` or `<a:name:id>`.",
            ephemeral=True
        )
        return

    set_config(interaction.guild_id, channel.id, emoji)

    await interaction.response.send_message(
        f"✅ Setup saved!\n"
        f"• Channel: {channel.mention}\n"
        f"• Emoji: {emoji}\n\n"
        f"I will auto-react to every message there and count only the **first** valid reactor per message.",
        ephemeral=True
    )


@bot.tree.command(
    name="leaderboard",
    description="Show the Instructor leaderboard.",
    guild=TEST_GUILD
)
async def leaderboard(interaction: discord.Interaction):
    if interaction.guild is None:
        await interaction.response.send_message(guild_only_description(), ephemeral=True)
        return

    rows = get_top(interaction.guild_id, limit=10)

    embed = discord.Embed(
        title="Instructor Leaderboard",
        color=discord.Color.gold()
    )

    if not rows:
        embed.description = "No points yet."
    else:
        lines = []
        for i, (user_id, pts) in enumerate(rows, start=1):
            lines.append(f"**{i}.** <@{user_id}> — **{pts}**")
        embed.description = "\n".join(lines)

    await interaction.response.send_message(embed=embed)


@bot.tree.command(
    name="ping",
    description="Check if bot is alive.",
    guild=TEST_GUILD
)
async def ping(interaction: discord.Interaction):
    await interaction.response.send_message(f"Pong! `{round(bot.latency * 1000)}ms`", ephemeral=True)

bot.run(TOKEN)
