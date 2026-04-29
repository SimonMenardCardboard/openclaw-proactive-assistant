# App Usage Monitoring Implementation Roadmap

**Goal:** Track desktop + mobile app usage to detect workflow patterns  
**Integration:** V8 continuous pattern daemon  
**Timeline:** 20-28 hours  
**Target:** Pro tier ($25/mo) feature

---

## Overview

### What This Adds

**App Usage Intelligence:**
- Track which apps user opens (desktop + mobile)
- Measure time spent in each app
- Detect app switching patterns
- Learn workflow routines
- Generate productivity insights

**Example Insights:**
- "You usually start Slack at 9 AM - it's 9:30 and you haven't opened it"
- "You've been in Gmail for 2 hours straight - time for a break?"
- "You always review contracts in the evening - here's tonight's queue"
- "Meeting prep: You spend 15 min in Google Docs before client calls"

---

## Architecture

```
┌─────────────────────────────────────────┐
│ Desktop Agents                          │
│ - macOS: NSWorkspace app monitoring     │
│ - Windows: Win32 API window tracking    │
│ - Linux: X11/Wayland window monitoring  │
└──────────────┬──────────────────────────┘
               │
               │ POST JSON (app usage events)
               ↓
┌─────────────────────────────────────────┐
│ Mobile Apps (iOS/Android)               │
│ - iOS: ScreenTime API                   │
│ - Android: UsageStatsManager            │
└──────────────┬──────────────────────────┘
               │
               ↓ (both send to webhook)
┌─────────────────────────────────────────┐
│ User VM: Webhook Endpoint               │
│ POST /api/app_usage/update              │
│ - Validates auth token                  │
│ - Stores in app_usage.db                │
└──────────────┬──────────────────────────┘
               │
               ↓ (stored in database)
┌─────────────────────────────────────────┐
│ App Usage Database (SQLite)             │
│ - app_events table (opens, closes)      │
│ - usage_sessions table (time spans)     │
│ - patterns table (learned routines)     │
└──────────────┬──────────────────────────┘
               │
               ↓ (queries every 5 min)
┌─────────────────────────────────────────┐
│ V8 Continuous Pattern Daemon            │
│ - Detects app usage patterns            │
│ - Learns workflows (email then calendar)│
│ - Generates productivity insights       │
└──────────────┬──────────────────────────┘
               │
               ↓ (delivers insights)
┌─────────────────────────────────────────┐
│ Proactive Queue → Telegram              │
│ "You usually start workday with Slack"  │
└─────────────────────────────────────────┘
```

---

## Platform-Specific Implementation

### Desktop App Usage Tracking

#### macOS (6-8 hours)

**Technology:** NSWorkspace + Accessibility API

**File:** `desktop_agents/macos_app_tracker.swift`

**Capabilities:**
- Active app detection (which app has focus)
- Window title tracking (Gmail: "Inbox", Slack: "#general")
- App open/close events
- Time spent per app
- Background vs foreground time

