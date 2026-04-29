# OpenClaw Proactive Assistant - Complete Repository

**Repository:** https://github.com/SimonMenardCardboard/openclaw-proactive-assistant

**Status:** Production-ready autonomous intelligence system

---

## Architecture Overview

This repository contains the complete V6-V8.5 autonomous proactive assistant system:

```
V6 (Autonomous Executor) → V7 (Self-Healing) → V8 (Pattern Learning) → V8.5 (Federated)
                                    ↓
                            Proactive Queue
                                    ↓
                          Telegram Notifier → User
```

---

## Components

### Core Proactive System (`proactive_system/`)

**V6: Autonomous Executor**
- `autonomous_executor.py` (19KB) - Executes background tasks autonomously
- Actions: refresh_auth_token, send_form_reminder, restart_launchagent, restart_tunnel
- Queues notifications on success/failure

**V7: Self-Healing**
- `v7_self_repair.py` (31KB) - Automatic system repair
- Repairs: refresh_auth_token, restart_service, restart_tunnel, cleanup_disk, database_recovery
- Queues repair notifications

**V8: Pattern Learning**
- `proactive_v8_patterns.py` (8.5KB) - Learns user patterns, generates recommendations
- Analyzes email response times, calendar density, work patterns
- Queues spontaneous recommendations every 4 hours

**V8.5: Federated Learning**
- `hobbes_control_client.py` (7KB) - Cross-user pattern learning client
- Submits anonymized patterns to Hobbes Control
- Retrieves federated insights from network
- Routes edge-case questions to Hobbes Prime

**Notification System**
- `proactive_queue.py` - Central queue (SQLite database)
- `proactive_telegram_notifier.py` - Delivery daemon (polls queue every 30s)
- `proactive_coordinator.py` - Orchestrates scheduled checks

**Multi-Provider Email**
- `gmail_api.py` - Google Gmail API implementation
- `microsoft_graph_api.py` - Microsoft Graph API (Outlook)
- `multi_provider_email.py` - Unified multi-account email aggregator
- Supports: Gmail, Outlook, IMAP (any provider)

**Multi-Provider Calendar**
- `icloud_caldav.py` - iCloud CalDAV implementation
- `multi_provider_calendar.py` - Unified multi-calendar aggregator
- Supports: Google Calendar, Outlook Calendar, iCloud

**Monitors**
- `proactive_email.py` - Email monitoring (urgent detection)
- `proactive_calendar.py` - Calendar monitoring (meeting prep, reminders)

**User Management**
- `user_preferences.py` - Multi-account configuration
- Per-account feature toggles (email/calendar on/off)
- Multi-device support

### Bootstrap Onboarding (`onboarding/`)

**Fast-Path to Value: 2-4 Hour Recommendations**

- `bootstrap.py` (11KB) - Main orchestrator
  - Pulls 30-day history on OAuth complete
  - Analyzes patterns (email, calendar, work)
  - Generates 3-5 recommendations
  - Queues with staggered delivery

- `oauth_webhook.py` (4.8KB) - OAuth integration
  - Detects first OAuth completion
  - Triggers bootstrap once per user
  - Tracks bootstrap status

- `test_bootstrap.py` (5.7KB) - Integration tests
  - Simulates full onboarding flow
  - Tests queue integration
  - Validates delivery

- `README.md` (9.7KB) - Production documentation

### Documentation

- `PROACTIVE_SYSTEM.md` - Complete system documentation
- `ONBOARDING_BOOTSTRAP.md` (14KB) - Bootstrap design document
- `FULL_MULTI_PROVIDER_COMPLETE.md` - Multi-provider API guide
- `QUICK_REFERENCE.md` - Quick start guide
- `README.md` - Repository overview

---

## Features

### Autonomous Intelligence (V6-V8)

✅ **V6:** Background task execution + notifications
✅ **V7:** Self-healing with automatic repairs
✅ **V8:** Pattern learning + spontaneous recommendations
✅ **V8.5:** Federated learning via Hobbes Control

### Multi-Account Support

✅ **Email Providers:**
- Google Gmail (OAuth2)
- Microsoft Outlook (OAuth2)
- IMAP (any provider: Fastmail, ProtonMail, custom domains)

✅ **Calendar Providers:**
- Google Calendar (OAuth2)
- Microsoft Outlook Calendar (OAuth2)
- iCloud Calendar (CalDAV)

✅ **Features:**
- Unlimited accounts per user
- Per-account feature toggles
- Smart deduplication (same event from multiple accounts)
- Multi-device delivery

### Bootstrap Onboarding

✅ **Timeline:**
- Hour 0: OAuth complete
- Hour 2: First recommendation
- Hour 4-6: 3-5 total recommendations
- Day 1+: V6/V7 real-time monitoring
- Week 1+: V8 autonomous learning

