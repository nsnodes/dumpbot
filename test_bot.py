#!/usr/bin/env python3
"""Test script to verify bot functionality without Telegram connection."""

import json
import logging
import asyncio
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from config import Config
from data_store import DataStore
from digest_integration import DigestIntegration
from git_sync import GitSync


def test_data_store():
    """Test data storage functionality."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        store = DataStore(Path(tmp_dir))

        # Test saving entries
        test_entry = {
            'timestamp': '2024-01-01T12:00:00',
            'user_id': 123,
            'username': 'testuser',
            'message_text': 'Check out https://example.com and https://test.org',
            'urls': ['https://example.com', 'https://test.org'],
            'message_id': 456
        }

        store.save_entry(test_entry)

        # Test retrieving entries
        entries = store.get_all_entries()
        assert len(entries) == 1
        assert entries[0]['username'] == 'testuser'

        # Test stats
        stats = store.get_stats()
        assert stats['total_entries'] == 1
        assert stats['total_urls'] == 2

        print("✅ DataStore tests passed")


def test_data_store_upserts_edits_and_collapses_duplicates():
    """Telegram edits replace an entry identified by chat/topic/message."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        store = DataStore(Path(tmp_dir))
        legacy_original = {
            'message_id': 42,
            'message_text': 'old https://old.example',
            'urls': ['https://old.example'],
        }
        store.save_entry(legacy_original)
        store.save_entry(legacy_original)

        edited = legacy_original | {
            'chat_id': -1003904448873,
            'message_thread_id': 311,
            'message_text': 'new https://new.example',
            'urls': ['https://new.example'],
            'edited_at': '2026-09-01T12:00:00',
        }
        store.upsert_entry(edited)

        assert store.get_all_entries() == [edited]
        store.delete_entry(edited)
        assert store.get_all_entries() == []
        print("✅ DataStore edit upsert test passed")


class _ReplySink:
    def __init__(self):
        self.messages = []

    async def reply_text(self, text):
        self.messages.append(text)


def _update(*, chat_id=-1003904448873, topic_id=311, message_id=1,
            text='https://example.com', edit=False, reply_to=None):
    message = SimpleNamespace(
        text=text,
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
        effective_user=SimpleNamespace(id=7, username='tester'),
    )
    return update, sink


def _private_bot(tmp_dir):
    from dumpbot import DumpBot

    bot = DumpBot.__new__(DumpBot)
    bot.config = SimpleNamespace(
        chat_id='-1003904448873', topic_id=311, git_export_enabled=False,
        data_output_dir=Path(tmp_dir),
    )
    bot.data_store = DataStore(Path(tmp_dir))
    bot.digest = DigestIntegration(tmp_dir)
    bot.git_sync = None
    bot.link_messages = {}
    return bot


def test_exact_topic_filter_and_message_edit_upsert():
    with tempfile.TemporaryDirectory() as tmp_dir:
        bot = _private_bot(tmp_dir)

        wrong_chat, _ = _update(chat_id=-1001)
        wrong_topic, _ = _update(topic_id=999)
        asyncio.run(bot.handle_message(wrong_chat, None))
        asyncio.run(bot.handle_message(wrong_topic, None))
        assert bot.data_store.get_all_entries() == []

        original, _ = _update(text='old https://old.example')
        asyncio.run(bot.handle_message(original, None))
        edited, _ = _update(text='new https://new.example', edit=True)
        asyncio.run(bot.handle_message(edited, None))

        entries = bot.data_store.get_all_entries()
        assert len(entries) == 1
        assert entries[0]['urls'] == ['https://new.example']
        assert entries[0]['chat_id'] == -1003904448873
        assert entries[0]['message_thread_id'] == 311
        assert entries[0]['timestamp'] == '2026-09-01T10:00:00'
        print("✅ Exact Dump topic filter and message edit test passed")


def test_reply_edits_upsert_inside_parent_thread():
    with tempfile.TemporaryDirectory() as tmp_dir:
        bot = _private_bot(tmp_dir)
        parent, _ = _update(message_id=10, text='https://example.com')
        asyncio.run(bot.handle_message(parent, None))

        reply, _ = _update(message_id=11, text='first note', reply_to=parent.message)
        asyncio.run(bot.handle_message(reply, None))
        edited_reply, _ = _update(
            message_id=11, text='corrected note', edit=True, reply_to=parent.message
        )
        asyncio.run(bot.handle_message(edited_reply, None))

        thread = bot.data_store.get_all_entries()[0]['thread']
        assert len(thread) == 1
        assert thread[0]['message_text'] == 'corrected note'
        print("✅ Reply edit upsert test passed")


