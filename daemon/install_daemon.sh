#!/bin/bash
# 🦷💀🔥 LAZARUS DAEMON INSTALLER 🔥💀🦷
#
# Installs the LAZARUS auto-sync daemon as a macOS launchd service.
# The daemon monitors for new conversations and auto-ingests them.

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
PLIST_NAME="com.vex.lazarus.sync.plist"
PLIST_SOURCE="$SCRIPT_DIR/$PLIST_NAME"
PLIST_DEST="$HOME/Library/LaunchAgents/$PLIST_NAME"
TEMP_PLIST="$(mktemp)"

resolve_python() {
    if [ -n "${LAZARUS_PYTHON:-}" ]; then
        printf '%s\n' "$LAZARUS_PYTHON"
        return
    fi
    if [ -x "$PROJECT_ROOT/venv/bin/python" ]; then
        printf '%s\n' "$PROJECT_ROOT/venv/bin/python"
        return
    fi
    if [ -x "$PROJECT_ROOT/.venv/bin/python" ]; then
        printf '%s\n' "$PROJECT_ROOT/.venv/bin/python"
        return
    fi
    command -v python3
}

PYTHON_BIN="$(resolve_python)"
DAEMON_SCRIPT="$SCRIPT_DIR/lazarus_sync_daemon.py"
STDOUT_LOG="$SCRIPT_DIR/lazarus_daemon.stdout.log"
STDERR_LOG="$SCRIPT_DIR/lazarus_daemon.stderr.log"

cleanup() {
    rm -f "$TEMP_PLIST"
}
trap cleanup EXIT

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
python3 - "$PLIST_SOURCE" "$TEMP_PLIST" "$PYTHON_BIN" "$DAEMON_SCRIPT" "$STDOUT_LOG" "$STDERR_LOG" "$PROJECT_ROOT" <<'PY'
from pathlib import Path
import sys

source, dest, python_bin, daemon_script, stdout_log, stderr_log, project_root = sys.argv[1:8]
text = Path(source).read_text(encoding="utf-8")
replacements = {
    "__LAZARUS_PYTHON__": python_bin,
    "__LAZARUS_DAEMON_SCRIPT__": daemon_script,
    "__LAZARUS_STDOUT__": stdout_log,
    "__LAZARUS_STDERR__": stderr_log,
    "__LAZARUS_WORKDIR__": project_root,
}
for needle, value in replacements.items():
    text = text.replace(needle, value)
Path(dest).write_text(text, encoding="utf-8")
PY
cp "$TEMP_PLIST" "$PLIST_DEST"

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
