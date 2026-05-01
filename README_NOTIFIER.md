# Direct Telegram Notifier

## Problem
Using `openclaw message send` via Gateway causes stuck processes that accumulate and overload the system (load average 135+ on 6-core CPU).

## Solution
Direct Telegram Bot API integration bypasses Gateway entirely.

## Files
- `telegram_notifier_direct.py` - Shared notifier used by all systems
- `v6_notifier_direct.py` - Direct API notifier for V6 daemon
- `v6_proactive_daemon.py` - Updated to use direct notifier
- `v8_code_generator.py` - Updated to use direct API

## Usage

### V6/V7/V8 Daemons
```python
from telegram_notifier_direct import TelegramNotifier

notifier = TelegramNotifier()
notifier.send({'message': 'Test notification'})
```

### Simple Scripts
```python
from telegram_notifier_direct import send_telegram_message

send_telegram_message("Hello from script!")
```

## Configuration
Bot token loaded from (in priority order):
1. `TELEGRAM_BOT_TOKEN` environment variable
2. `~/.openclaw/config/config.json` → `telegram.botToken`
3. `~/.openclaw/.env` file

## Impact
- ✅ No more stuck `openclaw-message` processes
- ✅ 10s timeout (was 30s+)
- ✅ Direct HTTP requests (no subprocess overhead)
- ✅ Load average: 4-8 (was 120-136)

## Deployment
All notification systems updated to use direct API:
- V6 Proactive Daemon
- V7 Self-Healing Daemon  
- V8 Meta-Learning
- Approval Handler
- All cron scripts

Works identically in multi-tenant Transmogrifier deployment.
