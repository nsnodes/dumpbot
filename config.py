"""Configuration management using environment variables."""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

STEWARD_DUMP_CHAT_ID = '-1003904448873'
STEWARD_DUMP_TOPIC_ID = 311


class Config:
    """Configuration class with environment variable handling."""

    def __init__(self):
        self.bot_token = self._get_env('TELEGRAM_BOT_TOKEN')
        self.chat_id = self._get_env('CHAT_ID')
        topic_id = os.getenv('TOPIC_ID', '').strip()
        self.topic_id = int(topic_id) if topic_id else None
        self.data_output_dir = Path(os.getenv('DATA_OUTPUT_DIR', 'data'))
        self.export_mode = os.getenv('EXPORT_MODE', 'public').strip().lower()
        if self.export_mode not in {'public', 'private'}:
            raise ValueError("EXPORT_MODE must be 'public' or 'private'")

        self.git_export_enabled = self._get_bool_env(
            'GIT_EXPORT_ENABLED', default=self.export_mode == 'public'
        )
        if self.export_mode == 'private' and self.git_export_enabled:
            raise ValueError(
                'GIT_EXPORT_ENABLED must be false when EXPORT_MODE=private'
            )
        if (
            self.chat_id == STEWARD_DUMP_CHAT_ID
            and self.topic_id == STEWARD_DUMP_TOPIC_ID
            and self.export_mode != 'private'
        ):
            raise ValueError(
                'The private steward Dump topic requires EXPORT_MODE=private'
            )

    @staticmethod
    def _get_env(key: str) -> str:
        """Get environment variable or raise error if missing."""
        value = os.getenv(key)
        if not value:
            raise ValueError(f"Missing required environment variable: {key}")
        return value

    @staticmethod
    def _get_bool_env(key: str, *, default: bool) -> bool:
        value = os.getenv(key)
        if value is None:
            return default
        normalized = value.strip().lower()
        if normalized in {'1', 'true', 'yes', 'on'}:
            return True
        if normalized in {'0', 'false', 'no', 'off'}:
            return False
        raise ValueError(f"{key} must be true or false")
