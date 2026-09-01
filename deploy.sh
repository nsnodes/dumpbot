#!/bin/bash
set -euo pipefail

echo "🚀 Deploying DumpBot to production..."

ssh nsnodes << 'EOF'
set -euo pipefail
cd /root/dumpbot
git pull --ff-only origin main
echo "Installing dependencies with uv..."
uv sync
uv run python test_bot.py
echo "Restarting bot service..."
systemctl restart dumpbot.service
systemctl is-active dumpbot.service
echo "✅ Deployment complete!"
EOF

echo "📊 Deployment finished. Check bot status with: ssh nsnodes 'systemctl status dumpbot'"
