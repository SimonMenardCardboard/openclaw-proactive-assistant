# Deferred Projects - Next Session

Two projects deferred from Priority 4 & 5 execution.

---

## Project 1: V7 Self-Healing Threshold Tuning

**Priority:** High  
**Effort:** 4-6 hours  
**Impact:** Make V7 actually detect and repair failures

---

### Current State

**What works:**
- ✅ V7 daemon running (21+ days uptime)
- ✅ Health monitoring code exists
- ✅ Repair action handlers implemented

**What doesn't work:**
- ❌ No repairs executed in last 30 days (0 repairs)
- ❌ Failures occurred but V7 didn't detect them:
  - OAuth tokens expired (not caught)
  - File descriptor leak accumulated (not caught)
  - Executor process froze (not caught)
  - V6 logs stopped updating (not caught)

---

### Root Cause Analysis

**Hypothesis 1: Detection Thresholds Too Conservative**

V7 health checks might be too strict:
- OAuth: Only alerts if token completely invalid (not "expires in 24h")
- Services: Only alerts if process crashed (not "no logs in 7 days")
- Resources: Only alerts at critical levels (not "trending toward failure")

**Hypothesis 2: Health Checks Not Comprehensive**

V7 monitors might be missing key signals:
- File descriptor count (didn't catch leak until 1000+)
- Log file freshness (didn't notice V6 logs stopped Apr 6)
- Process responsiveness (didn't notice executor frozen)

**Hypothesis 3: Repair Actions Too Cautious**

V7 might require manual approval for repairs:
- OAuth refresh needs approval? (should be auto)
- Service restart needs approval? (should be auto for daemons)
- Risk thresholds too high for safe repairs?

---

### Investigation Steps (2 hours)

**Step 1: Review V7 Health Check Configuration**

```bash
# Find V7 daemon configuration
cat ~/.openclaw/workspace/integrations/intelligence/v7_self_healing_daemon.py | grep -A 20 "health_check\|threshold\|detect"

# Check what health checks are enabled
sqlite3 ~/.openclaw/workspace/integrations/intelligence/health_monitor.db ".tables"
sqlite3 ~/.openclaw/workspace/integrations/intelligence/health_monitor.db "SELECT * FROM health_checks LIMIT 10;"

# Review detection logic
grep -n "def detect\|def check_health" ~/.openclaw/workspace/integrations/intelligence/v7_*.py
```

**Step 2: Analyze Why Recent Failures Weren't Caught**

Known failures that V7 should have detected:

1. **OAuth Token Expiry (simon@legalmensch.com)**
   - Expired: Unknown date
   - V7 should have: Detected expiry, auto-refreshed
   - Why it didn't: Check OAuth monitor thresholds

2. **File Descriptor Leak (Telegram Notifier)**
   - Started: ~Apr 21
   - Reached critical: Apr 29 (1000+ handles)
   - V7 should have: Detected rising FD count, restarted notifier
   - Why it didn't: No FD count monitoring?

3. **Executor Process Frozen**
   - Froze: Apr 18
   - Discovered: Apr 29 (11 days later)
   - V7 should have: Detected no log activity, restarted process
   - Why it didn't: Check process monitor

4. **V6 Logs Stopped Updating**
   - Stopped: Apr 6
   - Still not updating: Apr 29 (23 days)
   - V7 should have: Detected stale logs, investigated daemon
   - Why it didn't: Check log freshness monitor

**Step 3: Test Current Detection (30 min)**

Create known failures and verify V7 detects them:

```python
# Test 1: Expire an OAuth token manually
import json
from pathlib import Path
from datetime import datetime, timedelta

token_file = Path.home() / ".openclaw/workspace/integrations/direct_api/token_test.json"
token_data = {
    'token': 'test_token',
    'expiry': (datetime.now() - timedelta(hours=1)).isoformat() + 'Z'  # Expired 1 hour ago
}
with open(token_file, 'w') as f:
    json.dump(token_data, f)

# Wait 5 minutes, check if V7 detected it
# sqlite3 health_monitor.db "SELECT * FROM health_checks WHERE check_type='oauth' ORDER BY timestamp DESC LIMIT 5;"
```

```python
# Test 2: Create a process with high file descriptors
import subprocess
import time

# Open 100 files without closing
handles = []
for i in range(100):
    handles.append(open('/tmp/leak_test_{i}.txt', 'w'))

# Wait 5 minutes, check if V7 detected it
time.sleep(300)
```

```python
# Test 3: Stop writing to a log file
# Simulate frozen process
import time
from pathlib import Path

log_file = Path("/tmp/test_daemon.log")
log_file.write_text("Starting daemon...\n")

# Stop writing (simulate freeze)
time.sleep(600)  # 10 minutes of silence

# Check if V7 detects stale log
```

---

### Implementation Plan (4 hours)

**Phase 1: Lower Detection Thresholds (2 hours)**

Current (conservative) → Target (proactive):

| Check | Current | Target | Why |
|-------|---------|--------|-----|
| OAuth expiry | Token invalid | Expires in <48h | Prevent expiry |
| Log freshness | No logs in 7 days | No logs in 24h | Catch freezes faster |
| File descriptors | >1024 (critical) | >100 (warning) | Early detection |
| Process health | Crashed | No logs in 1h | Detect hangs |
| Service uptime | Stopped | Not responding | Catch freezes |

**Implementation:**

```python
# v7_self_healing_daemon.py

# OAuth Monitor
class OAuthHealthCheck:
    def __init__(self):
        self.expiry_warning_hours = 48  # Down from 168 (7 days)
        self.expiry_critical_hours = 24  # Down from 24
    
    def check(self, token_file):
        # Check expiry
        expires_in_hours = calculate_expiry(token_file)
        
        if expires_in_hours < self.expiry_critical_hours:
            return {'status': 'critical', 'action': 'refresh_now'}
        elif expires_in_hours < self.expiry_warning_hours:
            return {'status': 'warning', 'action': 'refresh_soon'}
        else:
            return {'status': 'ok'}

# Log Freshness Monitor
class LogFreshnessCheck:
    def __init__(self):
        self.warning_threshold_hours = 24  # Down from 168 (7 days)
        self.critical_threshold_hours = 48  # Down from 336 (14 days)
    
    def check(self, log_file):
        import os
        from datetime import datetime, timedelta
        
        if not os.path.exists(log_file):
            return {'status': 'critical', 'action': 'investigate_missing_log'}
        
        mtime = os.path.getmtime(log_file)
        age_hours = (datetime.now() - datetime.fromtimestamp(mtime)).total_seconds() / 3600
        
        if age_hours > self.critical_threshold_hours:
            return {'status': 'critical', 'action': 'restart_process'}
        elif age_hours > self.warning_threshold_hours:
            return {'status': 'warning', 'action': 'monitor_closely'}
        else:
            return {'status': 'ok'}

# File Descriptor Monitor (NEW)
class FileDescriptorCheck:
    def __init__(self):
        self.warning_threshold = 100  # Warning at 100 handles
        self.critical_threshold = 500  # Critical at 500 handles
    
    def check(self, process_name):
        import subprocess
        
        # Get process PID
        result = subprocess.run(['pgrep', '-f', process_name], capture_output=True, text=True)
        if not result.stdout.strip():
            return {'status': 'ok'}  # Process not running
        
        pid = result.stdout.strip().split()[0]
        
        # Count file descriptors
        result = subprocess.run(['lsof', '-p', pid], capture_output=True, text=True)
        fd_count = len(result.stdout.strip().split('\n')) - 1  # Minus header
        
        if fd_count > self.critical_threshold:
            return {'status': 'critical', 'action': 'restart_process', 'fd_count': fd_count}
        elif fd_count > self.warning_threshold:
            return {'status': 'warning', 'action': 'monitor_process', 'fd_count': fd_count}
        else:
            return {'status': 'ok', 'fd_count': fd_count}
```

**Phase 2: Enable Auto-Repair for Safe Actions (1 hour)**

```python
# v7_self_healing_daemon.py

class SelfHealingDaemon:
    def __init__(self):
        # Auto-repair whitelist (no approval needed)
        self.auto_repair_actions = [
            'refresh_oauth_token',      # Safe: just refreshes credentials
            'restart_daemon',            # Safe: LaunchAgent restarts automatically
            'clear_log_file',            # Safe: just rotates logs
            'restart_telegram_notifier'  # Safe: stateless service
        ]
        
        # Approval required (risky actions)
        self.approval_required_actions = [
            'restart_database',          # Risky: could lose data
            'delete_cache',              # Risky: could break things
            'modify_config'              # Risky: could misconfigure
        ]
    
    def execute_repair(self, action, context):
        if action in self.auto_repair_actions:
            logger.info(f"🔧 Auto-executing repair: {action}")
            result = self.repair_handlers[action](context)
            
            # Notify user of repair
            self.notify_user(f"✅ Auto-repaired: {action}\n\nDetails: {result}")
            
            return result
        else:
            logger.info(f"⏸️  Repair needs approval: {action}")
            return self.request_approval(action, context)
```

**Phase 3: Add Missing Monitors (1 hour)**

```python
# Add to v7_self_healing_daemon.py

monitors = [
    # Existing monitors
    OAuthHealthCheck(),
    ServiceHealthCheck(),
    
    # NEW MONITORS
    FileDescriptorCheck(),      # Catch leaks early
    LogFreshnessCheck(),        # Catch frozen processes
    ProcessResponsivenessCheck(), # Ping processes for liveness
    DiskSpaceCheck(),           # Prevent disk full errors
    DatabaseIntegrityCheck()    # Catch corruption early
]

# Process Responsiveness Check (NEW)
class ProcessResponsivenessCheck:
    def check(self, process_name, healthcheck_endpoint):
        """
        Send a health check ping to the process.
        If no response in 10s, consider process frozen.
        """
        import requests
        
        try:
            response = requests.get(healthcheck_endpoint, timeout=10)
            if response.status_code == 200:
                return {'status': 'ok'}
            else:
                return {'status': 'warning', 'action': 'investigate'}
        except requests.exceptions.Timeout:
            return {'status': 'critical', 'action': 'restart_frozen_process'}
        except Exception as e:
            return {'status': 'critical', 'action': 'restart_crashed_process', 'error': str(e)}
```

---

### Testing Plan (1 hour)

**Test 1: OAuth Expiry Detection**
```bash
# Manually expire a token
# Wait 5 minutes
# Verify V7 detected it and auto-refreshed
```

**Test 2: File Descriptor Leak**
```bash
# Run a process that leaks FDs
# Wait for V7 to detect and restart it
# Verify FD count drops after repair
```

**Test 3: Frozen Process**
```bash
# Start a daemon, then freeze it (kill -STOP)
# Wait for V7 to detect no log activity
# Verify V7 restarts the process
```

**Test 4: Log Freshness**
```bash
# Stop writing to a log file
# Wait 24 hours (or mock timestamp)
# Verify V7 detects stale log and investigates
```

**Success Criteria:**
- All 4 test failures detected within 5 minutes
- At least 2 auto-repaired without approval
- User notified of all repairs

---

### Expected Outcomes

**Before:**
- 0 repairs in 30 days
- Multiple failures undetected
- Manual intervention required

**After:**
- OAuth tokens auto-refresh before expiry
- File descriptor leaks caught early
- Frozen processes detected and restarted
- 80%+ failures auto-repaired

**Grade Impact:**
- V7 Self-Healing: C- (72) → B+ (88)
- Overall System: B+ (87) → A- (92)

---

### Files to Modify

1. `~/.openclaw/workspace/integrations/intelligence/v7_self_healing_daemon.py`
   - Lower detection thresholds
   - Add new monitors
   - Enable auto-repair for safe actions

2. `~/.openclaw/workspace/integrations/intelligence/v7_health_checks.py` (if exists)
   - Add FileDescriptorCheck
   - Add LogFreshnessCheck
   - Add ProcessResponsivenessCheck

3. `~/.openclaw/workspace/integrations/intelligence/v7_repair_handlers.py` (if exists)
   - Implement missing repair handlers
   - Add verification steps

---

### Success Metrics

| Metric | Current | Target | Measurement |
|--------|---------|--------|-------------|
| Repairs/month | 0 | 10+ | execution_log.db |
| Auto-repair rate | 0% | 80% | repairs / total failures |
| Detection time | Never | <5 min | timestamp diff |
| False positive rate | Unknown | <10% | manual review |
| Mean time to repair | ∞ (manual) | <10 min | auto repair latency |

---

## Project 2: Message Filtering & Prioritization

**Priority:** Medium  
**Effort:** 3-4 hours  
**Impact:** Improve signal-to-noise ratio from 10% → 90%

---

### Current State

**User receives (last 48 hours):**
- 90% meta/system messages ("I built X", "I pushed Y")
- 10% intelligence messages (email/calendar insights)

**User expectation:**
- 90% intelligence
- 10% system updates (only critical)

**Current implementation:**
- All messages go to single proactive_queue
- Notifier delivers everything with priority >2
- No filtering by message type/source

---

### Problem Analysis

**Example of current message flow:**

```
User receives in order:
1. "🎉 Bootstrap Onboarding System LIVE" (system)
2. "✅ Integration Layer BUILT & TESTED" (system)
3. "🔍 User Stickiness Audit Complete" (system)
4. "✅ Repository Verified - COMPLETE" (system)
5. "📧 You have 73 unread emails" (intelligence, but fake data)
6. "✅ V8.5 Hobbes Control Integration Complete" (system)
7. "⏳ DNS Configuration - Manual Required" (system)
```

**User perception:** "This is a developer commit log, not an AI assistant"

**What user wants:**

```
User receives in order:
1. "📧 You have 201 unread emails - 12 from Sarah (urgent)" (intelligence)
2. "📅 Meeting in 10 min with John - here's context" (intelligence)
3. "🏋️ WHOOP recovery 32% - recommend light training" (intelligence)
4. "⚙️ Auto-refreshed OAuth token for gmail" (system, low priority)
5. "✅ Fixed file descriptor leak in notifier" (system, low priority)
```

---

### Solution Design

**Two-Tier Queue System:**

```
┌─────────────────────────────────────────┐
│         Proactive Queue DB              │
├─────────────────────────────────────────┤
│  All messages with metadata             │
│  - source (v6, v7, v8, system, etc)     │
│  - priority (1-5)                       │
│  - type (intelligence vs system)        │
│  - user_facing (bool)                   │
└─────────────────────────────────────────┘
            ↓
    ┌───────┴────────┐
    ↓                ↓
┌─────────┐    ┌──────────┐
│ User    │    │ System   │
│ Channel │    │ Log      │
├─────────┤    ├──────────┤
│Telegram │    │ File     │
│Push     │    │ Only     │
│Email    │    │          │
└─────────┘    └──────────┘
```

**Filtering Rules:**

| Source | Type | User Channel | System Log |
|--------|------|--------------|------------|
| `v6-executor` | Action taken | ✅ Always | ✅ Always |
| `v7-self-healing` | Repair made | ✅ Always | ✅ Always |
| `v8-pattern` | Insight found | ✅ Always | ✅ Always |
| `bootstrap` | Personalized rec | ✅ Always | ✅ Always |
| `email` | Email insight | ✅ Always | ✅ Always |
| `calendar` | Calendar insight | ✅ Always | ✅ Always |
| `system` | Build notification | ❌ Never | ✅ Always |
| `build` | Build complete | ❌ Never | ✅ Always |
| `audit` | Audit result | Priority 1 only | ✅ Always |
| `github` | Code pushed | ❌ Never | ✅ Always |
| `test` | Test result | ❌ Never | ✅ Always |

**Priority Override:**
- Priority 1 (urgent): Always send to user, regardless of source
- Priority 2-3 (normal): Filter by source (intelligence only)
- Priority 4-5 (low): System log only

---

### Implementation Plan (3 hours)

**Phase 1: Add Message Type Classification (1 hour)**

```python
# proactive_queue.py

class ProactiveQueue:
    def add(self, source: str, message: str, priority: int = 3, context: Optional[Dict] = None):
        """Add a recommendation to the queue with automatic classification."""
        
        # Classify message type
        message_type = self._classify_message(source)
        user_facing = self._is_user_facing(source, priority)
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO proactive_queue 
                (source, message, priority, context, message_type, user_facing)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (source, message, priority, 
                  json.dumps(context) if context else None,
                  message_type, user_facing))
    
    def _classify_message(self, source: str) -> str:
        """Classify message as intelligence or system."""
        intelligence_sources = [
            'v6-executor', 'v7-self-healing', 'v8-pattern',
            'bootstrap', 'email', 'calendar', 'training',
            'recovery', 'nutrition'
        ]
        
        if source in intelligence_sources:
            return 'intelligence'
        else:
            return 'system'
    
    def _is_user_facing(self, source: str, priority: int) -> bool:
        """Determine if message should go to user channel."""
        
        # Priority 1 always goes to user
        if priority == 1:
            return True
        
        # System messages go to log only (unless P1)
        system_sources = ['system', 'build', 'github', 'test']
        if source in system_sources:
            return False
        
        # Intelligence messages go to user
        return True

# Update schema
ALTER TABLE proactive_queue ADD COLUMN message_type TEXT DEFAULT 'system';
ALTER TABLE proactive_queue ADD COLUMN user_facing BOOLEAN DEFAULT 1;
CREATE INDEX idx_user_facing ON proactive_queue(user_facing, priority);
```

**Phase 2: Update Notifier to Filter (1 hour)**

```python
# proactive_telegram_notifier.py

class TelegramNotifier:
    def process_pending(self):
        """Process only user-facing pending recommendations."""
        
        # Get ONLY user-facing messages
        pending = self.queue.get_user_facing_pending(limit=5)
        
        if not pending:
            logger.debug("No user-facing pending recommendations")
            return
        
        logger.info(f"📬 Processing {len(pending)} user-facing recommendation(s)")
        
        for rec in pending:
            message = rec['message']
            
            if self.send_message(message):
                self.queue.mark_delivered(rec['id'])
                logger.info(f"✅ Delivered #{rec['id']} to user")
                time.sleep(2)
            else:
                logger.warning(f"⚠️  Failed to deliver #{rec['id']}")
                break

# proactive_queue.py

class ProactiveQueue:
    def get_user_facing_pending(self, limit: int = 10) -> List[Dict]:
        """Get only user-facing undelivered recommendations."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("""
                SELECT id, source, priority, message, context, created_at
                FROM proactive_queue
                WHERE delivered = 0 
                  AND user_facing = 1
                ORDER BY priority ASC, created_at ASC
                LIMIT ?
            """, (limit,))
            
            rows = cursor.fetchall()
            cursor.close()
            
            results = []
            for row in rows:
                results.append({
                    'id': row['id'],
                    'source': row['source'],
                    'priority': row['priority'],
                    'message': row['message'],
                    'context': json.loads(row['context']) if row['context'] else {},
                    'created_at': row['created_at']
                })
            return results
```

**Phase 3: Add System Log Writer (1 hour)**

```python
# proactive_system_logger.py

import sqlite3
import logging
from pathlib import Path
from datetime import datetime

class SystemLogger:
    """Writes system messages to structured log file."""
    
    def __init__(self, log_file: Path):
        self.log_file = log_file
        self.logger = logging.getLogger('system_queue')
        
        # Setup file handler
        handler = logging.FileHandler(log_file)
        handler.setFormatter(logging.Formatter(
            '%(asctime)s [%(levelname)s] [%(source)s] %(message)s'
        ))
        self.logger.addHandler(handler)
        self.logger.setLevel(logging.INFO)
    
    def process_pending(self, queue):
        """Process system messages to log file."""
        
        # Get only system messages
        pending = queue.get_system_pending(limit=100)
        
        for rec in pending:
            # Write to log file
            extra = {'source': rec['source']}
            
            if rec['priority'] == 1:
                self.logger.critical(rec['message'], extra=extra)
            elif rec['priority'] == 2:
                self.logger.error(rec['message'], extra=extra)
            elif rec['priority'] == 3:
                self.logger.warning(rec['message'], extra=extra)
            else:
                self.logger.info(rec['message'], extra=extra)
            
            # Mark as delivered
            queue.mark_delivered(rec['id'])

# proactive_queue.py
class ProactiveQueue:
    def get_system_pending(self, limit: int = 100) -> List[Dict]:
        """Get only system messages (not user-facing)."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("""
                SELECT id, source, priority, message, created_at
                FROM proactive_queue
                WHERE delivered = 0 
                  AND user_facing = 0
                ORDER BY created_at DESC
                LIMIT ?
            """, (limit,))
            
            rows = cursor.fetchall()
            cursor.close()
            
            return [dict(row) for row in rows]

# Run as separate daemon
if __name__ == '__main__':
    queue = ProactiveQueue()
    logger = SystemLogger(Path.home() / '.openclaw/workspace/logs/system_queue.log')
    
    while True:
        logger.process_pending(queue)
        time.sleep(60)  # Every minute
```

---

### Migration Plan

**Step 1: Backfill existing messages (5 min)**

```python
# Classify all existing undelivered messages
import sqlite3
from pathlib import Path

db_path = Path.home() / '.openclaw/workspace/integrations/intelligence/proactive_queue.db'
conn = sqlite3.connect(db_path)

# Add new columns
conn.execute("ALTER TABLE proactive_queue ADD COLUMN message_type TEXT DEFAULT 'system'")
conn.execute("ALTER TABLE proactive_queue ADD COLUMN user_facing BOOLEAN DEFAULT 1")

# Classify existing messages
intelligence_sources = ['v6-executor', 'v7-self-healing', 'v8-pattern', 'bootstrap', 'email', 'calendar']

for source in intelligence_sources:
    conn.execute("""
        UPDATE proactive_queue
        SET message_type = 'intelligence', user_facing = 1
        WHERE source = ?
    """, (source,))

system_sources = ['system', 'build', 'github', 'test', 'audit']

for source in system_sources:
    conn.execute("""
        UPDATE proactive_queue
        SET message_type = 'system', user_facing = 0
        WHERE source = ? AND priority > 1
    """, (source,))

conn.commit()
conn.close()

print("✅ Backfilled message classifications")
```

**Step 2: Deploy updated notifier (5 min)**

```bash
# Kill old notifier
pkill -f "proactive_telegram_notifier.py"

# Start new filtered notifier
cd ~/.openclaw/workspace/integrations/intelligence
nohup python3 proactive_telegram_notifier.py \
  --bot-token 8089051398:AAHx1njRcwL7WiUbeCBPESqACCXwW7hs_MY \
  --chat-id 8451730454 \
  --interval 30 \
  > /tmp/filtered_notifier.log 2>&1 &
```

**Step 3: Start system logger (5 min)**

```bash
# Start system message logger
cd ~/.openclaw/workspace/integrations/intelligence
nohup python3 proactive_system_logger.py > /dev/null 2>&1 &
```

---

### Testing Plan

**Test 1: System Message Filtering**

```python
# Add a system message
queue.add(
    source='build',
    message='Test build notification (should go to log only)',
    priority=3
)

# Wait 60 seconds
# Verify: NOT sent to Telegram
# Verify: Written to system_queue.log
```

**Test 2: Intelligence Message Delivery**

```python
# Add an intelligence message
queue.add(
    source='v8-pattern',
    message='Test intelligence insight (should go to user)',
    priority=2
)

# Wait 30 seconds
# Verify: Sent to Telegram
# Verify: Also in system_queue.log
```

**Test 3: Priority Override**

```python
# Add high-priority system message
queue.add(
    source='system',
    message='CRITICAL: System alert (P1 goes to user)',
    priority=1
)

# Wait 30 seconds
# Verify: Sent to Telegram (priority override)
# Verify: Also in system_queue.log
```

---

### Expected Outcomes

**Before:**
- 45 messages in 48h (90% system, 10% intelligence)
- User overwhelmed with build logs
- Signal-to-noise ratio: 10%

**After:**
- User channel: 5 messages in 48h (100% intelligence)
- System log: 40 messages in 48h (build logs)
- Signal-to-noise ratio: 90%+

**User perception:**
- Before: "Developer commit log"
- After: "AI assistant with insights"

**Grade Impact:**
- Message Quality: D+ (69) → B+ (88)
- User Experience: C+ (77) → A- (90)

---

### Success Metrics

| Metric | Current | Target |
|--------|---------|--------|
| User messages/day | 22.5 | 3-5 |
| Intelligence ratio | 10% | 90%+ |
| System messages to user | 90% | <10% |
| User satisfaction | "Too noisy" | "Just right" |

---

## Summary

### Project 1: V7 Threshold Tuning
- **Effort:** 4-6 hours
- **Impact:** 0 repairs/month → 10+ repairs/month
- **Approach:** Lower thresholds, add monitors, enable auto-repair

### Project 2: Message Filtering
- **Effort:** 3-4 hours
- **Impact:** 90% noise → 10% noise
- **Approach:** Two-tier queue, source-based filtering, system log

**Total deferred work:** 7-10 hours  
**Grade impact if completed:** B+ (87) → A (93-95)

**Recommendation:** Do Project 2 first (higher user impact, lower risk)
