"""Git synchronization utilities for committing and pushing telegram data."""

import logging
import subprocess
from datetime import datetime
from pathlib import Path
from typing import List

logger = logging.getLogger(__name__)


class GitSync:
    """Handles git operations for syncing telegram data to repository."""

    def __init__(self, repo_path: str = '.'):
        self.repo_path = Path(repo_path)

    def commit_daily_data(self, data_files: List[str], date: str = None) -> bool:
        """Commit daily telegram data files and push to origin."""
        if date is None:
            date = datetime.now().strftime('%Y-%m-%d')

        try:
            # Change to repo directory
            original_cwd = Path.cwd()
            import os
            os.chdir(self.repo_path)

            # Add the data files
            for file_path in data_files:
                result = subprocess.run(['git', 'add', '-f', file_path],
                                      capture_output=True, text=True)
                if result.returncode != 0:
                    logger.error(f"Failed to add {file_path}: {result.stderr}")
                    return False

            # Check if there are changes to commit
            result = subprocess.run(['git', 'status', '--porcelain'],
                                  capture_output=True, text=True)

            if not result.stdout.strip():
                logger.info("No changes to commit")
                return True

            # Commit the changes
            commit_message = f"Add telegram data {date}"
            result = subprocess.run(['git', 'commit', '-m', commit_message],
                                  capture_output=True, text=True)

            if result.returncode != 0:
                logger.error(f"Commit failed: {result.stderr}")
                return False

            logger.info(f"Committed telegram data for {date}")

            # Push to origin
            result = subprocess.run(['git', 'push', 'origin', 'main'],
                                  capture_output=True, text=True)

            if result.returncode != 0:
                logger.error(f"Push failed: {result.stderr}")
                return False

            logger.info("Successfully pushed to origin")
            return True

        except Exception as e:
            logger.error(f"Git sync failed: {e}")
            return False
        finally:
            # Restore original working directory
            os.chdir(original_cwd)

    def setup_git_config(self):
        """Set up git config for automated commits on VPS."""
        try:
            import os
            os.chdir(self.repo_path)

            # Set up git user for commits
            subprocess.run(['git', 'config', 'user.name', 'DumpBot'],
                          capture_output=True)
            subprocess.run(['git', 'config', 'user.email', 'dumpbot@nsnodes.com'],
                          capture_output=True)

            logger.info("Git config set up for automated commits")
            return True
        except Exception as e:
            logger.error(f"Failed to set up git config: {e}")
            return False