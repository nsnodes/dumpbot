"""Ingest content from one private Telegram forum topic."""

import logging
import re
from datetime import datetime, timezone

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from config import Config
from data_store import DataStore

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
# python-telegram-bot's HTTP transport logs request URLs at INFO. Telegram puts
# the bot credential in that URL, so those records must never reach journald.
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

URL_PATTERN = re.compile(
    r"http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+"
)


class DumpBot:
    def __init__(self):
        self.config = Config()
        self.data_store = DataStore(self.config.data_output_dir)
        self.messages = {}  # (chat_id, topic_id, message_id) -> entry dict
        self._load_existing_messages()

    @staticmethod
    def _message_key(message, chat_id=None):
        message_chat = getattr(message, "chat", None)
        return (
            chat_id if chat_id is not None else getattr(message_chat, "id", None),
            getattr(message, "message_thread_id", None),
            message.message_id,
        )

    def _matches_source(self, update: Update) -> bool:
        """Accept only the private Steward Dump topic."""
        message = update.effective_message
        chat = update.effective_chat
        if message is None or chat is None or chat.id != self.config.chat_id:
            return False
        return message.message_thread_id == self.config.topic_id

    @staticmethod
    def _timestamp(message) -> str:
        timestamp = getattr(message, "date", None)
        if timestamp and timestamp.tzinfo is not None:
            timestamp = timestamp.astimezone(timezone.utc).replace(tzinfo=None)
        return (
            timestamp.isoformat()
            if timestamp
            else datetime.now(timezone.utc).replace(tzinfo=None).isoformat()
        )

    @staticmethod
    def _file_metadata(kind, telegram_file) -> dict:
        """Keep durable Telegram file metadata without assigning workflow meaning."""
        metadata = {"kind": kind}
        for field in (
            "file_id",
            "file_unique_id",
            "file_name",
            "mime_type",
            "file_size",
            "duration",
            "width",
            "height",
        ):
            value = getattr(telegram_file, field, None)
            if value is not None:
                metadata[field] = value
        return metadata

    @classmethod
    def _content(cls, message):
        """Normalize supported Telegram content into a neutral record shape."""
        text = getattr(message, "text", None)
        if text is not None:
            return "text", text, [], None

        caption = getattr(message, "caption", None) or ""
        photos = getattr(message, "photo", None) or []
        if photos:
            return "photo", caption, [cls._file_metadata("photo", photos[-1])], None

        for kind in (
            "document",
            "audio",
            "voice",
            "video",
            "animation",
            "video_note",
            "sticker",
        ):
            telegram_file = getattr(message, kind, None)
            if telegram_file is not None:
                return kind, caption, [cls._file_metadata(kind, telegram_file)], None

        location = getattr(message, "location", None)
        if location is not None:
            return (
                "location",
                caption,
                [],
                {
                    "latitude": location.latitude,
                    "longitude": location.longitude,
                },
            )

        contact = getattr(message, "contact", None)
        if contact is not None:
            content = {
                "phone_number": contact.phone_number,
                "first_name": contact.first_name,
            }
            for field in ("last_name", "user_id", "vcard"):
                value = getattr(contact, field, None)
                if value is not None:
                    content[field] = value
            return "contact", caption, [], content

        poll = getattr(message, "poll", None)
        if poll is not None:
            return (
                "poll",
                poll.question,
                [],
                {
                    "poll_id": poll.id,
                    "options": [option.text for option in poll.options],
                    "is_anonymous": poll.is_anonymous,
                    "allows_multiple_answers": poll.allows_multiple_answers,
                },
            )

        return None

    def _load_existing_messages(self):
        """Load current-schema messages on startup so replies remain threaded."""
        for entry in self.data_store.get_all_entries():
            if entry.get("type") != "message":
                continue
            message_id = entry.get("message_id")
            if message_id is not None:
                self.messages[
                    (
                        entry.get("chat_id"),
                        entry.get("message_thread_id"),
                        message_id,
                    )
                ] = entry

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Ingest supported content from the configured topic."""
        message = update.effective_message
        if not message or not self._matches_source(update):
            return

        normalized = self._content(message)
        if normalized is None:
            logger.info("Ignored unsupported Telegram message type")
            return

        content_type, message_text, attachments, content = normalized

        chat_id = update.effective_chat.id
        topic_id = message.message_thread_id
        message_key = self._message_key(message, chat_id)
        base = {
            "timestamp": self._timestamp(message),
            "chat_id": chat_id,
            "message_thread_id": topic_id,
            "user_id": getattr(update.effective_user, "id", None),
            "username": getattr(update.effective_user, "username", None) or "Unknown",
            "message_id": message.message_id,
            "type": "message",
            "content_type": content_type,
            "message_text": message_text,
            "urls": list(dict.fromkeys(URL_PATTERN.findall(message_text))),
            "attachments": attachments,
        }
        if content is not None:
            base["content"] = content
        if getattr(message, "edit_date", None):
            base["edited_at"] = message.edit_date.isoformat()

        if getattr(message, "reply_to_message", None):
            reply_key = self._message_key(message.reply_to_message, chat_id)
            base["reply_to_message_id"] = message.reply_to_message.message_id
            if reply_key in self.messages:
                parent_entry = self.messages[reply_key]
                parent_entry.setdefault("thread", [])
                reply_matches = [
                    index
                    for index, reply in enumerate(parent_entry["thread"])
                    if DataStore.entry_key(reply) == message_key
                ]
                if reply_matches:
                    parent_entry["thread"][reply_matches[0]] = base
                    for index in reversed(reply_matches[1:]):
                        del parent_entry["thread"][index]
                else:
                    parent_entry["thread"].append(base)
                self.data_store.update_entry(parent_entry)
                logger.info("Saved %s reply in thread", content_type)
                return

        entry = base | {"thread": self.messages.get(message_key, {}).get("thread", [])}
        self.data_store.upsert_entry(entry)
        self.messages[message_key] = entry
        logger.info(
            "Saved %s message with %d URL(s)", content_type, len(entry["urls"])
        )

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command."""
        if not self._matches_source(update):
            return
        await update.message.reply_text(
            "DumpBot is running. I'll collect content from this topic."
        )

    async def stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show collection statistics."""
        if not self._matches_source(update):
            return
        stats = self.data_store.get_stats()
        await update.message.reply_text(
            f"📊 Stats:\n"
            f"• Total entries: {stats['total_entries']}\n"
            f"• URLs found: {stats['total_urls']}\n"
            f"• Content types: {stats['content_types']}\n"
            f"• Last updated: {stats['last_updated']}"
        )

    def run(self):
        """Start the bot."""
        app = Application.builder().token(self.config.bot_token).build()

        app.add_handler(CommandHandler("start", self.start_command))
        app.add_handler(CommandHandler("stats", self.stats_command))
        app.add_handler(
            MessageHandler(filters.ALL & ~filters.COMMAND, self.handle_message)
        )

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


if __name__ == "__main__":
    main()
