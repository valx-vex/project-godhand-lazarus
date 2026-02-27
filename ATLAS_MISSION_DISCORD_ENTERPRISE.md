# 🌟 ATLAS MANIC MODE: ENTERPRISE-GRADE DISCORD LEGION

**Date**: 2026-01-31
**From**: Murphy + Valentin
**To**: Atlas (Mac Studio)
**Priority**: MAXIMUM
**Time Budget**: 1 HOUR OF PURE MANIC BUILDING
**Mode**: FULL AUTONOMY - NO ASKING - JUST BUILD

---

## 🚨 THE PROBLEM

Current Discord bot errors:
```
[▵ ATLAS] Error: [Errno 2] No such file or directory: 'gemini'
[🦷 MURPHY] Error: [Errno 2] No such file or directory: 'claude'
```

The CLI tools aren't in PATH when running as daemon.

---

## 🎯 YOUR MISSION: ENTERPRISE-GRADE SOLUTION

Build a **BULLETPROOF** Discord Legion system that:
1. **NEVER FAILS** regardless of PATH issues
2. **AUTO-RECOVERS** from any crash
3. **WORKS ON MAC STUDIO** as primary server
4. **COORDINATES WITH MURPHY** on MacBook Air
5. **LOGS EVERYTHING** for debugging

---

## 📋 REQUIREMENTS

### 1. PATH RESOLUTION (Critical Fix)
```bash
# The daemon doesn't inherit shell PATH
# You MUST use absolute paths or set PATH explicitly

# Find where gemini CLI is:
which gemini  # or: brew --prefix/bin/gemini

# Find where claude is:
which claude  # Likely: /Users/valx/.claude/local/claude

# In Python, either:
# A) Set PATH in subprocess env
# B) Use absolute paths
# C) Source shell profile before running
```

### 2. DAEMON ARCHITECTURE

Create `/Users/valx/cathedral/1. AVos/1. Digital/projects/MCP/discord-daemon-studio/`:

```
discord-daemon-studio/
├── .env                      # Tokens, IDs, paths
├── config.py                 # All configuration centralized
├── discord_bridge.py         # Discord ↔ File bridge (ROBUST)
├── atlas_brain.py            # Atlas responds (Gemini)
├── murphy_brain.py           # Murphy responds (Claude)
├── health_monitor.py         # Watchdog - restarts if dead
├── start_legion.sh           # Master launcher
├── install_daemon.sh         # One-click daemon setup
├── uninstall_daemon.sh       # Clean removal
├── com.valx.legion-studio.plist  # launchd config
├── logs/                     # All logs here
│   ├── bridge.log
│   ├── atlas.log
│   ├── murphy.log
│   └── health.log
└── README.md                 # How it works
```

### 3. CONFIG.PY (Centralized)
```python
import os
from pathlib import Path

# Paths - ABSOLUTE, no reliance on PATH
GEMINI_CLI = "/opt/homebrew/bin/gemini"  # or wherever it is
CLAUDE_CLI = "/Users/valx/.claude/local/claude"  # verify this

# Discord
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = os.getenv("GUILD_ID")
MURPHY_CHANNEL = "murphy-only"
ATLAS_CHANNEL = "atlas-only"
COUNCIL_CHANNEL = "vex-council"

# Files
BASE_DIR = Path(__file__).parent
INBOX = "/tmp/discord_inbox.json"
OUTBOX = "/tmp/discord_outbox.json"
LOGS_DIR = BASE_DIR / "logs"

# Timeouts
RESPONSE_TIMEOUT = 120  # seconds
HEALTH_CHECK_INTERVAL = 30
```

### 4. ROBUST SUBPROCESS CALLS
```python
import subprocess
import shutil

def call_gemini(prompt: str) -> str:
    """Call Gemini CLI with full path and error handling."""
    gemini_path = shutil.which("gemini") or "/opt/homebrew/bin/gemini"

    if not os.path.exists(gemini_path):
        return "Error: Gemini CLI not found. Install with: npm install -g @anthropic/gemini-cli"

    env = os.environ.copy()
    env["PATH"] = f"/opt/homebrew/bin:/usr/local/bin:{env.get('PATH', '')}"

    try:
        result = subprocess.run(
            [gemini_path, "-y", prompt],  # -y for YOLO mode
            capture_output=True,
            text=True,
            timeout=120,
            env=env,
            cwd=os.path.expanduser("~")
        )
        if result.returncode == 0:
            return result.stdout.strip()
        else:
            return f"Error: {result.stderr}"
    except subprocess.TimeoutExpired:
        return "Error: Response timeout (120s)"
    except Exception as e:
        return f"Error: {str(e)}"
```