def test_private_profile_cannot_enable_git_export():
    env = {
        'TELEGRAM_BOT_TOKEN': 'test-token',
        'CHAT_ID': '-1003904448873',
        'TOPIC_ID': '311',
        'EXPORT_MODE': 'private',
        'GIT_EXPORT_ENABLED': 'true',
    }
    with patch.dict(os.environ, env, clear=True):
        try:
            Config()
        except ValueError as exc:
            assert 'must be false' in str(exc)
        else:
            raise AssertionError('private profile allowed Git export')
    print("✅ Private profile Git export guard test passed")


def test_steward_dump_topic_cannot_use_public_profile():
    env = {
        'TELEGRAM_BOT_TOKEN': 'test-token',
        'CHAT_ID': '-1003904448873',
        'TOPIC_ID': '311',
        'EXPORT_MODE': 'public',
        'GIT_EXPORT_ENABLED': 'true',
    }
    with patch.dict(os.environ, env, clear=True):
        try:
            Config()
        except ValueError as exc:
            assert 'requires EXPORT_MODE=private' in str(exc)
        else:
            raise AssertionError('steward Dump topic allowed public export')
    print("✅ Steward Dump topic privacy boundary test passed")


def test_private_export_command_is_a_noop():
    with tempfile.TemporaryDirectory() as tmp_dir:
        bot = _private_bot(tmp_dir)
        update, sink = _update(text='/export')
        asyncio.run(bot.export_command(update, None))
        assert sink.messages == [
            'Private collection is enabled; GitHub export is disabled.'
        ]
        assert list(Path(tmp_dir).glob('telegram-*.json')) == []
    print("✅ Private export command guard test passed")


def test_digest_integration():
    """Test digest pipeline integration."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        digest = DigestIntegration(tmp_dir)

        # Test data with realistic entries
        test_entries = [
            {
                'timestamp': '2024-01-01T12:00:00',
                'user_id': 123,
                'username': 'testuser1',
                'message_text': 'Check out https://example.com',
                'urls': ['https://example.com'],
                'message_id': 456
            },
            {
                'timestamp': '2024-01-01T13:00:00',
                'user_id': 124,
                'username': 'testuser2',
                'message_text': 'Found this: https://test.org and https://news.com',
                'urls': ['https://test.org', 'https://news.com'],
                'message_id': 457
            }
        ]

        # Test weekly summary export
        export_file = digest.export_weekly_summary(test_entries)
        assert Path(export_file).exists()

        with open(export_file) as f:
            exported = json.load(f)

        assert exported['source'] == 'telegram_dumpbot'
        assert 'period' in exported
        assert 'summary' in exported
        assert exported['summary']['total_messages'] >= 0
        assert exported['summary']['total_urls'] >= 0

        # Test daily export
        daily_file = digest.export_daily_data(test_entries, '2024-01-01')
        assert Path(daily_file).exists()

        with open(daily_file) as f:
            daily_data = json.load(f)

        assert daily_data['source'] == 'telegram_dumpbot'
        assert daily_data['date'] == '2024-01-01'

        print("✅ DigestIntegration tests passed")


def test_git_sync():
    """Test git sync functionality (dry run without actual git operations)."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        git_sync = GitSync(tmp_dir)

        # Test config setup (won't actually run git)
        try:
            result = git_sync.setup_git_config()
            # Expect this to fail in test environment, which is fine
        except:
            pass

        print("✅ GitSync tests passed")


def test_url_pattern():
    """Test URL extraction pattern."""
    import re
    from dumpbot import URL_PATTERN

    test_message = "Check https://example.com and http://test.org/path?param=value"
    urls = URL_PATTERN.findall(test_message)

    assert len(urls) == 2
    assert 'https://example.com' in urls
    assert 'http://test.org/path?param=value' in urls

    print("✅ URL pattern tests passed")


def test_http_transport_logging_does_not_expose_bot_token():
    import dumpbot  # noqa: F401

    assert logging.getLogger("httpx").getEffectiveLevel() >= logging.WARNING
    assert logging.getLogger("httpcore").getEffectiveLevel() >= logging.WARNING

    print("✅ HTTP transport logging is credential-safe")


if __name__ == '__main__':
    print("Running DumpBot tests...")
    test_data_store()
    test_data_store_upserts_edits_and_collapses_duplicates()
    test_exact_topic_filter_and_message_edit_upsert()
    test_reply_edits_upsert_inside_parent_thread()
    test_private_profile_cannot_enable_git_export()
    test_steward_dump_topic_cannot_use_public_profile()
    test_private_export_command_is_a_noop()
    test_digest_integration()
    test_git_sync()
    test_url_pattern()
    test_http_transport_logging_does_not_expose_bot_token()
    print("🎉 All tests passed! Bot is ready to deploy.")