**Implementation:**
```swift
import Cocoa
import ApplicationServices

class MacAppTracker: NSObject {
    static let shared = MacAppTracker()
    
    private var currentApp: NSRunningApplication?
    private var appStartTime: Date?
    private let apiBaseURL = "https://user.transmogrifier.app"
    
    func startTracking() {
        // Monitor app activation
        NSWorkspace.shared.notificationCenter.addObserver(
            self,
            selector: #selector(appActivated(_:)),
            name: NSWorkspace.didActivateApplicationNotification,
            object: nil
        )
        
        // Monitor app termination
        NSWorkspace.shared.notificationCenter.addObserver(
            self,
            selector: #selector(appTerminated(_:)),
            name: NSWorkspace.didTerminateApplicationNotification,
            object: nil
        )
        
        // Timer for periodic sync (every 5 min)
        Timer.scheduledTimer(withTimeInterval: 300, repeats: true) { _ in
            self.syncCurrentState()
        }
    }
    
    @objc func appActivated(_ notification: Notification) {
        guard let app = notification.userInfo?[NSWorkspace.applicationUserInfoKey] as? NSRunningApplication else { return }
        
        // Save previous app duration
        if let prevApp = currentApp, let startTime = appStartTime {
            let duration = Date().timeIntervalSince(startTime)
            sendUsageEvent(app: prevApp, duration: duration, event: "deactivate")
        }
        
        // Start tracking new app
        currentApp = app
        appStartTime = Date()
        
        sendUsageEvent(app: app, duration: 0, event: "activate")
    }
    
    @objc func appTerminated(_ notification: Notification) {
        guard let app = notification.userInfo?[NSWorkspace.applicationUserInfoKey] as? NSRunningApplication else { return }
        
        sendUsageEvent(app: app, duration: 0, event: "terminate")
    }
    
    func sendUsageEvent(app: NSRunningApplication, duration: TimeInterval, event: String) {
        let payload: [String: Any] = [
            "device_type": "desktop",
            "device_os": "macOS",
            "app_name": app.localizedName ?? "Unknown",
            "bundle_id": app.bundleIdentifier ?? "",
            "event_type": event,
            "duration": Int(duration),
            "timestamp": ISO8601DateFormatter().string(from: Date())
        ]
        
        // POST to webhook (implementation similar to location tracker)
        sendToWebhook(payload)
    }
    
    func getActiveWindowTitle() -> String? {
        // Use Accessibility API to get window title
        let options = CGWindowListOption(arrayLiteral: .optionOnScreenOnly)
        let windowListInfo = CGWindowListCopyWindowInfo(options, kCGNullWindowID)
        
        if let windows = windowListInfo as? [[String: Any]] {
            for window in windows {
                if let ownerName = window[kCGWindowOwnerName as String] as? String,
                   let windowTitle = window[kCGWindowName as String] as? String {
                    if ownerName == currentApp?.localizedName {
                        return windowTitle
                    }
                }
            }
        }
        
        return nil
    }
}
```

**Privacy:**
- Request Accessibility permission on first launch
- Only track app name + bundle ID (not window contents)
- Window title optional (user can disable)
- Data stored on user's private VM only

**LaunchAgent:** Run at login, background process

---

#### Windows (6-8 hours)

**Technology:** Win32 API + SetWinEventHook

**File:** `desktop_agents/windows_app_tracker.py`

**Implementation:**
```python
import win32gui
import win32process
import psutil
import time
import requests
from datetime import datetime

class WindowsAppTracker:
    def __init__(self):
        self.current_app = None
        self.app_start_time = None
        self.api_url = "https://user.transmogrifier.app/api/app_usage/update"
    
    def get_active_window(self):
        """Get currently active window"""
        hwnd = win32gui.GetForegroundWindow()
        if hwnd == 0:
            return None, None
        
        # Get window title
        window_title = win32gui.GetWindowText(hwnd)
        
        # Get process name
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        try:
            process = psutil.Process(pid)
            app_name = process.name()
        except:
            app_name = "Unknown"
        
        return app_name, window_title
    
    def track_loop(self):
        """Main tracking loop"""
        while True:
            app_name, window_title = self.get_active_window()
            
            if app_name and app_name != self.current_app:
                # App changed
                if self.current_app:
                    # Send duration for previous app
                    duration = int((time.time() - self.app_start_time))
                    self.send_usage_event(
                        app_name=self.current_app,
                        duration=duration,
                        event="deactivate"
                    )
                
                # Start tracking new app
                self.current_app = app_name
                self.app_start_time = time.time()
                
                self.send_usage_event(
                    app_name=app_name,
                    window_title=window_title,
                    duration=0,
                    event="activate"
                )
            
            time.sleep(1)  # Check every second
    
    def send_usage_event(self, app_name, duration, event, window_title=None):
        """Send usage event to webhook"""
        payload = {
            "device_type": "desktop",
            "device_os": "Windows",
            "app_name": app_name,
            "window_title": window_title,
            "event_type": event,
            "duration": duration,
            "timestamp": datetime.now().isoformat()
        }
        
        try:
            requests.post(self.api_url, json=payload, headers={
                "Authorization": "Bearer USER_TOKEN"
            }, timeout=5)
        except Exception as e:
            print(f"Failed to send usage event: {e}")

if __name__ == '__main__':
    tracker = WindowsAppTracker()
    tracker.track_loop()
```

**Deployment:** Windows Service (runs at startup)

---

#### Linux (4-6 hours)

**Technology:** X11/Wayland window tracking

**File:** `desktop_agents/linux_app_tracker.py`

