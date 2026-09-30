"""Telegram bot message handlers."""

import re
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from telegram import Update
from telegram.ext import ContextTypes

from shared.api_client import APIClient

_URL_RE = re.compile(r'https?://[^\s]+')

api_client: APIClient = None  # Set from main.py


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Send me any article URL and I'll convert it to a printable PDF.\n\n"
        "Commands:\n"
        "/layout essay — single-column essay (default)\n"
        "/layout newspaper — three-column newspaper style\n"
        "/help — show this message"
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await start(update, context)


async def layout_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    args = context.args
    if not args or args[0] not in ("essay", "newspaper"):
        await update.message.reply_text("Usage: /layout essay  or  /layout newspaper")
        return
    context.chat_data["layout"] = args[0]
    await update.message.reply_text(f"Layout set to: {args[0]}")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = update.message.text or ""
    urls = _URL_RE.findall(text)

    if not urls:
        await update.message.reply_text("Send me an article URL to convert it to PDF.")
        return

    url = urls[0]
    layout = context.chat_data.get("layout", "essay")
    status_msg = await update.message.reply_text(f"Converting article… (layout: {layout})")

    try:
        result = await api_client.convert_article(url, layout_type=layout)
        if result.get("success") and result.get("pdf_url"):
            await status_msg.edit_text(
                f"Done! Download your PDF:\n{result['pdf_url']}"
            )
        else:
            await status_msg.edit_text("Conversion failed. Please check the URL and try again.")
    except Exception as e:
        await status_msg.edit_text(f"Error: {e}")
