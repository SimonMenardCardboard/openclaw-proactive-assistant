# V8.5 Pattern Learning System - Deployment Guide

**Complete deployment guide for production Chief of Staff AI**

---

## Prerequisites

- Python 3.8+
- SQLite 3
- Mobile app with event tracking instrumentation
- Backend API server
- Push notification service (APNs/FCM)

---

## Phase 1: Database Setup (Day 1)

### 1.1 Initialize Database

```bash
cd ~/.openclaw/workspace/integrations/intelligence/v8.5_pattern_learning

# Initialize database and create tables
python scripts/init_database.py

# Verify installation
sqlite3 pattern_learning.db "SELECT name FROM sqlite_master WHERE type='table';"
```

**Expected output:**
```
user_interactions
user_patterns
aggregate_patterns
recommendation_effectiveness
ab_tests
pattern_overrides
pattern_metrics
user_profiles
```

### 1.2 Verify Sample Data

```bash
# Check sample user
sqlite3 pattern_learning.db "SELECT COUNT(*) FROM user_interactions WHERE user_id='demo_user';"

# Should show 300-500 interactions
```

---

## Phase 2: Pattern Learning Integration (Days 2-3)

### 2.1 Integrate with Existing System

**Backend Integration:**

```python
# In your existing Chief of Staff backend
from v8.5_pattern_learning.pattern_learning.pattern_analyzer import UserPatternAnalyzer
from v8.5_pattern_learning.pattern_learning.feedback_loop import FeedbackLoop
from v8.5_pattern_learning.recommendations.personalized_generator import PersonalizedRecommendationGenerator

# Initialize components
db_path = '/path/to/pattern_learning.db'
analyzer = UserPatternAnalyzer(db_path)
feedback = FeedbackLoop(db_path)
generator = PersonalizedRecommendationGenerator(db_path)

# Example: Generate personalized recommendation
email = {
    'id': 'email_123',
    'sender': 'boss@company.com',
    'subject': 'Q2 Budget Review',
    'received_at': datetime.now(),
    'preview': '...'
}

rec = generator.generate_email_recommendation(user_id, email)

# Send recommendation via push notification
send_push_notification(user_id, rec)

# When user interacts
feedback.record_feedback(user_id, rec['recommendation_id'], 'clicked')
```

### 2.2 Set Up Pattern Analysis Cron

**Run pattern analysis every 6 hours:**

```bash
# Add to crontab
0 */6 * * * python /path/to/v8.5_pattern_learning/scripts/analyze_all_users.py
```

**Create script: `scripts/analyze_all_users.py`**

```python
#!/usr/bin/env python3
from pattern_learning.pattern_analyzer import UserPatternAnalyzer
import sqlite3

db_path = '/path/to/pattern_learning.db'
analyzer = UserPatternAnalyzer(db_path)

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Get all active users
cursor.execute("SELECT DISTINCT user_id FROM user_interactions")
users = [row[0] for row in cursor.fetchall()]
conn.close()

print(f"Analyzing patterns for {len(users)} users...")

for user_id in users:
    try:
        analyzer.save_patterns(user_id)
        print(f"✓ {user_id}")
    except Exception as e:
        print(f"✗ {user_id}: {e}")

print("Pattern analysis complete")
```

---

## Phase 3: Mobile App Instrumentation (Days 4-7)

### 3.1 iOS Event Tracking

**Add to your iOS app:**

```swift
// EventTracker.swift
import Foundation

class EventTracker {
    static let shared = EventTracker()
    private let apiEndpoint = "https://your-api.com/api/interactions/track"
    
    func trackEvent(eventType: String, eventData: [String: Any]) {
        let event = [
            "user_id": getCurrentUserId(),
            "event_type": eventType,
            "event_data": eventData,
            "timestamp": ISO8601DateFormatter().string(from: Date()),
            "session_id": getCurrentSessionId(),
            "device_id": getDeviceId()
        ]
        
        // Send to backend (batched)
        EventBatchUploader.shared.addEvent(event)
    }
    
    // Track recommendation shown
    func trackRecommendationShown(recommendationId: String, type: String, priority: Double) {
        trackEvent(eventType: "recommendation_shown", eventData: [
            "recommendation_id": recommendationId,
            "type": type,
            "priority": priority
        ])
    }
    
    // Track recommendation clicked
    func trackRecommendationClicked(recommendationId: String) {
        trackEvent(eventType: "recommendation_clicked", eventData: [
            "recommendation_id": recommendationId
        ])
    }
    
    // Track email opened
    func trackEmailOpened(emailId: String, sender: String) {
        trackEvent(eventType: "email_opened", eventData: [
            "email_id": emailId,
            "sender": sender,
            "action": "opened"
        ])
    }
    
    // Track meeting joined
    func trackMeetingJoined(meetingId: String, title: String) {
        trackEvent(eventType: "meeting_joined", eventData: [
            "meeting_id": meetingId,
            "meeting_title": title,
            "action": "joined"
        ])
    }
}
```

