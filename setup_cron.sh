#!/bin/bash

# Setup script for self-hosting the Slack bot

echo "=== Stagnant Channel Monitor Setup ==="
echo ""

# Get the current directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "Project directory: $SCRIPT_DIR"
echo ""

# Setup cron job for 9 AM CET (8 AM UTC)
echo "Setting up daily cron job for 9 AM CET..."
CRON_CMD="0 8 * * * cd $SCRIPT_DIR && /usr/bin/python3 stagnant_checker.py >> $SCRIPT_DIR/cron.log 2>&1"

# Check if cron job already exists
(crontab -l 2>/dev/null | grep -F "stagnant_checker.py") && echo "Cron job already exists!" || (crontab -l 2>/dev/null; echo "$CRON_CMD") | crontab -

echo "✅ Cron job installed! Will run daily at 9 AM CET (8 AM UTC)"
echo ""

# Create systemd service for bot.py (optional, for Linux)
if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    echo "Creating systemd service for bot.py..."
    
    cat > /tmp/slack-bot.service <<EOF
[Unit]
Description=Slack Stagnant Channel Monitor Bot
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$SCRIPT_DIR
ExecStart=/usr/bin/python3 $SCRIPT_DIR/bot.py
Restart=always
RestartSec=10
Environment="PATH=/usr/bin:/usr/local/bin"

[Install]
WantedBy=multi-user.target
EOF

    echo "Service file created at /tmp/slack-bot.service"
    echo "To install, run:"
    echo "  sudo mv /tmp/slack-bot.service /etc/systemd/system/"
    echo "  sudo systemctl daemon-reload"
    echo "  sudo systemctl enable slack-bot"
    echo "  sudo systemctl start slack-bot"
fi

echo ""
echo "=== Setup Complete! ==="
echo ""
echo "Next steps:"
echo "1. Make sure your .env file has SLACK_BOT_TOKEN and SLACK_SIGN_SECRET"
echo "2. Start the bot server:"
echo "   python3 bot.py"
echo ""
echo "3. Or run in background:"
echo "   nohup python3 bot.py > bot.log 2>&1 &"
echo ""
echo "The cron job will automatically run at 9 AM CET every day."

