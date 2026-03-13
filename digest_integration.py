"""Integration utilities for the nsnodes digest pipeline."""

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List

logger = logging.getLogger(__name__)


class DigestIntegration:
    """Handles integration with the nsnodes digest pipeline."""

    def __init__(self, data_dir: str = 'data'):
        # Store data locally in the dumpbot repo, not in digest repo
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)

    def export_daily_data(self, entries: List[Dict[str, Any]], target_date: str = None) -> str:
        """Export collected data for a specific date in digest pipeline format."""
        if target_date is None:
            target_date = datetime.now().strftime('%Y-%m-%d')

        output_file = self.data_dir / f'telegram-{target_date}.json'

        # Filter entries for the target date
        target_datetime = datetime.strptime(target_date, '%Y-%m-%d')
        next_day = target_datetime + timedelta(days=1)

        filtered_entries = []
        for entry in entries:
            entry_date = datetime.fromisoformat(entry['timestamp'].replace('Z', '+00:00'))
            if target_datetime <= entry_date < next_day:
                filtered_entries.append(entry)

        # Format data to match digest pipeline expectations
        digest_data = {
            'source': 'telegram_dumpbot',
            'date': target_date,
            'collected_at': datetime.now().isoformat(),
            'total_messages': len(filtered_entries),
            'total_urls': sum(len(entry.get('urls', [])) for entry in filtered_entries),
            'entries': filtered_entries
        }

        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(digest_data, f, ensure_ascii=False, indent=2)

            logger.info(f"Exported {len(filtered_entries)} entries to {output_file}")
            return str(output_file)
        except Exception as e:
            logger.error(f"Failed to export daily data: {e}")
            raise

    def export_weekly_summary(self, entries: List[Dict[str, Any]], days: int = 7) -> str:
        """Export last N days of data for weekly digest."""
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)

        # Filter entries for the date range
        filtered_entries = []
        for entry in entries:
            entry_date = datetime.fromisoformat(entry['timestamp'].replace('Z', '+00:00'))
            if start_date <= entry_date <= end_date:
                filtered_entries.append(entry)

        # Sort by timestamp and group by domain for better analysis
        filtered_entries.sort(key=lambda x: x['timestamp'])

        domain_stats = {}
        for entry in filtered_entries:
            for url in entry.get('urls', []):
                try:
                    from urllib.parse import urlparse
                    domain = urlparse(url).netloc
                    if domain:
                        domain_stats[domain] = domain_stats.get(domain, 0) + 1
                except:
                    continue

        weekly_data = {
            'source': 'telegram_dumpbot',
            'period': {
                'start_date': start_date.strftime('%Y-%m-%d'),
                'end_date': end_date.strftime('%Y-%m-%d'),
                'days': days
            },
            'summary': {
                'total_messages': len(filtered_entries),
                'total_urls': sum(len(entry.get('urls', [])) for entry in filtered_entries),
                'unique_users': len(set(entry['username'] for entry in filtered_entries)),
                'top_domains': sorted(domain_stats.items(), key=lambda x: x[1], reverse=True)[:10]
            },
            'entries': filtered_entries
        }

        today = datetime.now().strftime('%Y-%m-%d')
        output_file = self.data_dir / f'telegram-{today}.json'

        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(weekly_data, f, ensure_ascii=False, indent=2)

            logger.info(f"Exported weekly summary with {len(filtered_entries)} entries to {output_file}")
            return str(output_file)
        except Exception as e:
            logger.error(f"Failed to export weekly summary: {e}")
            raise

    def validate_data_dir(self) -> bool:
        """Check if data directory is accessible."""
        return self.data_dir.exists() and self.data_dir.is_dir()