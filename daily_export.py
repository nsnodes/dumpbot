#!/usr/bin/env python3
"""Daily export script for automatic telegram data commits."""

import logging
import sys
from datetime import datetime

from config import Config
from data_store import DataStore
from digest_integration import DigestIntegration
from git_sync import GitSync

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def daily_export():
    """Export and commit today's telegram data."""
    try:
        # Initialize components
        config = Config()
        data_store = DataStore(config.data_output_dir)
        digest = DigestIntegration()
        git_sync = GitSync()

        # Get today's date
        today = datetime.now().strftime('%Y-%m-%d')

        # Get all entries and export today's data
        all_entries = data_store.get_all_entries()
        if not all_entries:
            logger.info("No telegram data to export")
            return True

        # Export today's data
        export_file = digest.export_daily_data(all_entries, today)
        logger.info(f"Exported telegram data to {export_file}")

        # Commit and push
        commit_success = git_sync.commit_daily_data([export_file], today)

        if commit_success:
            logger.info(f"Successfully committed and pushed telegram data for {today}")
        else:
            logger.error(f"Failed to commit telegram data for {today}")
            return False

        return True

    except Exception as e:
        logger.error(f"Daily export failed: {e}")
        return False


if __name__ == '__main__':
    success = daily_export()
    sys.exit(0 if success else 1)