**Implementation:**
```python
import subprocess
import time
import requests
from datetime import datetime

class LinuxAppTracker:
    def __init__(self):
        self.current_app = None
        self.app_start_time = None
        self.api_url = "https://user.transmogrifier.app/api/app_usage/update"
    
    def get_active_window_x11(self):
        """Get active window using xdotool (X11)"""
        try:
            # Get active window ID
            window_id = subprocess.check_output(['xdotool', 'getactivewindow']).decode().strip()
            
            # Get window name
            window_name = subprocess.check_output(['xdotool', 'getwindowname', window_id]).decode().strip()
            
            # Get process name
            pid = subprocess.check_output(['xdotool', 'getwindowpid', window_id]).decode().strip()
            app_name = subprocess.check_output(['ps', '-p', pid, '-o', 'comm=']).decode().strip()
            
            return app_name, window_name
        except Exception as e:
            return None, None
    
    def track_loop(self):
        """Main tracking loop"""
        while True:
            app_name, window_title = self.get_active_window_x11()
            
            if app_name and app_name != self.current_app:
                # App changed (same logic as Windows)
                # ... send events ...
            
            time.sleep(1)
    
    # (Similar to Windows implementation)
```

**Deployment:** systemd service

---

### Mobile App Usage Tracking

#### iOS (4-6 hours)

**Technology:** ScreenTime API (FamilyControls framework)

**File:** `mobile_apps/ios/ScreenTimeTracker.swift`

**Implementation:**
```swift
import FamilyControls
import DeviceActivity
import ManagedSettings

class ScreenTimeTracker {
    static let shared = ScreenTimeTracker()
    
    func requestAuthorization() {
        AuthorizationCenter.shared.requestAuthorization { result in
            switch result {
            case .success:
                print("ScreenTime authorization granted")
                self.startTracking()
            case .failure(let error):
                print("Authorization failed: \\(error)")
            }
        }
    }
    
    func startTracking() {
        // Monitor app usage via DeviceActivity
        let schedule = DeviceActivitySchedule(
            intervalStart: DateComponents(hour: 0, minute: 0),
            intervalEnd: DateComponents(hour: 23, minute: 59),
            repeats: true
        )
        
        let center = DeviceActivityCenter()
        do {
            try center.startMonitoring(.daily, during: schedule)
        } catch {
            print("Failed to start monitoring: \\(error)")
        }
    }
    
    func getUsageData() -> [AppUsage] {
        // Fetch ScreenTime data
        // Note: iOS 15+ provides this data
        // Returns app bundle ID + total time
        
        var usageData: [AppUsage] = []
        
        // Query ScreenTime API
        // (Simplified - actual implementation uses DeviceActivityReport)
        
        return usageData
    }
    
    func syncToServer() {
        let usage = getUsageData()
        
        for app in usage {
            let payload: [String: Any] = [
                "device_type": "mobile",
                "device_os": "iOS",
                "app_name": app.name,
                "bundle_id": app.bundleId,
                "duration": app.duration,
                "timestamp": ISO8601DateFormatter().string(from: Date())
            ]
            
            // POST to webhook
            sendToWebhook(payload)
        }
    }
}

struct AppUsage {
    let name: String
    let bundleId: String
    let duration: TimeInterval
}
```

**Limitations:**
- ScreenTime API only available iOS 15+
- User must grant explicit permission
- Can't access real-time data (hourly aggregates only)

**Alternative:** Use accessibility events (less reliable)

---

#### Android (4-6 hours)

**Technology:** UsageStatsManager

**File:** `mobile_apps/android/AppUsageTracker.kt`

