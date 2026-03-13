#!/usr/bin/env python3
"""
Telegram bot that collects links and comments from a group chat
for the nsnodes digest pipeline.
"""

import json
import logging
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from config import Config
from data_store import DataStore
from digest_integration import DigestIntegration
from git_sync import GitSync


logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

URL_PATTERN = re.compile(
    r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'
)


class DumpBot:
    def __init__(self):
        self.config = Config()
        self.data_store = DataStore(self.config.data_output_dir)
        self.digest = DigestIntegration()
        self.git_sync = GitSync()

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Process incoming messages for links and comments."""
        message = update.effective_message

        if not message or not message.text:
            return

        # Only process messages from the configured chat
        if str(update.effective_chat.id) != self.config.chat_id:
            return

        urls = URL_PATTERN.findall(message.text)

        if urls:
            entry = {
                'timestamp': datetime.now().isoformat(),
                'user_id': update.effective_user.id,
                'username': update.effective_user.username or 'Unknown',
                'message_text': message.text,
                'urls': list(set(urls)),  # Remove duplicates
                'message_id': message.message_id
            }

            self.data_store.save_entry(entry)

            logger.info(f"Saved {len(urls)} URLs from {entry['username']}")

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command."""
        await update.message.reply_text("DumpBot is running. I'll collect links from this chat.")

    async def stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show collection statistics."""
        stats = self.data_store.get_stats()
        await update.message.reply_text(
            f"📊 Stats:\n"
            f"• Total entries: {stats['total_entries']}\n"
            f"• Total URLs: {stats['total_urls']}\n"
            f"• Last updated: {stats['last_updated']}"
        )

    async def export_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Export collected data and commit to repository."""
        try:
            all_entries = self.data_store.get_all_entries()

            # Export today's data for digest pipeline
            today = datetime.now().strftime('%Y-%m-%d')
            export_file = self.digest.export_daily_data(all_entries, today)

            # Commit and push to repository
            commit_success = self.git_sync.commit_daily_data([export_file], today)

            stats = self.data_store.get_stats()

            if commit_success:
                await update.message.reply_text(
                    f"✅ Exported and committed: {export_file}\n"
                    f"📊 {stats['total_entries']} messages, {stats['total_urls']} URLs\n"
                    f"🔄 Pushed to GitHub for digest pipeline"
                )
            else:
                await update.message.reply_text(
                    f"⚠️ Exported but commit failed: {export_file}\n"
                    f"📊 {stats['total_entries']} messages, {stats['total_urls']} URLs"
                )
        except Exception as e:
            await update.message.reply_text(f"❌ Export failed: {str(e)}")

    def run(self):
        """Start the bot."""
        app = Application.builder().token(self.config.bot_token).build()

        app.add_handler(CommandHandler("start", self.start_command))
        app.add_handler(CommandHandler("stats", self.stats_command))
        app.add_handler(CommandHandler("export", self.export_command))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))

        logger.info("Starting DumpBot...")
        app.run_polling(allowed_updates=Update.ALL_TYPES)


def main():
    """Main entry point for the bot."""
    try:
        bot = DumpBot()
        bot.run()
    except KeyboardInterrupt:
        print("\nBot stopped by user")
    except Exception as e:
        print(f"Failed to start bot: {e}")
        raise


if __name__ == '__main__':
    main()