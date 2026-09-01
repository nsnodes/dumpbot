#!/usr/bin/env python3
"""
Telegram bot that collects links and comments from a group chat
for the nsnodes digest pipeline.
"""

import json
import logging
import re
from datetime import datetime, timezone
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
# python-telegram-bot's HTTP transport logs request URLs at INFO. Telegram puts
# the bot credential in that URL, so those records must never reach journald.
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

URL_PATTERN = re.compile(
    r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'
)


class DumpBot:
    def __init__(self):
        self.config = Config()
        self.data_store = DataStore(self.config.data_output_dir)
        self.digest = DigestIntegration(self.config.data_output_dir)
        self.git_sync = GitSync()
        # Track messages with links to build threads
        self.link_messages = {}  # (chat_id, topic_id, message_id) -> entry dict
        self._load_existing_link_messages()

    @staticmethod
    def _message_key(message, chat_id=None):
        message_chat = getattr(message, 'chat', None)
        return (
            chat_id if chat_id is not None else getattr(message_chat, 'id', None),
            getattr(message, 'message_thread_id', None),
            message.message_id,
        )

    def _matches_source(self, update: Update) -> bool:
        """Accept only the configured chat and, when set, exact forum topic."""
        message = update.effective_message
        chat = update.effective_chat
        if message is None or chat is None or str(chat.id) != self.config.chat_id:
            return False
        if self.config.topic_id is None:
            return True
        return message.message_thread_id == self.config.topic_id

    @staticmethod
    def _timestamp(message) -> str:
        timestamp = getattr(message, 'date', None)
        if timestamp and timestamp.tzinfo is not None:
            timestamp = timestamp.astimezone(timezone.utc).replace(tzinfo=None)
        return timestamp.isoformat() if timestamp else datetime.now().isoformat()

    def _load_existing_link_messages(self):
        """Load existing link messages on startup to track threads."""
        entries = self.data_store.get_all_entries()
        for entry in entries:
            if entry.get('type') == 'link' or ('urls' in entry and 'type' not in entry):
                message_id = entry.get('message_id')
                if message_id:
                    configured_chat_id = int(self.config.chat_id)
                    key = (
                        entry.get('chat_id', configured_chat_id),
                        entry.get('message_thread_id', self.config.topic_id),
                        message_id,
                    )
                    self.link_messages[key] = entry

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Process incoming messages for links and comments."""
        message = update.effective_message

        if not message or not message.text:
            return

        if not self._matches_source(update):
            return

        chat_id = update.effective_chat.id
        topic_id = message.message_thread_id
        message_key = self._message_key(message, chat_id)
        base = {
            'timestamp': self._timestamp(message),
            'chat_id': chat_id,
            'message_thread_id': topic_id,
            'user_id': update.effective_user.id,
            'username': update.effective_user.username or 'Unknown',
            'message_id': message.message_id,
        }
        if getattr(message, 'edit_date', None):
            base['edited_at'] = message.edit_date.isoformat()

        # Handle @claude directives for digest instructions
        if message.text.startswith('@claude'):
            entry = base | {
                'type': 'directive',
                'instruction': message.text[7:].strip(),  # Remove @claude prefix
            }

            self.data_store.upsert_entry(entry)
            self.link_messages.pop(message_key, None)
            logger.info(f"Saved directive from {entry['username']}: {entry['instruction'][:50]}...")
            return

        # Check if this is a reply to a message with links
        if message.reply_to_message:
            reply_key = self._message_key(message.reply_to_message, chat_id)
            if reply_key in self.link_messages:
                # This is a reply to a link message, add it to the thread
                parent_entry = self.link_messages[reply_key]

                # Initialize thread if not exists
                if 'thread' not in parent_entry:
                    parent_entry['thread'] = []

                # Add this reply to the thread
                reply_entry = base | {
                    'message_text': message.text,
                }
                reply_matches = [
                    index for index, reply in enumerate(parent_entry['thread'])
                    if DataStore.entry_key(reply) == message_key
                ]
                if reply_matches:
                    parent_entry['thread'][reply_matches[0]] = reply_entry
                    for index in reversed(reply_matches[1:]):
                        del parent_entry['thread'][index]
                else:
                    parent_entry['thread'].append(reply_entry)

                # Update the stored entry
                self.data_store.update_entry(parent_entry)
                logger.info(f"Added reply from {update.effective_user.username} to thread")
                return

        urls = URL_PATTERN.findall(message.text)

        if urls:
            entry = base | {
                'type': 'link',
                'message_text': message.text,
                'urls': list(dict.fromkeys(urls)),
                'thread': []  # Initialize empty thread for potential replies
            }

            existing = self.link_messages.get(message_key)
            if existing:
                entry['thread'] = existing.get('thread', [])
            self.data_store.upsert_entry(entry)
            # Track this message for potential replies
            self.link_messages[message_key] = entry

            logger.info(f"Saved {len(urls)} URLs from {entry['username']}")
        elif message_key in self.link_messages:
            # An edit may remove the last URL. Do not leave stale content in the
            # feed after Telegram says the source message no longer contains it.
            self.data_store.delete_entry(base)
            del self.link_messages[message_key]
        elif getattr(message, 'edit_date', None):
            # The edited message may previously have been a directive.
            self.data_store.delete_entry(base)

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command."""
        if not self._matches_source(update):
            return
        await update.message.reply_text("DumpBot is running. I'll collect links from this chat.")

    async def stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show collection statistics."""
        if not self._matches_source(update):
            return
        stats = self.data_store.get_stats()
        await update.message.reply_text(
            f"📊 Stats:\n"
            f"• Total entries: {stats['total_entries']}\n"
            f"• Links collected: {stats['total_urls']}\n"
            f"• Directives: {stats.get('total_directives', 0)}\n"
            f"• Last updated: {stats['last_updated']}"
        )

    async def export_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Export collected data and commit to repository."""
        if not self._matches_source(update):
            return
        if not self.config.git_export_enabled:
            await update.message.reply_text(
                "Private collection is enabled; GitHub export is disabled."
            )
            return
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