**Implementation:**
```kotlin
package com.transmogrifier.appusage

import android.app.usage.UsageStats
import android.app.usage.UsageStatsManager
import android.content.Context
import android.content.pm.PackageManager
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import okhttp3.*
import org.json.JSONObject
import java.util.*

class AppUsageTracker(private val context: Context) {
    
    private val usageStatsManager = context.getSystemService(Context.USAGE_STATS_SERVICE) as UsageStatsManager
    private val packageManager = context.packageManager
    private val apiUrl = "https://user.transmogrifier.app/api/app_usage/update"
    
    fun getUsageStats(days: Int = 1): List<AppUsage> {
        val endTime = System.currentTimeMillis()
        val startTime = endTime - (days * 24 * 60 * 60 * 1000)
        
        val usageStats = usageStatsManager.queryUsageStats(
            UsageStatsManager.INTERVAL_DAILY,
            startTime,
            endTime
        )
        
        val appUsageList = mutableListOf<AppUsage>()
        
        for (stats in usageStats) {
            if (stats.totalTimeInForeground > 0) {
                val appName = try {
                    packageManager.getApplicationLabel(
                        packageManager.getApplicationInfo(stats.packageName, 0)
                    ).toString()
                } catch (e: PackageManager.NameNotFoundException) {
                    stats.packageName
                }
                
                appUsageList.add(AppUsage(
                    appName = appName,
                    packageName = stats.packageName,
                    duration = stats.totalTimeInForeground / 1000, // Convert to seconds
                    lastTimeUsed = Date(stats.lastTimeUsed)
                ))
            }
        }
        
        return appUsageList.sortedByDescending { it.duration }
    }
    
    fun syncToServer() {
        CoroutineScope(Dispatchers.IO).launch {
            val usageStats = getUsageStats(days = 1)
            
            for (app in usageStats) {
                val payload = JSONObject().apply {
                    put("device_type", "mobile")
                    put("device_os", "Android")
                    put("app_name", app.appName)
                    put("bundle_id", app.packageName)
                    put("duration", app.duration)
                    put("timestamp", Date().toString())
                }
                
                val client = OkHttpClient()
                val request = Request.Builder()
                    .url(apiUrl)
                    .post(RequestBody.create(
                        MediaType.parse("application/json"),
                        payload.toString()
                    ))
                    .addHeader("Authorization", "Bearer USER_TOKEN")
                    .build()
                
                try {
                    client.newCall(request).execute()
                } catch (e: Exception) {
                    println("Sync failed: ${e.message}")
                }
            }
        }
    }
}

data class AppUsage(
    val appName: String,
    val packageName: String,
    val duration: Long, // seconds
    val lastTimeUsed: Date
)
```

**Permission Required:**
```xml
<uses-permission android:name="android.permission.PACKAGE_USAGE_STATS"/>
```

User must grant "Usage Access" permission in Settings.

---

## Backend Infrastructure (6-8 hours)

### App Usage Database

**File:** `app_usage/app_usage_db.py`

**Schema:**
```sql
-- App usage events (open, close, switch)
CREATE TABLE app_events (
    id INTEGER PRIMARY KEY,
    user_email TEXT NOT NULL,
    device_id TEXT NOT NULL,
    device_type TEXT NOT NULL, -- desktop, mobile
    device_os TEXT NOT NULL,   -- macOS, Windows, iOS, Android
    app_name TEXT NOT NULL,
    bundle_id TEXT,
    window_title TEXT,
    event_type TEXT NOT NULL,  -- activate, deactivate, open, close
    timestamp TEXT NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_user_time (user_email, timestamp)
);

-- Usage sessions (aggregated time spans)
CREATE TABLE usage_sessions (
    id INTEGER PRIMARY KEY,
    user_email TEXT NOT NULL,
    device_id TEXT NOT NULL,
    app_name TEXT NOT NULL,
    bundle_id TEXT,
    start_time TEXT NOT NULL,
    end_time TEXT,
    duration INTEGER, -- seconds
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_user_app (user_email, app_name)
);

-- Learned patterns (e.g., "You always open Slack at 9 AM")
CREATE TABLE app_patterns (
    id INTEGER PRIMARY KEY,
    user_email TEXT NOT NULL,
    pattern_type TEXT NOT NULL, -- routine, sequence, anomaly
    app_sequence TEXT,          -- JSON: ["Slack", "Gmail", "Calendar"]
    typical_time TEXT,          -- "09:00:00"
    day_of_week INTEGER,        -- 0-6 (Mon-Sun)
    confidence REAL,
    metadata TEXT,              -- JSON
    last_detected TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
```

---

### Webhook Endpoint

**File:** `webhooks/app_usage_webhook.py`

