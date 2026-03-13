#!/usr/bin/env python3
"""Debug script to test bot message reception."""

import asyncio
import logging
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes

from config import Config

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.DEBUG
)
logger = logging.getLogger(__name__)


async def debug_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Log all incoming messages for debugging."""
    logger.info(f"=== INCOMING MESSAGE ===")
    logger.info(f"Chat ID: {update.effective_chat.id}")
    logger.info(f"Chat Type: {update.effective_chat.type}")
    logger.info(f"User: {update.effective_user.username}")
    logger.info(f"Message: {update.effective_message.text}")
    logger.info(f"========================")


def main():
    config = Config()
    logger.info(f"Starting debug bot with chat_id: {config.chat_id}")

    app = Application.builder().token(config.bot_token).build()
    app.add_handler(MessageHandler(filters.ALL, debug_handler))

    logger.info("Debug bot starting...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    main()