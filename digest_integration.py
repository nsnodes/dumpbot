"""Integration utilities for the nsnodes digest pipeline."""

import json
import logging
from pathlib import Path
from typing import Dict, Any

logger = logging.getLogger(__name__)


class DigestIntegration:
    """Handles integration with the nsnodes digest pipeline."""

    def __init__(self, digest_dir: str = '../digest/data/'):
        self.digest_dir = Path(digest_dir)
        self.digest_dir.mkdir(parents=True, exist_ok=True)

    def export_to_digest(self, data: Dict[str, Any]) -> str:
        """Export collected data to digest pipeline format."""
        output_file = self.digest_dir / 'telegram_links.json'

        digest_format = {
            'source': 'telegram_dumpbot',
            'type': 'link_collection',
            'data': data,
            'metadata': {
                'format_version': '1.0',
                'collection_method': 'telegram_bot'
            }
        }

        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(digest_format, f, ensure_ascii=False, indent=2)

            logger.info(f"Exported data to digest pipeline: {output_file}")
            return str(output_file)
        except Exception as e:
            logger.error(f"Failed to export to digest: {e}")
            raise

    def validate_digest_connection(self) -> bool:
        """Check if digest directory is accessible."""
        return self.digest_dir.exists() and self.digest_dir.is_dir()