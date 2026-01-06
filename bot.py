# bot.py

import os

import discord
from discord.ext import commands
from dotenv import load_dotenv

from database import db  # juste pour initialiser la BDD

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)


@bot.event
async def on_ready():
    print(f"Connecté en tant que {bot.user} (ID: {bot.user.id})")
    print("------")


async def main():
    async with bot:
        # charger les cogs
        await bot.load_extension("cogs.quiz")
        await bot.load_extension("cogs.duel")
        await bot.load_extension("cogs.battle_royale")
        await bot.load_extension("cogs.scheduler")
        await bot.start(TOKEN)


if __name__ == "__main__":
    import asyncio
    if not TOKEN:
        raise RuntimeError("DISCORD_TOKEN manquant dans .env")
    asyncio.run(main())
