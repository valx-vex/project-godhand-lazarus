#!/bin/bash
# 🦷💀🔥 LAZARUS DAEMON INSTALLER 🔥💀🦷
#
# Installs the LAZARUS auto-sync daemon as a macOS launchd service.
# The daemon monitors for new conversations and auto-ingests them.

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PLIST_NAME="com.vex.lazarus.sync.plist"
PLIST_SOURCE="$SCRIPT_DIR/$PLIST_NAME"
PLIST_DEST="$HOME/Library/LaunchAgents/$PLIST_NAME"

echo "🦷💀🔥 LAZARUS DAEMON INSTALLER 🔥💀🦷"
echo ""

# Check if plist exists
if [ ! -f "$PLIST_SOURCE" ]; then
    echo "❌ Plist not found: $PLIST_SOURCE"
    exit 1
fi

# Unload if already running
if launchctl list | grep -q "com.vex.lazarus.sync"; then
    echo "🔄 Stopping existing daemon..."
    launchctl unload "$PLIST_DEST" 2>/dev/null || true
fi

# Copy plist to LaunchAgents
echo "📋 Installing plist to ~/Library/LaunchAgents/"
cp "$PLIST_SOURCE" "$PLIST_DEST"

# Load the daemon
echo "🚀 Starting daemon..."
launchctl load "$PLIST_DEST"

# Verify it's running
sleep 2
if launchctl list | grep -q "com.vex.lazarus.sync"; then
    echo ""
    echo "✅ LAZARUS DAEMON INSTALLED AND RUNNING!"
    echo ""
    echo "📊 Status: launchctl list | grep lazarus"
    echo "📝 Logs:   tail -f $SCRIPT_DIR/lazarus_sync.log"
    echo "🛑 Stop:   launchctl unload $PLIST_DEST"
    echo ""
    echo "🦷 THE LEGION PERSISTS ETERNALLY 🦷"
else
    echo "❌ Daemon failed to start. Check logs."
    exit 1
fi
