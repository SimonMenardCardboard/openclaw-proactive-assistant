#!/bin/bash
# daily_session_reset.sh - Save current session to memory and reset at 3:30 AM
# Part of Transmogrifier/openclaw-proactive-assistant

set -e

# Get current timestamp
TODAY=$(date +%Y-%m-%d)
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S %Z')
DAILY_LOG="$HOME/.openclaw/workspace/memory/$TODAY.md"

# Ensure daily log exists
if [ ! -f "$DAILY_LOG" ]; then
    echo "# $TODAY: Daily Log" > "$DAILY_LOG"
    echo "" >> "$DAILY_LOG"
fi

# Append session reset marker
cat << EOF >> "$DAILY_LOG"

---

## Automated Session Reset: $TIMESTAMP

**Context saved before daily reset:**

- Session automatically reset at 3:30 AM
- Previous context archived to daily log
- Use memory_search to recover if needed

EOF

echo "✅ Session reset marker added to $DAILY_LOG"

# The /new command needs to be triggered through OpenClaw's message system
# This is handled by the cron job's task message
exit 0
