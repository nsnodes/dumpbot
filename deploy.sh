#!/bin/bash
set -e

echo "🚀 Deploying DumpBot to production..."

# Deploy via git clone/pull on remote server
ssh nsnodes << 'EOF'
if [ ! -d ~/dumpbot ]; then
    echo "Cloning repository..."
    git clone https://github.com/nsnodes/dumpbot.git ~/dumpbot
else
    echo "Pulling latest changes..."
    cd ~/dumpbot
    git pull origin main
fi

cd ~/dumpbot
echo "Installing dependencies with uv..."
uv sync

echo "Restarting bot service..."
sudo systemctl restart dumpbot || echo "Service not yet configured"

echo "✅ Deployment complete!"
EOF

echo "📊 Deployment finished. Check bot status with: ssh nsnodes 'systemctl status dumpbot'"