"""Data storage and retrieval for collected links and metadata."""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List

logger = logging.getLogger(__name__)


class DataStore:
    """Simple JSON-based data store for bot collections."""

    def __init__(self, data_dir: Path):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)
        self.entries_file = self.data_dir / 'entries.jsonl'

    def save_entry(self, entry: Dict[str, Any]) -> None:
        """Save a single entry to the data store."""
        try:
            with open(self.entries_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(entry, ensure_ascii=False) + '\n')
        except Exception as e:
            logger.error(f"Failed to save entry: {e}")

    def update_entry(self, updated_entry: Dict[str, Any]) -> None:
        """Update an existing entry by message_id."""
        if not self.entries_file.exists():
            return

        entries = []
        try:
            # Read all entries
            with open(self.entries_file, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.strip():
                        entries.append(json.loads(line))

            # Find and update the entry
            updated = False
            for i, entry in enumerate(entries):
                if entry.get('message_id') == updated_entry.get('message_id'):
                    entries[i] = updated_entry
                    updated = True
                    break

            if updated:
                # Rewrite the entire file
                with open(self.entries_file, 'w', encoding='utf-8') as f:
                    for entry in entries:
                        f.write(json.dumps(entry, ensure_ascii=False) + '\n')
                logger.info(f"Updated entry with message_id: {updated_entry.get('message_id')}")
            else:
                logger.warning(f"Entry with message_id {updated_entry.get('message_id')} not found")

        except Exception as e:
            logger.error(f"Failed to update entry: {e}")

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