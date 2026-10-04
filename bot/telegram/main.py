"""Telegram bot entry point."""

import os
import logging
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from telegram.ext import Application, CommandHandler, MessageHandler, filters

import handlers
from shared.api_client import APIClient

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


def main() -> None:
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    base_url = os.environ.get("FASTAPI_BASE_URL", "http://fastapi:8000")

    handlers.api_client = APIClient(base_url)

    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler("start", handlers.start))
    app.add_handler(CommandHandler("help", handlers.help_command))
    app.add_handler(CommandHandler("layout", handlers.layout_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.handle_message))

    logger.info("Telegram bot starting (polling mode)…")
    app.run_polling()


if __name__ == "__main__":
    main()
