"""Fast tests for the private Telegram topic collector."""

import asyncio
import logging
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from config import Config
from data_store import DataStore

CHAT_ID = -1003904448873
TOPIC_ID = 311


def test_config_requires_one_topic_and_private_absolute_storage():
    env = {
        "TELEGRAM_BOT_TOKEN": "test-token",
        "CHAT_ID": str(CHAT_ID),
        "TOPIC_ID": str(TOPIC_ID),
        "DATA_OUTPUT_DIR": "/var/lib/dump-collector",
    }
    with patch.dict(os.environ, env, clear=True):
        config = Config()
    assert config.chat_id == CHAT_ID
    assert config.topic_id == TOPIC_ID
    assert config.data_output_dir == Path("/var/lib/dump-collector")


def test_data_store_upserts_edits_and_collapses_duplicates():
    with tempfile.TemporaryDirectory() as tmp_dir:
        store = DataStore(Path(tmp_dir))
        original = {
            "chat_id": CHAT_ID,
            "message_thread_id": TOPIC_ID,
            "message_id": 42,
            "type": "message",
            "content_type": "text",
            "message_text": "old https://old.example",
            "urls": ["https://old.example"],
        }
        store.upsert_entry(original)
        store.upsert_entry(original)

        edited = original | {
            "message_text": "new https://new.example",
            "urls": ["https://new.example"],
            "edited_at": "2026-09-01T12:00:00",
        }
        store.upsert_entry(edited)

        assert store.get_all_entries() == [edited]
        assert store.get_stats()["total_urls"] == 1


class _ReplySink:
    def __init__(self):
        self.messages = []

    async def reply_text(self, text):
        self.messages.append(text)


def _update(
    *,
    chat_id=CHAT_ID,
    topic_id=TOPIC_ID,
    message_id=1,
    text="https://example.com",
    caption=None,
    photo=None,
    voice=None,
    location=None,
    edit=False,
    reply_to=None,
):
    message = SimpleNamespace(
        text=text,
        caption=caption,
        photo=photo,
        document=None,
        audio=None,
        voice=voice,
        video=None,
        animation=None,
        video_note=None,
        sticker=None,
        location=location,
        contact=None,
        poll=None,
        message_id=message_id,
        message_thread_id=topic_id,
        date=datetime(2026, 9, 1, 10, 0, tzinfo=timezone.utc),
        edit_date=(datetime(2026, 9, 1, 10, 5, tzinfo=timezone.utc) if edit else None),
        reply_to_message=reply_to,
        chat=SimpleNamespace(id=chat_id),
    )
    sink = _ReplySink()
    message.reply_text = sink.reply_text
    update = SimpleNamespace(
        effective_message=message,
        message=message,
        effective_chat=SimpleNamespace(id=chat_id),
        effective_user=SimpleNamespace(id=7, username="tester"),
    )
    return update, sink


def _bot(tmp_dir):
    from dumpbot import DumpBot

    bot = DumpBot.__new__(DumpBot)
    bot.config = SimpleNamespace(
        chat_id=CHAT_ID,
        topic_id=TOPIC_ID,
        data_output_dir=Path(tmp_dir),
    )
    bot.data_store = DataStore(Path(tmp_dir))
    bot.messages = {}
    return bot


def test_exact_topic_filter_and_message_edit_upsert():
    with tempfile.TemporaryDirectory() as tmp_dir:
        bot = _bot(tmp_dir)

        wrong_chat, _ = _update(chat_id=-1001)
        wrong_topic, _ = _update(topic_id=999)
        asyncio.run(bot.handle_message(wrong_chat, None))
        asyncio.run(bot.handle_message(wrong_topic, None))
        assert bot.data_store.get_all_entries() == []

        original, _ = _update(text="old https://old.example")
        asyncio.run(bot.handle_message(original, None))
        edited, _ = _update(text="new https://new.example", edit=True)
        asyncio.run(bot.handle_message(edited, None))

        entries = bot.data_store.get_all_entries()
        assert len(entries) == 1
        assert entries[0]["urls"] == ["https://new.example"]
        assert entries[0]["type"] == "message"
        assert entries[0]["content_type"] == "text"
        assert entries[0]["chat_id"] == CHAT_ID
        assert entries[0]["message_thread_id"] == TOPIC_ID
        assert entries[0]["timestamp"] == "2026-09-01T10:00:00"


