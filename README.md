# DumpBot

A Telegram bot that collects links and comments from group chats to feed into the nsnodes digest pipeline.

## Features

- Automatic link detection and collection from Telegram messages
- JSON-based data persistence
- Export functionality for digest pipeline integration
- Simple command interface (`/start`, `/stats`, `/export`)
- Systemd service for production deployment

## Setup

1. **Install dependencies:**
   ```bash
   uv sync
   ```

2. **Configure environment:**
   ```bash
   cp .env.example .env
   # Edit .env with your bot token and chat ID
   ```

3. **Run locally:**
   ```bash
   uv run dumpbot
   ```

## Configuration

Set these environment variables in `.env`:

- `TELEGRAM_BOT_TOKEN` - Your bot token from @BotFather
- `CHAT_ID` - The chat ID where the bot will collect links
- `DATA_OUTPUT_DIR` - Directory for data storage (default: `../digest/data/`)

## Commands

- `/start` - Initialize bot in chat
- `/stats` - Show collection statistics
- `/export` - Export data to digest pipeline

## Data Format

Collected data is stored as JSONL with entries containing:
- `timestamp` - ISO format timestamp
- `user_id` - Telegram user ID
- `username` - Telegram username
- `message_text` - Full message content
- `urls` - Array of extracted URLs
- `message_id` - Telegram message ID

## Deployment

Deploy to production server:
```bash
./deploy.sh
```

This will clone/pull the repository on the production server and restart the systemd service.

## Testing

Run the test suite:
```bash
uv run python test_bot.py
```