✅ **Recommendations:**
- Email response speed optimization
- Inbox cleanup suggestions
- Focus time blocking
- Meeting overload reduction
- Work-life boundary protection

---

## Production Deployment

### Prerequisites

- Python 3.11+
- SQLite3
- OpenClaw CLI
- Telegram Bot Token

### Installation

```bash
git clone https://github.com/SimonMenardCardboard/openclaw-proactive-assistant.git
cd openclaw-proactive-assistant

# Install dependencies
pip install -r requirements.txt

# Configure user preferences
cd proactive_system
python3 user_preferences.py
```

### Services to Deploy

1. **Telegram Notifier** (daemon)
   ```bash
   python3 proactive_system/proactive_telegram_notifier.py
   ```

2. **Coordinator** (cron every 30 min)
   ```bash
   python3 proactive_system/proactive_coordinator.py
   ```

3. **Bootstrap Delivery** (cron every 30 min)
   ```bash
   python3 proactive_system/proactive_v6_deliver.py
   ```

### LaunchAgents (macOS)

- `com.openclaw.proactive-notifier.plist`
- `com.openclaw.proactive-coordinator.plist`

---

## Testing

### Test Bootstrap Onboarding

```bash
cd onboarding
python3 test_bootstrap.py              # Simulation
python3 test_bootstrap.py --real       # Real Telegram delivery
```

### Test OAuth Webhook

```bash
cd onboarding
python3 oauth_webhook.py test_user_123
```

### Test Proactive Queue

```bash
cd proactive_system
python3 -c "
from proactive_queue import ProactiveQueue
q = ProactiveQueue()
q.add(source='test', message='Test notification', priority=2)
print('Queued successfully')
"
```

---

## Integration Points

### 1. OAuth Callback (COS)

```python
from onboarding.oauth_webhook import webhook_handler

@app.route('/oauth/callback/<provider>')
def oauth_callback(provider: str):
    save_credentials(user_id, provider, credentials)
    
    # Trigger bootstrap on first OAuth
    if is_first_oauth(user_id):
        asyncio.create_task(
            webhook_handler.on_oauth_complete(user_id, provider, credentials)
        )
```

### 2. V6 Autonomous Actions

```python
from proactive_system.autonomous_executor import AutonomousExecutor

executor = AutonomousExecutor()
executor.execute_action('refresh_auth_token', user_id='default')
# → Queues notification on success/failure
```

### 3. V7 Self-Healing

```python
from proactive_system.v7_self_repair import SelfRepair

repairer = SelfRepair()
repairer.repair('restart_service', service_name='tunnel_manager')
# → Queues repair notification
```

### 4. V8 Pattern Learning

```python
from proactive_system.proactive_v8_patterns import PatternBasedRecommendations

recommender = PatternBasedRecommendations(user_id='default')
recommender.check_for_recommendations()
# → Queues spontaneous recommendations
```

---

## Database Schema

### proactive_queue.db

```sql
CREATE TABLE proactive_queue (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  source TEXT NOT NULL,           -- 'v6', 'v7', 'v8', 'bootstrap'
  priority INTEGER DEFAULT 3,     -- 1=highest, 3=normal, 5=low
  message TEXT NOT NULL,          -- Markdown formatted
  context JSON,                   -- {user_id, type, etc}
  delivered BOOLEAN DEFAULT 0,
  delivered_at TIMESTAMP,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

---

## Monitoring

### Check Queue Status

```bash
sqlite3 proactive_system/proactive_queue.db "
  SELECT COUNT(*) as total,
         SUM(delivered) as delivered,
         COUNT(*) - SUM(delivered) as pending
  FROM proactive_queue"
```

### View Recent Notifications

```bash
sqlite3 proactive_system/proactive_queue.db "
  SELECT source, priority, substr(message, 1, 50) as preview, created_at
  FROM proactive_queue
  ORDER BY created_at DESC
  LIMIT 10"
```

---

## File Count

**Total Files:** 25 Python modules + 7 documentation files = 32 files  
**Total Lines:** ~2,500 lines of code + documentation  
**Repository Size:** ~250KB

---

## Dependencies

- `requests` - HTTP client
- `sqlite3` - Database (built-in)
- `asyncio` - Async operations (built-in)
- `caldav` - iCloud calendar support
- `google-auth` - Gmail OAuth
- `msal` - Microsoft OAuth

---

## License

Private repository - Not open source

---

## Support

**Issues:** https://github.com/SimonMenardCardboard/openclaw-proactive-assistant/issues  
**Contact:** simon@legalmensch.com

---

## Version History

**v1.1.0** (Apr 28, 2026) - V8.5 Federated Learning + Bootstrap Onboarding  
**v1.0.0** (Apr 28, 2026) - Initial commit: V6/V7/V8 + Multi-provider  

---

**Built with ❤️ for autonomous intelligence**