```python
from flask import Flask, request, jsonify
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent / 'app_usage'))
from app_usage_db import AppUsageDB

app = Flask(__name__)
app_usage_db = AppUsageDB()

@app.route('/api/app_usage/update', methods=['POST'])
def update_app_usage():
    """
    Receive app usage event from desktop agent or mobile app.
    
    Request body:
    {
        "device_type": "desktop",
        "device_os": "macOS",
        "app_name": "Slack",
        "bundle_id": "com.tinyspeck.slackmacgap",
        "window_title": "#general",
        "event_type": "activate",
        "duration": 300,
        "timestamp": "2026-04-29T14:30:00Z"
    }
    """
    # Auth check (similar to location webhook)
    auth_header = request.headers.get('Authorization')
    if not auth_header:
        return jsonify({'error': 'Missing auth'}), 401
    
    token = auth_header.replace('Bearer ', '')
    user_email = validate_token(token)
    
    if not user_email:
        return jsonify({'error': 'Invalid token'}), 401
    
    # Parse request
    data = request.get_json()
    
    # Record event
    event_id = app_usage_db.record_event(
        user_email=user_email,
        device_id=data.get('device_id', 'unknown'),
        device_type=data['device_type'],
        device_os=data['device_os'],
        app_name=data['app_name'],
        bundle_id=data.get('bundle_id'),
        window_title=data.get('window_title'),
        event_type=data['event_type'],
        timestamp=data['timestamp']
    )
    
    return jsonify({'status': 'ok', 'event_id': event_id}), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5006)
```

---

## V8 Pattern Detection Integration (4-6 hours)

### Add to V8 Continuous Daemon

**File:** `v8_continuous_pattern_daemon.py` (enhancement)

```python
async def _check_app_usage_patterns(self) -> List[Dict]:
    """Check for app usage patterns"""
    insights = []
    
    try:
        from app_usage.app_usage_db import AppUsageDB
        
        app_db = AppUsageDB()
        user_email = 'simon@email.com'
        
        # 1. Detect daily routine deviations
        now = datetime.now()
        current_hour = now.hour
        
        # Check if user usually opens Slack at 9 AM
        slack_pattern = app_db.get_pattern(user_email, app_name='Slack', hour=9)
        
        if slack_pattern and current_hour == 9 and slack_pattern['confidence'] > 0.8:
            # Check if Slack was opened today
            slack_opened = app_db.check_app_opened_today(user_email, 'Slack')
            
            if not slack_opened:
                insights.append({
                    'pattern_id': f"app_routine_slack_{now.strftime('%Y%m%d')}",
                    'pattern_type': 'app_usage',
                    'message': f"💬 You usually start Slack at 9 AM - it's {now.strftime('%H:%M')} and you haven't opened it yet",
                    'confidence': slack_pattern['confidence'],
                    'priority': 2
                })
        
        # 2. Detect excessive app usage
        gmail_duration = app_db.get_todays_duration(user_email, 'Gmail')
        
        if gmail_duration > 7200:  # 2 hours
            insights.append({
                'pattern_id': f"app_excessive_gmail_{now.strftime('%Y%m%d')}",
                'pattern_type': 'app_usage',
                'message': f"📧 You've been in Gmail for {gmail_duration // 60} minutes today - time for a break?",
                'confidence': 1.0,
                'priority': 2
            })
        
        # 3. Detect workflow sequences
        # Example: User always opens Google Docs before client meetings
        upcoming_meetings = app_db.get_upcoming_meetings(user_email, hours=1)
        
        if upcoming_meetings:
            meeting = upcoming_meetings[0]
            
            # Check if user usually opens Docs before this type of meeting
            prep_pattern = app_db.get_meeting_prep_pattern(user_email, meeting['type'])
            
            if prep_pattern and 'Google Docs' in prep_pattern['apps']:
                docs_opened = app_db.check_app_opened_recently(user_email, 'Google Docs', minutes=30)
                
                if not docs_opened:
                    insights.append({
                        'pattern_id': f"meeting_prep_{meeting['id']}",
                        'pattern_type': 'workflow',
                        'message': f"📝 Meeting prep: You usually spend 15 min in Google Docs before {meeting['title']} - want to start now?",
                        'confidence': prep_pattern['confidence'],
                        'priority': 1
                    })
    
    except ImportError:
        pass
    except Exception as e:
        print(f"    ⚠️  App usage pattern check failed: {e}", flush=True)
    
    return insights
```

---

