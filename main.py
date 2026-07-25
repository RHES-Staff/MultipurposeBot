import logging
import logging.config
import os
import asyncio
import json

from discord import Intents
from discord.ext import commands
from dotenv import load_dotenv

import database

log = logging.getLogger(f"App.{__name__}")
load_dotenv()

class MultipurposeBot(commands.Bot):
    def __init__(self):
        intents = Intents.default()
        intents.message_content = True
        intents.members = True
        intents.voice_states = True
        intents.guilds = True
        intents.typing = False
        super().__init__(command_prefix="&", intents=intents)

    async def setup_hook(self):
        os.makedirs("logs", exist_ok=True)
        db = database.Database()
        await db.connect()

        with open("logging.json", "r", encoding="utf-8") as f:
            config = json.load(f)
        logging.config.dictConfig(config)

        self.serverDepartments = await database.discordServers.getAllServersOfDepartments()
        self.servers = await database.discordServers.getAllRegisteredServers()

        # load all discord handlers automatically
        cogs_dir = os.path.join(os.path.dirname(__file__), "features")
        for filename in os.listdir(cogs_dir):
            if not filename.endswith(".py"):
                continue
            await self.load_extension(f"features.{filename[:-3]}")
            log.debug(f"Loaded Feature{filename}")
        
        for server in await database.discordServers.getAllRegisteredServers():
            await self.tree.sync(guild=server)
            
        log.info("Finished Bot Bootstrapping")
    
    async def on_ready(self):
        # can fire multiple times on reconnects
        log.info(f"Logged in as {self.user}")

async def main():
    bot = MultipurposeBot()
    db = database.Database()
    try:
        async with bot:
            await bot.start(os.getenv("TOKEN"))
    finally:
        await db.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log.warning("Keyboard Interrupt detected. Exiting...")
