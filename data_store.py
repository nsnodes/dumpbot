"""Data storage and retrieval for collected links and metadata."""

import json
import logging
import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List

logger = logging.getLogger(__name__)


class DataStore:
    """Simple JSON-based data store for bot collections."""

    def __init__(self, data_dir: Path):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.entries_file = self.data_dir / 'entries.jsonl'

    def save_entry(self, entry: Dict[str, Any]) -> None:
        """Save a single entry to the data store."""
        try:
            with open(self.entries_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(entry, ensure_ascii=False) + '\n')
        except Exception as e:
            logger.error(f"Failed to save entry: {e}")

    @staticmethod
    def entry_key(entry: Dict[str, Any]) -> tuple[Any, Any, Any]:
        """Stable Telegram identity, including the source chat and forum topic."""
        return (
            entry.get('chat_id'),
            entry.get('message_thread_id'),
            entry.get('message_id'),
        )

    def upsert_entry(self, updated_entry: Dict[str, Any]) -> None:
        """Insert or replace one Telegram message without retaining edit duplicates."""
        entries = self.get_all_entries()
        key = self.entry_key(updated_entry)
        matches = [index for index, entry in enumerate(entries) if self.entry_key(entry) == key]

        # Entries written before source scoping did not include chat/topic. This
        # collector historically had one configured chat, so adopt every legacy
        # version with the same message id and collapse old edit duplicates.
        if not matches:
            legacy_matches = [
                index for index, entry in enumerate(entries)
                if entry.get('message_id') == updated_entry.get('message_id')
                and entry.get('chat_id') is None
                and entry.get('message_thread_id') is None
            ]
            if legacy_matches:
                matches = legacy_matches

        if matches:
            first = matches[0]
            existing = entries[first]
            if 'thread' in existing and 'thread' not in updated_entry:
                updated_entry['thread'] = existing['thread']
            entries[first] = updated_entry
            for index in reversed(matches[1:]):
                del entries[index]
        else:
            entries.append(updated_entry)

        self._write_entries(entries)

    def delete_entry(self, identity: Dict[str, Any]) -> None:
        """Remove all stored versions of one Telegram message."""
        key = self.entry_key(identity)
        message_id = identity.get('message_id')
        entries = [
            entry for entry in self.get_all_entries()
            if self.entry_key(entry) != key
            and not (
                entry.get('message_id') == message_id
                and entry.get('chat_id') is None
                and entry.get('message_thread_id') is None
            )
        ]
        self._write_entries(entries)

    def _write_entries(self, entries: List[Dict[str, Any]]) -> None:
        """Atomically replace the JSONL store."""
        self.data_dir.mkdir(parents=True, exist_ok=True)
        temp_path = None
        try:
            with tempfile.NamedTemporaryFile(
                'w', encoding='utf-8', dir=self.data_dir, delete=False
            ) as output:
                temp_path = Path(output.name)
                for entry in entries:
                    output.write(json.dumps(entry, ensure_ascii=False) + '\n')
                output.flush()
                os.fsync(output.fileno())
            os.replace(temp_path, self.entries_file)
        except Exception as exc:
            logger.error(f"Failed to rewrite entries: {exc}")
            if temp_path is not None:
                temp_path.unlink(missing_ok=True)
            raise

    def update_entry(self, updated_entry: Dict[str, Any]) -> None:
        """Update an existing entry by message_id."""
        self.upsert_entry(updated_entry)
        logger.info(f"Updated entry with message_id: {updated_entry.get('message_id')}")

    def get_all_entries(self) -> List[Dict[str, Any]]:
        """Retrieve all stored entries."""
        if not self.entries_file.exists():
            return []

        entries = []
        try:
            with open(self.entries_file, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.strip():
                        entries.append(json.loads(line))
        except Exception as e:
            logger.error(f"Failed to read entries: {e}")

        return entries

    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about the collected data."""
        entries = self.get_all_entries()

        # Count different entry types
        link_entries = [e for e in entries if e.get('type') == 'link']
        directive_entries = [e for e in entries if e.get('type') == 'directive']
        # Legacy entries without type field are assumed to be links
        legacy_entries = [e for e in entries if 'type' not in e and 'urls' in e]

        total_urls = sum(len(entry.get('urls', [])) for entry in link_entries + legacy_entries)
        total_directives = len(directive_entries)

        last_updated = 'Never'
        if entries:
            last_entry = max(entries, key=lambda x: x.get('timestamp', ''))
            last_updated = last_entry.get('timestamp', 'Unknown')

        return {
            'total_entries': len(entries),
            'total_urls': total_urls,
            'total_directives': total_directives,
            'last_updated': last_updated
        }

    def export_for_digest(self) -> str:
        """Export data in format suitable for digest pipeline."""
        entries = self.get_all_entries()

        digest_data = {
            'source': 'telegram_dumpbot',
            'exported_at': datetime.now().isoformat(),
            'entries': entries
        }

        output_file = self.data_dir / f'digest_export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'

        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(digest_data, f, ensure_ascii=False, indent=2)

            logger.info(f"Exported {len(entries)} entries to {output_file}")
            return str(output_file)
        except Exception as e:
            logger.error(f"Failed to export data: {e}")
            raise
