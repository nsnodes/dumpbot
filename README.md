# DumpBot

A Telegram bot that collects links and comments from group chats to feed into the nsnodes digest pipeline.

## Features

- Automatic link detection and collection from Telegram messages
- JSON-based data persistence
- Export functionality for digest pipeline integration
- Simple command interface (`/start`, `/stats`, `/export`)
- Systemd service for production deployment

## Setup

### 1. Create Telegram Bot

1. **Create bot with @BotFather:**
   - Message @BotFather on Telegram
   - Use `/newbot` and follow prompts
   - Save the bot token

2. **Add bot to group:**
   - Create/use existing Telegram group
   - Add your bot to the group
   - Get the chat ID (use @userinfobot or check bot logs)

### 2. Install and Configure

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

### 3. Production Deployment

The bot should run on the nsnodes VPS with daily auto-export:

```bash
# Add to crontab for daily export at 23:00 UTC
0 23 * * * /home/ubuntu/dumpbot/cron-daily-export.sh
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

## Digest Pipeline Integration

The bot integrates with the nsnodes digest pipeline:

1. **VPS Operation**: Bot runs on nsnodes VPS, collects telegram data
2. **Auto-Commit**: `/export` command creates `data/telegram-YYYY-MM-DD.json` and commits/pushes to GitHub
3. **Digest Fetch**: GitHub Actions `fetch-weekly-data.sh` pulls committed data from dumpbot repo
4. **Pipeline Processing**: Data flows into weekly digest generation

The VPS commits data to GitHub, then digest workflow pulls it for processing.

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