## Example Patterns Detected

### 1. Daily Routine Deviation
```
Pattern: Open Slack at 9:00 AM ±15 min (Mon-Fri)
Confidence: 0.92

Current time: 9:30 AM
Slack status: Not opened

Insight: "You usually start Slack at 9 AM - it's 9:30 and you haven't opened it yet"
```

### 2. Excessive App Usage
```
Pattern: Gmail usage averages 60 min/day
Current: 120 minutes today
Threshold: 2× average

Insight: "You've been in Gmail for 2 hours - time for a break?"
```

### 3. Workflow Sequence
```
Pattern: Before client meetings, user opens:
1. Google Calendar (review agenda)
2. Google Docs (15 min prep)
3. Zoom (2 min before)

Current: Client meeting in 30 min, Google Docs not opened

Insight: "Meeting prep: You usually spend 15 min in Docs before client calls"
```

### 4. Context Switching
```
Pattern: User switches between Slack + Gmail 20× per hour
Average: 5× per hour

Insight: "High context switching detected (20×/hour vs 5× avg) - enable focus mode?"
```

---

## Privacy & Security

### Data Collection
- **What:** App name, bundle ID, window title (optional), duration
- **What NOT:** Screenshots, typed content, passwords, private data
- **Storage:** User's private VM only
- **Sharing:** Never (not even with Transmogrifier)

### User Controls
- View all tracked apps
- Pause tracking anytime
- Delete all usage data
- Exclude specific apps (e.g., password managers)
- Disable window title tracking

### Compliance
- GDPR: Right to access, delete, export
- CCPA: Opt-in consent required
- Privacy policy: Clear explanation

---

## Effort Summary

| Component | Platform | Hours |
|-----------|----------|-------|
| **Desktop Agent** | macOS | 6-8 |
| **Desktop Agent** | Windows | 6-8 |
| **Desktop Agent** | Linux | 4-6 |
| **Mobile Tracker** | iOS | 4-6 |
| **Mobile Tracker** | Android | 4-6 |
| **Backend** | Database + Webhook | 6-8 |
| **V8 Integration** | Pattern detection | 4-6 |
| **Total** | | **34-48 hours** |

**Simplified (macOS + iOS only):** 20-28 hours

---

## Timeline

**Week 1: Desktop (macOS only)**
- Days 1-2: macOS agent (Swift)
- Day 3: Backend database + webhook
- Day 4-5: V8 integration

**Week 2: Mobile (iOS only)**
- Days 1-2: iOS ScreenTime tracker
- Day 3: Testing + deployment
- Days 4-5: Pattern tuning

**Total: 2 weeks (20-28 hours for macOS + iOS only)**

---

## ROI Analysis

**Development cost:** 20-28 hours @ $150/hr = $3,000-4,200

**Revenue impact:**
- Basic tier: $15/mo
- Pro tier (location + app usage): $25/mo
- **Upsell: $10/mo per user**

**Break-even:** 300-420 user-months = 30 users for 10 months

**Target:** 100 Pro users = $1,000/mo additional revenue

**Payback:** ~3-4 months

---

## Recommendation

**Start with macOS + iOS only (20-28 hours)**

**Why:**
1. Most Transmogrifier users likely use Mac (target audience)
2. iOS ScreenTime API is mature
3. Windows/Android add complexity
4. Test with smaller scope first

**Defer Windows/Linux/Android until:**
- 50+ Pro tier users on macOS/iOS
- Users explicitly ask for Windows support
- Proven value of app usage tracking

**Timeline:**
- Build macOS + iOS: 2-3 weeks
- Launch Pro tier with location + app usage: Q3 2026
- Add Windows/Android: Q4 2026 if demanded

---

## Next Steps

1. **Decide:** Build app usage tracking or defer to Q4 2026?
2. **If now:** Start with macOS agent (simplest platform)
3. **If later:** Ship Basic tier + location tracking first

**Recommendation:** Defer until location tracking is validated. Don't build two major features simultaneously - increases risk and delays launch.

**Priority order:**
1. Ship Basic tier (email/calendar) - May 2026
2. Add location tracking (Pro tier) - Q3 2026
3. Add app usage tracking (Pro tier enhancement) - Q4 2026

**Build one premium feature at a time, validate, then add next.**