**Usage in your UI:**

```swift
// When recommendation shown
EventTracker.shared.trackRecommendationShown(
    recommendationId: rec.id,
    type: rec.type,
    priority: rec.priority
)

// When user taps recommendation
EventTracker.shared.trackRecommendationClicked(recommendationId: rec.id)

// When email opened
EventTracker.shared.trackEmailOpened(emailId: email.id, sender: email.sender)
```

### 3.2 Android Event Tracking

**Similar implementation for Android:**

```kotlin
// EventTracker.kt
class EventTracker {
    companion object {
        val instance = EventTracker()
        private const val API_ENDPOINT = "https://your-api.com/api/interactions/track"
    }
    
    fun trackEvent(eventType: String, eventData: Map<String, Any>) {
        val event = mapOf(
            "user_id" to getCurrentUserId(),
            "event_type" to eventType,
            "event_data" to eventData,
            "timestamp" to Instant.now().toString(),
            "session_id" to getCurrentSessionId(),
            "device_id" to getDeviceId()
        )
        
        EventBatchUploader.instance.addEvent(event)
    }
    
    fun trackRecommendationShown(recommendationId: String, type: String, priority: Double) {
        trackEvent("recommendation_shown", mapOf(
            "recommendation_id" to recommendationId,
            "type" to type,
            "priority" to priority
        ))
    }
}
```

### 3.3 Backend API Endpoint

**Add to your backend:**

```python
# api/interaction_tracker.py
from flask import Flask, request, jsonify
import sqlite3
import json
from datetime import datetime

app = Flask(__name__)

@app.route('/api/interactions/track', methods=['POST'])
def track_interaction():
    """
    Track user interaction.
    
    POST /api/interactions/track
    {
        "user_id": "user_123",
        "event_type": "recommendation_clicked",
        "event_data": {...},
        "timestamp": "2026-04-20T10:00:00Z",
        "session_id": "session_456",
        "device_id": "device_789"
    }
    """
    data = request.json
    
    # Validate
    required = ['user_id', 'event_type', 'timestamp']
    if not all(k in data for k in required):
        return jsonify({'error': 'Missing required fields'}), 400
    
    # Insert into database
    conn = sqlite3.connect('pattern_learning.db')
    cursor = conn.cursor()
    
    cursor.execute("""
        INSERT INTO user_interactions
        (user_id, event_type, event_data, timestamp, session_id, device_id)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        data['user_id'],
        data['event_type'],
        json.dumps(data.get('event_data', {})),
        data['timestamp'],
        data.get('session_id'),
        data.get('device_id')
    ))
    
    conn.commit()
    conn.close()
    
    return jsonify({'status': 'success'}), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
```

---

## Phase 4: Federated Learning (Days 8-10)

### 4.1 Set Up Pattern Aggregation

**Run daily to aggregate patterns across users:**

```bash
# Add to crontab (daily at 3 AM)
0 3 * * * python /path/to/v8.5_pattern_learning/scripts/aggregate_patterns.py
```

**Create script: `scripts/aggregate_patterns.py`**

```python
#!/usr/bin/env python3
from pattern_learning.federated_learning import FederatedPatternLearning

db_path = '/path/to/pattern_learning.db'
fed_learning = FederatedPatternLearning(db_path)

print("Aggregating patterns across all users...")
fed_learning.aggregate_patterns()
print("✓ Pattern aggregation complete")
```

### 4.2 Bootstrap New Users

**When new user signs up:**

```python
from pattern_learning.federated_learning import FederatedPatternLearning

# Get user industry/role from signup form
industry = request.form.get('industry')  # e.g., 'tech', 'legal', 'finance'
role = request.form.get('role')  # e.g., 'executive', 'individual_contributor'

# Bootstrap with aggregate patterns
fed_learning = FederatedPatternLearning(db_path)
bootstrap_patterns = fed_learning.bootstrap_new_user(user_id, industry, role)

print(f"✓ New user bootstrapped with {industry} / {role} patterns")
```

---

## Phase 5: Testing & Validation (Days 11-12)

### 5.1 Run Unit Tests

```bash
# Run all tests
python -m unittest discover tests/

# Run specific test
python tests/test_pattern_analyzer.py
```

**Expected output:**
```
test_vip_detection ... ok
test_ignored_sender_detection ... ok
test_urgent_keyword_detection ... ok
test_response_time_calculation ... ok
test_confidence_score ... ok
test_late_meeting_detection ... ok
test_prep_time_calculation ... ok
test_priority_prediction_vip ... ok
test_priority_prediction_ignored ... ok
test_save_and_load_patterns ... ok

----------------------------------------------------------------------
Ran 10 tests in 0.523s

OK
```

