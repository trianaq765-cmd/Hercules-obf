#!/bin/bash
echo "Starting Hercules Obfuscator Services..."

mkdir -p /app/uploads /app/outputs /app/logs

# Start web server
gunicorn --bind 0.0.0.0:10000 --workers 2 --timeout 300 server:app &
WEB_PID=$!

sleep 3

# Start Discord bot
python3 bot.py &
BOT_PID=$!

echo "Web Server PID: $WEB_PID"
echo "Discord Bot PID: $BOT_PID"

trap "kill $WEB_PID $BOT_PID 2>/dev/null; exit" SIGTERM SIGINT
wait -n
kill $WEB_PID $BOT_PID 2>/dev/null
