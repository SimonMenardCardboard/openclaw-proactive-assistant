# Notification System

## Overview
The proactive assistant supports multiple notification backends:

1. **Telegram Bot** (Hobbes Prime / personal use)
2. **In-App Notifications** (Transmogrifier customers)
3. **Push Notifications** (Future: APNs/FCM)

## Auto-Detection
The system automatically detects which mode to use:

```python
from universal_notifier import UniversalNotifier

notifier = UniversalNotifier()
notifier.send_text("Hello!")
```

Detection priority:
1. `NOTIFICATION_MODE` environment variable
2. `TELEGRAM_BOT_TOKEN` → Telegram mode
3. `.transmogrifier/notifications.db` exists → In-app mode
4. APNs/FCM credentials → Push mode
5. Default → In-app mode

## For Transmogrifier Deployment (In-App Mode)

### Setup
No configuration needed. The system automatically:
1. Creates `~/.transmogrifier/notifications.db`
2. Stores notifications in SQLite
3. Mobile/desktop app polls for new notifications

### Database Schema
```sql
CREATE TABLE notifications (
    id INTEGER PRIMARY KEY,
    user_id TEXT NOT NULL,
    title TEXT,
    message TEXT NOT NULL,
    priority INTEGER DEFAULT 3,
    delivered BOOLEAN DEFAULT 0,
    read BOOLEAN DEFAULT 0,
    created_at TIMESTAMP
)
```

### Mobile App Integration
The Transmogrifier mobile app should:

1. **Poll for notifications** (every 30-60 seconds):
```javascript
// React Native
import SQLite from 'react-native-sqlite-storage';

const db = SQLite.openDatabase({ 
  name: 'notifications.db',
  location: 'default' 
});

db.transaction(tx => {
  tx.executeSql(
    'SELECT * FROM notifications WHERE delivered=0 ORDER BY created_at DESC',
    [],
    (tx, results) => {
      // Show notifications in app
    }
  );
});
```

2. **Mark as delivered** after showing:
```sql
UPDATE notifications SET delivered=1 WHERE id=?
```

3. **Mark as read** when user opens:
```sql
UPDATE notifications SET read=1 WHERE id=?
```

## For Personal Use (Telegram Mode)

### Setup
Set environment variable:
```bash
export TELEGRAM_BOT_TOKEN="your_bot_token_here"
```

Or create `~/.openclaw/.env`:
```
TELEGRAM_BOT_TOKEN=your_bot_token_here
```

### LaunchAgent
Add to plist:
```xml
<key>EnvironmentVariables</key>
<dict>
    <key>TELEGRAM_BOT_TOKEN</key>
    <string>YOUR_TOKEN_HERE</string>
</dict>
```

## Migration Path

**Current (Hobbes Prime):**
- Uses Telegram Bot API
- Direct API calls (no Gateway)
- Notifications to @Tsmclaw_bot

**Future (Transmogrifier):**
- Uses in-app database
- No external API calls
- Notifications in mobile app

**Hybrid Support:**
- Same codebase works for both
- Auto-detects mode
- Zero config changes needed

## Architecture

```
V6/V7/V8 Daemons
    ↓
UniversalNotifier
    ↓
┌───────────────┬──────────────────┬─────────────────┐
│   Telegram    │    In-App DB     │  Push (Future)  │
│   Bot API     │   SQLite         │   APNs/FCM      │
└───────────────┴──────────────────┴─────────────────┘
```

## Testing

### Test In-App Mode
```python
import os
os.environ['NOTIFICATION_MODE'] = 'in_app'

from universal_notifier import UniversalNotifier
notifier = UniversalNotifier(user_id='test_user')
notifier.send_text("Test notification")

# Check database
import sqlite3
conn = sqlite3.connect(os.path.expanduser('~/.transmogrifier/notifications.db'))
cursor = conn.cursor()
cursor.execute('SELECT * FROM notifications')
print(cursor.fetchall())
```

### Test Telegram Mode
```python
import os
os.environ['NOTIFICATION_MODE'] = 'telegram'
os.environ['TELEGRAM_BOT_TOKEN'] = 'your_token'

from universal_notifier import UniversalNotifier
notifier = UniversalNotifier()
notifier.send_text("Test from Telegram mode")
```

## Performance

**In-App Mode:**
- Write: <1ms (SQLite insert)
- No network calls
- No stuck processes
- No rate limits

**Telegram Mode:**
- Send: ~100-200ms (API call)
- 10s timeout
- No stuck processes (direct HTTP)
- Telegram rate limits apply

## Security

**In-App:**
- Local database only
- No external API
- User data stays on device

**Telegram:**
- Bot token in environment (not in code)
- HTTPS API calls only
- No user data stored externally