### 5.2 Load Testing

**Test with 1000+ users:**

```python
# scripts/load_test.py
import concurrent.futures
from pattern_learning.pattern_analyzer import UserPatternAnalyzer

analyzer = UserPatternAnalyzer(db_path)

# Create 1000 fake users
users = [f"load_test_user_{i}" for i in range(1000)]

def analyze_user(user_id):
    analyzer.save_patterns(user_id)

# Parallel analysis
with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
    executor.map(analyze_user, users)

print("✓ Load test complete")
```

---

## Phase 6: Production Deployment (Days 13-14)

### 6.1 Deploy to Production

**Steps:**

1. **Backup existing data**
   ```bash
   sqlite3 production.db ".backup backup_$(date +%Y%m%d).db"
   ```

2. **Run migrations**
   ```bash
   python scripts/migrate_to_v8.5.py
   ```

3. **Initialize pattern learning tables**
   ```bash
   python scripts/init_database.py production.db
   ```

4. **Start pattern analysis service**
   ```bash
   python scripts/pattern_service.py &
   ```

5. **Deploy mobile app updates**
   - iOS: Submit to App Store
   - Android: Submit to Play Store

6. **Monitor metrics**
   ```bash
   python scripts/monitor_effectiveness.py
   ```

### 6.2 Monitoring

**Create dashboard: `scripts/monitor_effectiveness.py`**

```python
#!/usr/bin/env python3
from pattern_learning.feedback_loop import FeedbackLoop
import time

feedback = FeedbackLoop(db_path)

while True:
    # Get all active users
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT user_id FROM user_patterns")
    users = [row[0] for row in cursor.fetchall()]
    conn.close()
    
    print(f"\n=== Pattern Learning Metrics ({datetime.now()}) ===")
    
    for user_id in users[:10]:  # Top 10 users
        metrics = feedback.measure_effectiveness(user_id, days=7)
        print(f"\n{user_id}:")
        print(f"  Click Rate: {metrics['click_rate']:.1%}")
        print(f"  Effectiveness: {metrics['avg_effectiveness']:.2f}")
        print(f"  Improvement: {metrics.get('improvement_trend', 'N/A')}")
    
    time.sleep(3600)  # Update every hour
```

---

## Success Metrics

### Week 1 (Cold Start)
- ✅ Pattern detection started (confidence > 0.3)
- ✅ VIP senders identified
- ✅ Basic urgent keywords learned

### Week 2 (Learning)
- ✅ Pattern confidence > 0.5
- ✅ Response time predictions accurate within 30 min
- ✅ Meeting patterns detected

### Month 1 (Personalized)
- ✅ Recommendation click rate > 30% (vs 10% baseline)
- ✅ Pattern confidence > 0.7
- ✅ User satisfaction > 4.0/5

### Month 3 (Optimized)
- ✅ Click rate > 40%
- ✅ Pattern confidence > 0.8
- ✅ User satisfaction > 4.5/5
- ✅ 90% of users have useful patterns

---

## Troubleshooting

### Issue: Low Pattern Confidence

**Symptoms:** Confidence score < 0.4 after 1 week

**Solutions:**
1. Check interaction count: `SELECT COUNT(*) FROM user_interactions WHERE user_id=?`
2. Verify event tracking is working
3. Ensure mobile app is sending events
4. Check API endpoint logs

### Issue: VIP Detection Not Working

**Symptoms:** No VIP senders detected

**Solutions:**
1. Verify email reply events: `SELECT * FROM user_interactions WHERE event_type='email_replied'`
2. Check response time calculation
3. Lower VIP threshold temporarily

### Issue: High Memory Usage

**Symptoms:** Pattern analysis consuming too much RAM

**Solutions:**
1. Batch process users (100 at a time)
2. Run analysis during off-peak hours
3. Optimize SQL queries with indexes

---

## Maintenance

### Daily
- ✅ Monitor error logs
- ✅ Check event ingestion rate
- ✅ Verify pattern analysis cron runs

### Weekly
- ✅ Review effectiveness metrics
- ✅ Check pattern confidence trends
- ✅ A/B test new recommendation styles

### Monthly
- ✅ Backup database
- ✅ Archive old interactions (>90 days)
- ✅ Update aggregate patterns
- ✅ Review user feedback

---

## Support

For issues or questions:
- Check logs: `/var/log/pattern_learning/`
- Run diagnostics: `python scripts/diagnose.py`
- Contact: ai-team@yourcompany.com

---

**✓ Deployment complete! Your V8.5 pattern learning system is live.**