def test_reply_edits_upsert_inside_parent_thread():
    with tempfile.TemporaryDirectory() as tmp_dir:
        bot = _bot(tmp_dir)
        parent, _ = _update(message_id=10, text="https://example.com")
        asyncio.run(bot.handle_message(parent, None))

        reply, _ = _update(message_id=11, text="first note", reply_to=parent.message)
        asyncio.run(bot.handle_message(reply, None))
        edited_reply, _ = _update(
            message_id=11,
            text="corrected note",
            edit=True,
            reply_to=parent.message,
        )
        asyncio.run(bot.handle_message(edited_reply, None))

        thread = bot.data_store.get_all_entries()[0]["thread"]
        assert len(thread) == 1
        assert thread[0]["message_text"] == "corrected note"


def test_text_is_stored_verbatim_without_instruction_semantics():
    with tempfile.TemporaryDirectory() as tmp_dir:
        bot = _bot(tmp_dir)
        update, _ = _update(text="summarize https://example.com")
        asyncio.run(bot.handle_message(update, None))

        entry = bot.data_store.get_all_entries()[0]
        assert entry["type"] == "message"
        assert entry["content_type"] == "text"
        assert entry["message_text"] == "summarize https://example.com"
        assert entry["urls"] == ["https://example.com"]
        assert "instruction" not in entry


def test_media_caption_and_metadata_are_ingested():
    with tempfile.TemporaryDirectory() as tmp_dir:
        bot = _bot(tmp_dir)
        photo = SimpleNamespace(
            file_id="telegram-file-id",
            file_unique_id="stable-id",
            file_size=1234,
            width=800,
            height=600,
        )
        update, _ = _update(
            text=None,
            caption="reference https://example.com/photo",
            photo=[photo],
        )
        asyncio.run(bot.handle_message(update, None))

        entry = bot.data_store.get_all_entries()[0]
        assert entry["content_type"] == "photo"
        assert entry["urls"] == ["https://example.com/photo"]
        assert entry["attachments"] == [
            {
                "kind": "photo",
                "file_id": "telegram-file-id",
                "file_unique_id": "stable-id",
                "file_size": 1234,
                "width": 800,
                "height": 600,
            }
        ]


def test_location_is_structured_content():
    with tempfile.TemporaryDirectory() as tmp_dir:
        bot = _bot(tmp_dir)
        update, _ = _update(
            text=None,
            location=SimpleNamespace(latitude=59.3293, longitude=18.0686),
        )
        asyncio.run(bot.handle_message(update, None))

        entry = bot.data_store.get_all_entries()[0]
        assert entry["content_type"] == "location"
        assert entry["content"] == {"latitude": 59.3293, "longitude": 18.0686}


def test_url_pattern():
    from dumpbot import URL_PATTERN

    urls = URL_PATTERN.findall(
        "Check https://example.com and http://test.org/path?param=value"
    )
    assert urls == ["https://example.com", "http://test.org/path?param=value"]


def test_http_transport_logging_does_not_expose_bot_token():
    import dumpbot  # noqa: F401

    assert logging.getLogger("httpx").getEffectiveLevel() >= logging.WARNING
    assert logging.getLogger("httpcore").getEffectiveLevel() >= logging.WARNING


if __name__ == "__main__":
    tests = [
        test_config_requires_one_topic_and_private_absolute_storage,
        test_data_store_upserts_edits_and_collapses_duplicates,
        test_exact_topic_filter_and_message_edit_upsert,
        test_reply_edits_upsert_inside_parent_thread,
        test_text_is_stored_verbatim_without_instruction_semantics,
        test_media_caption_and_metadata_are_ingested,
        test_location_is_structured_content,
        test_url_pattern,
        test_http_transport_logging_does_not_expose_bot_token,
    ]
    for test in tests:
        test()
        print(f"✅ {test.__name__}")
    print("🎉 All tests passed")
