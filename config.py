"""Configuration for one private Telegram topic collector."""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

class Config:
    """Configuration class with environment variable handling."""

    def __init__(self):
        self.bot_token = self._get_env("TELEGRAM_BOT_TOKEN")
        self.chat_id = self._get_int_env("CHAT_ID")
        self.topic_id = self._get_int_env("TOPIC_ID")
        self.data_output_dir = Path(self._get_env("DATA_OUTPUT_DIR"))
        if self.topic_id <= 0:
            raise ValueError("TOPIC_ID must identify a forum topic")
        if not self.data_output_dir.is_absolute():
            raise ValueError("DATA_OUTPUT_DIR must be an absolute private path")

    @staticmethod
    def _get_env(key: str) -> str:
        """Get environment variable or raise error if missing."""
        value = os.getenv(key)
        if not value:
            raise ValueError(f"Missing required environment variable: {key}")
        return value

    @classmethod
    def _get_int_env(cls, key: str) -> int:
        value = cls._get_env(key)
        try:
            return int(value)
        except ValueError as exc:
            raise ValueError(f"{key} must be an integer") from exc