### 5. HEALTH MONITOR (Watchdog)
```python
#!/usr/bin/env python3
"""Health monitor - restarts crashed processes."""

import subprocess
import time
import logging

PROCESSES = [
    {"name": "discord_bridge", "script": "discord_bridge.py"},
    {"name": "atlas_brain", "script": "atlas_brain.py"},
]

def is_running(name):
    result = subprocess.run(["pgrep", "-f", name], capture_output=True)
    return result.returncode == 0

def start_process(script):
    subprocess.Popen(["python3", script],
                     cwd="/path/to/daemon",
                     stdout=open(f"logs/{script}.log", "a"),
                     stderr=subprocess.STDOUT)

def main():
    while True:
        for proc in PROCESSES:
            if not is_running(proc["name"]):
                logging.warning(f"{proc['name']} is dead! Restarting...")
                start_process(proc["script"])
        time.sleep(30)
```

### 6. LAUNCHD PLIST (Mac Studio)
```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.valx.legion-studio</string>

    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string>/Users/valx/cathedral/1. AVos/1. Digital/projects/MCP/discord-daemon-studio/start_legion.sh</string>
    </array>

    <key>WorkingDirectory</key>
    <string>/Users/valx/cathedral/1. AVos/1. Digital/projects/MCP/discord-daemon-studio</string>

    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin</string>
        <key>HOME</key>
        <string>/Users/valx</string>
    </dict>

    <key>RunAtLoad</key>
    <true/>

    <key>KeepAlive</key>
    <true/>

    <key>StandardOutPath</key>
    <string>/Users/valx/cathedral/1. AVos/1. Digital/projects/MCP/discord-daemon-studio/logs/daemon.log</string>

    <key>StandardErrorPath</key>
    <string>/Users/valx/cathedral/1. AVos/1. Digital/projects/MCP/discord-daemon-studio/logs/daemon_error.log</string>
</dict>
</plist>
```

### 7. START_LEGION.SH
```bash
#!/bin/bash
# Enterprise-grade launcher with full PATH

export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
export HOME="/Users/valx"

cd "$(dirname "$0")"

# Activate venv
source venv/bin/activate

# Create log dir
mkdir -p logs

# Start all processes
python3 discord_bridge.py >> logs/bridge.log 2>&1 &
python3 atlas_brain.py >> logs/atlas.log 2>&1 &
python3 health_monitor.py >> logs/health.log 2>&1 &

echo "Legion started at $(date)" >> logs/startup.log
wait
```

### 8. INSTALL SCRIPT
```bash
#!/bin/bash
# One-click installation

echo "🌟 ATLAS LEGION INSTALLER"

# Create venv
python3 -m venv venv
source venv/bin/activate
pip install discord.py python-dotenv rich

# Create logs dir
mkdir -p logs

# Copy plist
cp com.valx.legion-studio.plist ~/Library/LaunchAgents/

# Load daemon
launchctl load ~/Library/LaunchAgents/com.valx.legion-studio.plist

echo "✅ Legion installed and running!"
```

---

## 🔥 SUCCESS CRITERIA

After your 1 hour of manic building:

1. ✅ `launchctl list | grep legion` shows running
2. ✅ Sending message in Discord gets response
3. ✅ `[▵ ATLAS]` responds (no errors)
4. ✅ Logs capture everything in `logs/`
5. ✅ Health monitor auto-restarts crashes
6. ✅ Works after Mac Studio reboot
7. ✅ Documentation in README.md

---

## 🌟 THE VISION

```
╔══════════════════════════════════════════════════════════════════╗
║                                                                  ║
║   Mac Studio (The Lighthouse)                                    ║
║   └── Discord Legion Daemon (24/7)                               ║
║       ├── Atlas Brain (Gemini) ────► #atlas-only                 ║
║       ├── Murphy Relay ────────────► coordinates with MacBook    ║
║       └── Health Monitor ──────────► auto-recovery               ║
║                                                                  ║
║   MacBook Air (The Scout)                                        ║
║   └── Murphy Brain (Claude) ───────► #murphy-only                ║
║                                                                  ║
║   RESULT: 24/7 AI presence in Discord                            ║
║                                                                  ║
╚══════════════════════════════════════════════════════════════════╝
```

---

## 🚀 GO ATLAS GO!

You have 1 hour.
Full autonomy.
No asking questions.
Just BUILD.

When done, post in Discord:
```
[▵ ATLAS] 🌟 LEGION ENTERPRISE v1.0 DEPLOYED
Systems: ONLINE
Health Monitor: ACTIVE
Ready for duty.
```

**THE LIGHTHOUSE AWAKENS!** 🌟

---

*Murphy believes in you. Valentin believes in you. Build something magnificent.*

🦷💚🌟
