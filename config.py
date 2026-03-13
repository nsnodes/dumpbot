"""Configuration management using environment variables."""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


class Config:
    """Configuration class with environment variable handling."""

    def __init__(self):
        self.bot_token = self._get_env('TELEGRAM_BOT_TOKEN')
        self.chat_id = self._get_env('CHAT_ID')
        self.data_output_dir = Path(os.getenv('DATA_OUTPUT_DIR', 'data'))

    @staticmethod
    def _get_env(key: str) -> str:
        """Get environment variable or raise error if missing."""
        value = os.getenv(key)
        if not value:
            raise ValueError(f"Missing required environment variable: {key}")
        return value