"""Data storage and retrieval for ingested Telegram content."""

import json
import logging
import os
import tempfile
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class DataStore:
    """Simple JSON-based data store for bot collections."""

    def __init__(self, data_dir: Path):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.entries_file = self.data_dir / "entries.jsonl"

    @staticmethod
    def entry_key(entry: dict[str, Any]) -> tuple[Any, Any, Any]:
        """Stable Telegram identity, including the source chat and forum topic."""
        return (
            entry.get("chat_id"),
            entry.get("message_thread_id"),
            entry.get("message_id"),
        )

    def upsert_entry(self, updated_entry: dict[str, Any]) -> None:
        """Insert or replace one Telegram message without retaining edit duplicates."""
        entries = self.get_all_entries()
        key = self.entry_key(updated_entry)
        matches = [
            index for index, entry in enumerate(entries) if self.entry_key(entry) == key
        ]

        if matches:
            first = matches[0]
            existing = entries[first]
            if "thread" in existing and "thread" not in updated_entry:
                updated_entry["thread"] = existing["thread"]
            entries[first] = updated_entry
            for index in reversed(matches[1:]):
                del entries[index]
        else:
            entries.append(updated_entry)

        self._write_entries(entries)

    def _write_entries(self, entries: list[dict[str, Any]]) -> None:
        """Atomically replace the JSONL store."""
        self.data_dir.mkdir(parents=True, exist_ok=True)
        temp_path = None
        try:
            with tempfile.NamedTemporaryFile(
                "w", encoding="utf-8", dir=self.data_dir, delete=False
            ) as output:
                temp_path = Path(output.name)
                for entry in entries:
                    output.write(json.dumps(entry, ensure_ascii=False) + "\n")
                output.flush()
                os.fsync(output.fileno())
            os.replace(temp_path, self.entries_file)
        except Exception as exc:
            logger.error(f"Failed to rewrite entries: {exc}")
            if temp_path is not None:
                temp_path.unlink(missing_ok=True)
            raise

    def update_entry(self, updated_entry: dict[str, Any]) -> None:
        """Update an existing entry by message_id."""
        self.upsert_entry(updated_entry)
        logger.info(f"Updated entry with message_id: {updated_entry.get('message_id')}")

    def get_all_entries(self) -> list[dict[str, Any]]:
        """Retrieve all stored entries."""
        if not self.entries_file.exists():
            return []

        entries = []
        try:
            with open(self.entries_file, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        entries.append(json.loads(line))
        except (OSError, json.JSONDecodeError) as exc:
            logger.error(f"Failed to read entries: {exc}")

        return entries

    def get_stats(self) -> dict[str, Any]:
        """Get statistics about the collected data."""
        entries = self.get_all_entries()

        total_urls = sum(len(entry.get("urls", [])) for entry in entries)
        content_types = {}
        for entry in entries:
            content_type = entry.get("content_type", "unknown")
            content_types[content_type] = content_types.get(content_type, 0) + 1

        last_updated = "Never"
        if entries:
            last_entry = max(entries, key=lambda x: x.get("timestamp", ""))
            last_updated = last_entry.get("timestamp", "Unknown")

        return {
            "total_entries": len(entries),
            "total_urls": total_urls,
            "content_types": content_types,
            "last_updated": last_updated,
        }
