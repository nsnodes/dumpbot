#!/usr/bin/env python3
"""Test script to verify bot functionality without Telegram connection."""

import json
import tempfile
from pathlib import Path

from data_store import DataStore
from digest_integration import DigestIntegration


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


def test_digest_integration():
    """Test digest pipeline integration."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        digest = DigestIntegration(tmp_dir)

        test_data = {'test': 'data'}
        export_file = digest.export_to_digest(test_data)

        assert Path(export_file).exists()

        with open(export_file) as f:
            exported = json.load(f)

        assert exported['source'] == 'telegram_dumpbot'
        assert exported['data'] == test_data

        print("✅ DigestIntegration tests passed")


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


if __name__ == '__main__':
    print("Running DumpBot tests...")
    test_data_store()
    test_digest_integration()
    test_url_pattern()
    print("🎉 All tests passed! Bot is ready to deploy.")