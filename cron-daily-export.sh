#!/bin/bash
# Daily Export Cron Wrapper
# Similar to x-sync's grok-cron.sh pattern

set -e

# Handle directory paths for VPS deployment
if [ -d "/home/ubuntu/dumpbot" ]; then
    PROJECT_ROOT="/home/ubuntu/dumpbot"
else
    # Fallback to script-relative path for local development
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    PROJECT_ROOT="$SCRIPT_DIR"
fi

# Log file for debugging
LOG_FILE="$PROJECT_ROOT/data/daily-export.log"
mkdir -p "$(dirname "$LOG_FILE")"

# Redirect all output to log file
exec >> "$LOG_FILE" 2>&1

# Set up PATH for cron environment
export PATH="$HOME/.local/bin:/usr/local/bin:/usr/bin:/bin:$PATH"

cd "$PROJECT_ROOT"

echo "Running daily telegram export at $(date)"
echo "Project root: $PROJECT_ROOT"

# Run daily export
uv run python daily_export.py

echo "Daily export completed at $(date)"