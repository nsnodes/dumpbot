# DumpBot

A Telegram bot that collects links and comments from group chats to feed into the nsnodes digest pipeline.

## Features

- Automatic link detection and collection from Telegram messages
- **@claude directives** - Send instructions to the digest with `@claude [instruction]`
- **Reply thread tracking** - Replies to link messages are captured as conversation threads
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

Initial deployment to nsnodes VPS:

```bash
# First time setup
ssh nsnodes
git clone https://github.com/nsnodes/dumpbot.git ~/dumpbot
cd ~/dumpbot
uv sync
cp .env.example .env
# Edit .env with bot token and chat ID

# Set up systemd service
sudo cp systemd/dumpbot.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable dumpbot
sudo systemctl start dumpbot

# Add daily export cron
crontab -e
# Add: 0 23 * * * /home/ubuntu/dumpbot/cron-daily-export.sh
```

Subsequent updates use `./deploy.sh` which pulls latest changes.

## Configuration

Set these environment variables in `.env`:

- `TELEGRAM_BOT_TOKEN` - Your bot token from @BotFather
- `CHAT_ID` - The chat ID where the bot will collect links
- `TOPIC_ID` - Optional forum topic ID; when set, all other topics are ignored
- `DATA_OUTPUT_DIR` - Directory for data storage (default: `data`)
- `EXPORT_MODE` - `public` for the legacy feed or `private` for a local-only feed
- `GIT_EXPORT_ENABLED` - Whether `/export` and the daily job may push data

## Steward Dump topic cutover

The replacement destination is [Dump](https://t.me/c/3904448873/311): chat
`-1003904448873`, topic `311`. `.env.dump-topic.example` is the production
profile template for that destination.

The cutover profile has deliberately different privacy semantics from the
legacy DumpBot chat:

- the chat and topic IDs must both match; no other steward topic is collected;
- raw entries are written beneath `/var/lib/dump-collector`, outside this
  public checkout;
- Git export is disabled, and configuration validation refuses to start if the
  steward Dump topic is configured as public;
- edits are upserts keyed by `(chat_id, topic_id, message_id)`, including reply
  edits, so Telegram edits do not become duplicate feed items.

Do not use the steward bot token for this collector: Telegram permits only one
`getUpdates` poller per token. Add the existing DumpBot bot to the steward forum
and disable BotFather privacy mode so it can see ordinary Dump-topic messages.

### Cutover order

1. Deploy this release to the legacy collector without changing `.env` and
   confirm the old public feed still exports.
2. Add the DumpBot bot to the steward forum, then stage the private profile and
   `/var/lib/dump-collector` with mode `0700`.
3. Stop the old-profile service, start the private profile, post and then edit a
   disposable URL in topic `311`, and verify there is exactly one updated row
   in the private `entries.jsonl`. Messages in another topic must add no row.
4. On the AudioSync host set
   `DUMP_FEED_FILE=/var/lib/dump-collector/entries.jsonl`; it will then read the
   private file directly and never fall back to GitHub.
5. Keep the historical public exports for existing consumers. Do not remove the
   legacy service or repository until Digest has a private authenticated input
   path and the private collector has completed a full weekly cycle.

Digest currently runs in GitHub Actions and reads the public repository. The
private Dump topic must not be wired into that job until a private authenticated
handoff exists; this repository intentionally does not weaken that boundary.

## Commands

- `/start` - Initialize bot in chat
- `/stats` - Show collection statistics
- `/export` - Export data to digest pipeline

## Data Format

Collected data is stored as JSONL with different entry types:

### Link Entries
- `type: 'link'`
- `timestamp` - ISO format timestamp
- `user_id` - Telegram user ID
- `username` - Telegram username
- `message_text` - Full message content
- `urls` - Array of extracted URLs
- `message_id` - Telegram message ID
- `thread` - Array of replies to this link message

### Directive Entries
- `type: 'directive'`
- `timestamp` - ISO format timestamp
- `user_id` - Telegram user ID
- `username` - Telegram username
- `instruction` - The directive text (without @claude prefix)
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
