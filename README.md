# DumpBot

DumpBot is a deliberately small Telegram forum-topic collector. One bot token
polls one configured supergroup topic and writes a private local JSONL event
stream for downstream consumers.

It is a content-ingestion adapter, not a conversational agent.

## Behaviour

- accepts content only from the exact configured `(chat_id, topic_id)` pair;
- records text, photos, documents, audio, voice notes, video, animations,
  video notes, stickers, locations, contacts, and polls using one neutral schema;
- extracts URLs from text and captions without giving them routing semantics;
- captures replies to collected messages as threads;
- atomically upserts Telegram edits by `(chat_id, topic_id, message_id)`;
- writes only to the configured absolute local directory;
- exposes `/start` and `/stats` for collector health.

Every stored item has `type: "message"` plus a `content_type`. Telegram media
is represented by its durable file identifiers and native metadata. Text is
stored verbatim and is never interpreted as an instruction.

Telegram cannot subscribe a bot to only one forum topic. The bot must have
privacy mode disabled to receive ordinary messages, and DumpBot enforces the
topic boundary after receipt. Use a dedicated token: two `getUpdates` pollers
on one token steal updates from each other.

## Configuration

Copy `.env.example` to `.env` and set:

- `TELEGRAM_BOT_TOKEN` — the dedicated collector bot token;
- `CHAT_ID` — the target Telegram supergroup ID;
- `TOPIC_ID` — the target forum topic ID;
- `DATA_OUTPUT_DIR` — an absolute private directory for `entries.jsonl`.

## Development

```bash
uv sync
uv run python test_bot.py
```

Run locally with `uv run dumpbot`.

## Production

The NSNodes deployment uses:

```dotenv
CHAT_ID=-1003904448873
TOPIC_ID=311
DATA_OUTPUT_DIR=/var/lib/dump-collector
```

`/var/lib/dump-collector` is mode `0700`. AudioSync reads
`/var/lib/dump-collector/entries.jsonl` directly; no consumer falls back to the
old public repository feed.

The Steward harness declares topic 311 passive so it acknowledges Telegram
updates there without starting a provider turn. That is a temporary single-bot
route: the hardened upstream harness is expected to own multiple bot identities
and harness-level bot/topic routing.

Deploy with `./deploy.sh`, or install `systemd/dumpbot.service` and restart the
service after a fast-forward pull.
