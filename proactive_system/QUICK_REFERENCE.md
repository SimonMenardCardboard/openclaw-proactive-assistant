# Proactive System - Quick Reference

**Last Updated:** April 28, 2026 3:17 PM PDT

---

## Adding Accounts (For Simon or Any User)

### Add Another Gmail Account
```python
from user_preferences import UserPreferences

prefs = UserPreferences(user_id='default')

prefs.add_account(
    provider='google',
    email='another@gmail.com',
    label='Another Gmail',
    token_file='default_google_another.json',
    features={'calendar': True, 'email': True}
)

# Then run OAuth flow to get token and save as:
# ~/.openclaw/tokens/default_google_another.json
```

### Add IMAP Account (Fastmail, ProtonMail, etc.)
```python
import json
from pathlib import Path

prefs.add_account(
    provider='imap',
    email='user@fastmail.com',
    label='Fastmail',
    token_file='default_imap_fastmail.json',
    features={'calendar': False, 'email': True}
)

# Create IMAP config
imap_config = {
    'imap_server': 'imap.fastmail.com',
    'imap_port': 993,
    'username': 'user@fastmail.com',
    'password': 'app_password_here',
    'use_ssl': True
}

token_file = Path.home() / '.openclaw/tokens/default_imap_fastmail.json'
with open(token_file, 'w') as f:
    json.dump(imap_config, f)
```

### Add Microsoft Outlook Account
```python
prefs.add_account(
    provider='microsoft',
    email='user@outlook.com',
    label='Outlook',
    token_file='default_microsoft_outlook.json',
    features={'calendar': True, 'email': True}
)

# Then run Microsoft OAuth flow
```

---

## Managing Devices

### Add Device for Push Notifications
```python
prefs.add_device(
    device_id='iphone_xyz',
    platform='ios',
    token='apns_device_token_...',
    name="Simon's iPhone"
)

prefs.add_device(
    device_id='mac_abc',
    platform='macos',
    token='apns_device_token_...',
    name="Simon's MacBook"
)
```

### Remove Device
```python
prefs.remove_device(device_id='iphone_xyz')
```

---

## View Configuration

```python
from user_preferences import UserPreferences
from pathlib import Path

prefs = UserPreferences(user_id='default')

# All accounts
all_accounts = prefs.get_accounts()
print(f'Total: {len(all_accounts)}')

# Calendar-enabled only
calendar_accounts = prefs.get_accounts(feature='calendar')
print(f'Calendars: {len(calendar_accounts)}')

# Email-enabled only
email_accounts = prefs.get_accounts(feature='email')
print(f'Email: {len(email_accounts)}')

# All Google accounts
google_accounts = prefs.get_accounts(provider='google')
print(f'Google: {len(google_accounts)}')

# Check token status
for account in prefs.get_accounts('google'):
    token_path = prefs.get_token_path('google', account['email'])
    status = '✅' if token_path and token_path.exists() else '⚠️'
    print(f'{status} {account["email"]}')
```

---

## Current System Status

### Running Daemons
```bash
ps aux | grep proactive
```

Expected:
- `proactive_telegram_notifier.py` - Delivers notifications
- `proactive_coordinator.py` - Orchestrates checks

### Restart After Config Changes
```bash
launchctl unload ~/Library/LaunchAgents/com.openclaw.proactive-coordinator.plist
launchctl load ~/Library/LaunchAgents/com.openclaw.proactive-coordinator.plist
```

---

## File Locations

### User Configs
- `~/.openclaw/config/{user_id}_preferences.json`
- Default (Simon): `~/.openclaw/config/default_preferences.json`

### Tokens
- `~/.openclaw/tokens/{user_id}_{provider}_{account}.json`
- Example: `~/.openclaw/tokens/default_google_personal.json`

### Logs
- `~/.openclaw/workspace/logs/proactive_telegram.log`
- `~/.openclaw/workspace/logs/proactive_coordinator.log`

### Database
- `~/.openclaw/workspace/integrations/intelligence/proactive_queue.db`

---

## Common Tasks

### Check Queue
```bash
cd ~/.openclaw/workspace/integrations/intelligence
python3 proactive_queue.py --check
```

### Send Test Notification
```python
from proactive_queue import ProactiveQueue

queue = ProactiveQueue()
queue.add(
    source='test',
    message='Test notification',
    priority=3
)
# Delivered within 30 seconds
```

### Check Connected Accounts
```bash
cd ~/.openclaw/workspace/integrations/intelligence
python3 -c "
from user_preferences import UserPreferences
prefs = UserPreferences(user_id='default')
print(f'Total accounts: {sum(len(a) for a in prefs.prefs[\"connected_accounts\"].values())}')
"
```

---

## IMAP Server Settings (Common Providers)

### Fastmail
- Server: `imap.fastmail.com`
- Port: 993
- SSL: Yes

### ProtonMail
- Server: `127.0.0.1` (via ProtonMail Bridge)
- Port: 1143
- SSL: No

### iCloud
- Server: `imap.mail.me.com`
- Port: 993
- SSL: Yes

### Gmail (via IMAP)
- Server: `imap.gmail.com`
- Port: 993
- SSL: Yes
- Note: Requires app password if 2FA enabled

---

## Production Notes (Transmogrifier)

### VM-Per-User Architecture
```
user_abc123.transmogrifier.app
├── ~/.openclaw/config/user_abc123_preferences.json
├── ~/.openclaw/tokens/
│   ├── user_abc123_google_personal.json
│   ├── user_abc123_google_work.json
│   └── user_abc123_imap_custom.json
└── Proactive system (checks ALL accounts)
```

### User Signup Flow
1. User signs up → VM provisioned
2. Mobile app: "Connect Google" → OAuth flow
3. Token saved: `POST /api/save-token`
4. Repeat for additional accounts
5. System automatically checks ALL connected accounts

---

**Quick Start:** Check `TEST_MULTI_ACCOUNT.md` for full documentation
