# Mobile Observer Implementation Plan

**Status:** BLOCKED - Requires OpenClaw nodes infrastructure  
**Date:** 2026-04-08  
**Estimated effort:** 8-12 hours once nodes API available

---

## Current Blockers

### 1. No OpenClaw Nodes API
**Problem:** Mobile observer needs to invoke commands on iOS/Android devices, but:
- No paired nodes exist (`openclaw status` shows "LaunchAgent not installed")
- No nodes API documentation found in workspace
- No examples of nodes invocation in codebase

**What we need:**
```python
# Hypothetical nodes API
from openclaw.nodes import NodesClient

client = NodesClient()
devices = client.list_devices()
result = client.invoke(
    node_id='iphone-123',
    command='get_screentime_data',
    params={'date': 'today'}
)
```

### 2. Mobile Apps Need ScreenTime/UsageStats Integration
**iOS Requirements:**
- FamilyControls framework integration
- DeviceActivity API for app usage
- Screen recording capability (requires user permission)
- Background task to sync data to gateway

**Android Requirements:**
- UsageStatsManager API
- Foreground service for monitoring
- Screen recording via MediaProjection API
- Sync service to gateway

**Current state:** OpenClaw iOS/Android apps may not have these capabilities

---

## What Exists Now

### Scaffolding Files
1. `ios_observer.py` - Python wrapper with mock data
2. `android_observer.py` - Python wrapper with mock data
3. Privacy controls defined
4. Data structures designed

### What Works
- Privacy configuration (allowed apps, work hours, retention policies)
- Mock data flows (demonstrating the API shape)
- Pattern detection logic (would work once real data flows)

---

## Implementation Path

### Phase 1: OpenClaw Nodes API (2-3 hours)
**Prerequisites:**
- Understand OpenClaw's node pairing mechanism
- Find/create nodes API documentation
- Test basic node invocation

**Deliverables:**
- Working nodes client in Python
- Ability to list paired devices
- Ability to invoke commands on devices

### Phase 2: iOS ScreenTime Integration (3-4 hours)
**Work in iOS app:**
1. Request FamilyControls permission
2. Integrate DeviceActivity framework
3. Create background task to collect usage data
4. Add command handler for `get_screentime_data`
5. Sync to gateway via nodes API

**Work in Python:**
1. Update `ios_observer.py` to call real nodes API
2. Parse returned ScreenTime data
3. Filter by privacy controls
4. Store in patterns database

### Phase 3: Android UsageStats Integration (3-4 hours)
**Work in Android app:**
1. Request UsageStats permission
2. Create foreground service for monitoring
3. Collect app usage data
4. Add command handler for `get_usage_stats`
5. Sync to gateway

**Work in Python:**
1. Update `android_observer.py` to call real nodes API
2. Parse returned usage data
3. Apply privacy filters
4. Store in patterns database

### Phase 4: Screen Recording (Optional, 2-3 hours)
**For detailed workflow analysis:**
1. iOS: Add screen recording via ReplayKit
2. Android: Add via MediaProjection
3. On-demand recording for high-usage apps
4. Local OCR on device (privacy-preserving)
5. Only sync extracted activities, not raw video

---

## Alternative: Webhook-Based Approach

**If nodes API doesn't exist, use webhooks:**

### iOS/Android App Changes
1. Apps periodically POST usage data to gateway endpoint
2. Gateway receives JSON payloads
3. Python observer polls gateway endpoint for new data

**Advantages:**
- Doesn't require nodes API
- Simpler architecture
- Apps control data flow

**Implementation:**
```python
# Gateway endpoint: POST /api/v8/mobile_activity
# Payload: {device_id, app_usage, timestamp}

# Observer polls for new data:
observer.poll_gateway_endpoint()
observer.process_new_activities()
```

**Estimated effort:** 4-6 hours (faster than nodes approach)

---

## Minimum Viable Mobile Observer

**Without full ScreenTime integration, we could:**

### Option A: Manual Log Export
User exports ScreenTime data from Settings → Screen Time → See All Activity
- User shares JSON/CSV export
- Observer parses exported file
- No real-time monitoring but still useful

**Effort:** 2-3 hours

### Option B: iOS Shortcuts Integration
Create iOS Shortcut to:
- Query ScreenTime data
- Save to iCloud Drive
- Observer reads from iCloud (like MacroFactor pattern)

**Effort:** 2-3 hours

---

## Recommendation

**For now: DEFER mobile observer until infrastructure ready**

**Reasons:**
1. No nodes API available (blocking)
2. Mobile apps may need significant updates
3. Alternative approaches (manual export, shortcuts) are hacky

**Better use of time:**
1. ✅ Desktop observer is working (done)
2. Validate desktop observer with real use cases
3. Let V8 prove value with desktop patterns first
4. Build mobile observer when clear use case emerges

**Timeline:**
- Desktop observer: Proven now
- Mobile infrastructure: Wait for nodes API (~Q2 2026?)
- Mobile observer: Build when infrastructure ready (~Q3 2026)

---

## If You Insist on Building Now

**Fastest path (4-6 hours):**

1. **Use webhook approach** (skip nodes API)
2. **Add to iOS app** (2 hours):
   - Background task to collect ScreenTime data
   - POST to gateway endpoint every hour
3. **Add to Android app** (2 hours):
   - UsageStats collection
   - POST to gateway endpoint
4. **Update Python observer** (2 hours):
   - Poll gateway endpoint
   - Process incoming data
   - Apply privacy filters

**But honestly:** This is building infrastructure for uncertain value. Desktop observer is working—use that first, prove V8's value, then justify mobile work.

---

**Status:** WAITING FOR NODES API OR CLEAR USE CASE  
**Next step:** Ask Simon if mobile observation is actually needed or if desktop is sufficient
