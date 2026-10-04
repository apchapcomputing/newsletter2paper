"""Discord bot entry point."""

import os
import re
import logging
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import discord
from discord.ext import commands

from shared.api_client import APIClient

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

_URL_RE = re.compile(r'https?://[^\s]+')

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="/", intents=intents)
api_client: APIClient = None
# Per-channel layout preference: {channel_id: "essay"|"newspaper"}
channel_layouts: dict = {}


@bot.event
async def on_ready():
    logger.info(f"Discord bot logged in as {bot.user}")


@bot.command(name="layout")
async def layout_command(ctx, layout_type: str = ""):
    if layout_type not in ("essay", "newspaper"):
        await ctx.send("Usage: `/layout essay`  or  `/layout newspaper`")
        return
    channel_layouts[ctx.channel.id] = layout_type
    await ctx.send(f"Layout set to: **{layout_type}**")


@bot.command(name="help")
async def help_command(ctx):
    await ctx.send(
        "**Newsletter2Paper Bot**\n"
        "Send me any article URL and I'll convert it to a printable PDF.\n\n"
        "`/layout essay` — single-column essay (default)\n"
        "`/layout newspaper` — three-column newspaper style\n"
        "`/help` — show this message"
    )


@bot.event
async def on_message(message):
    if message.author.bot:
        return

    await bot.process_commands(message)

    urls = _URL_RE.findall(message.content)
    if not urls:
        return

    url = urls[0]
    layout = channel_layouts.get(message.channel.id, "essay")
    status = await message.reply(f"Converting article… (layout: {layout})")

    try:
        result = await api_client.convert_article(url, layout_type=layout)
        if result.get("success") and result.get("pdf_url"):
            await status.edit(content=f"Done! Download your PDF:\n{result['pdf_url']}")
        else:
            await status.edit(content="Conversion failed. Please check the URL and try again.")
    except Exception as e:
        await status.edit(content=f"Error: {e}")


def main():
    global api_client
    token = os.environ["DISCORD_BOT_TOKEN"]
    base_url = os.environ.get("FASTAPI_BASE_URL", "http://fastapi:8000")
    api_client = APIClient(base_url)
    logger.info("Discord bot starting…")
    bot.run(token)


if __name__ == "__main__":
    main()
