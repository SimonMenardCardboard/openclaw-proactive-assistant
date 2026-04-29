# Transmogrifier: Fast-Path Onboarding (4-6 Hour Recommendations)

**Goal:** New user gets first proactive recommendations within 4-6 hours of signup

---

## Current State (No Bootstrap)

**Timeline without fast-path:**
- Day 1: OAuth → data collection starts
- Day 2-7: V8 pattern learning (needs 7+ days of data)
- Day 8+: First recommendations

**Problem:** 7+ days is too long for initial value demonstration

---

## Proposed: Aggressive Bootstrap Mode

### Phase 1: Onboarding (0-15 min)

**User provides:**
1. OAuth for email (Gmail/Outlook/etc)
2. OAuth for calendar (Google/Outlook/etc)
3. Basic preferences (work hours, notification preferences)

**System immediately:**
```python
# On successful OAuth completion
async def on_user_oauth_complete(user_id: str, credentials: Dict):
    """Trigger aggressive bootstrap mode."""
    
    # 1. Start historical data pull (background)
    await pull_email_history(user_id, days=30)
    await pull_calendar_history(user_id, days=30)
    
    # 2. Run fast pattern detection (lightweight V8)
    await run_bootstrap_analysis(user_id)
    
    # 3. Queue first recommendations
    await queue_bootstrap_recommendations(user_id)
    
    # 4. Enable real-time monitoring
    await enable_webhooks(user_id)
```

### Phase 2: Historical Analysis (15 min - 2 hours)

**Fast pattern detection using last 30 days:**

```python
def run_bootstrap_analysis(user_id: str):
    """Lightweight pattern detection for immediate insights."""
    
    # Email patterns (15 min)
    email_patterns = {
        'avg_response_time': analyze_response_times(last_30_days),
        'email_volume_by_hour': count_emails_by_hour(),
        'top_senders': get_frequent_contacts(top=10),
        'unread_pile_up': detect_inbox_buildup(),
    }
    
    # Calendar patterns (10 min)
    calendar_patterns = {
        'meeting_density': meetings_per_day_avg(),
        'focus_time_gaps': find_unscheduled_blocks(),
        'recurring_meetings': extract_recurring_patterns(),
        'meeting_duration_avg': avg_meeting_length(),
    }
    
    # Work patterns (5 min - heuristics)
    work_patterns = {
        'work_hours_start': earliest_email_sent(),
        'work_hours_end': latest_email_sent(),
        'weekend_work': weekend_email_count(),
        'after_hours_meetings': meetings_after_6pm_count(),
    }
    
    return {
        'email': email_patterns,
        'calendar': calendar_patterns,
        'work': work_patterns,
        'confidence': 'bootstrap'  # Lower confidence than 7-day learning
    }
```

### Phase 3: First Recommendations (2-4 hours)

**Immediate low-hanging fruit (high confidence even with 30-day data):**

```python
def queue_bootstrap_recommendations(user_id: str, patterns: Dict):
    """Queue safe, high-value recommendations based on historical data."""
    
    recommendations = []
    
    # Email-based recommendations
    if patterns['email']['avg_response_time'] > 24:
        recommendations.append({
            'type': 'email_response_speed',
            'message': f"📧 You respond to emails in {patterns['email']['avg_response_time']} hours on average.\n\nWant me to prioritize urgent emails and remind you of follow-ups?",
            'priority': 2,
            'actions': ['enable_email_triage', 'enable_followup_reminders']
        })
    
    if patterns['email']['unread_pile_up'] > 50:
        recommendations.append({
            'type': 'inbox_cleanup',
            'message': f"📬 You have {patterns['email']['unread_pile_up']} unread emails piling up.\n\nWant me to help triage and auto-archive newsletters?",
            'priority': 3,
            'actions': ['enable_auto_archive', 'weekly_inbox_review']
        })
    
    # Calendar-based recommendations
    if patterns['calendar']['focus_time_gaps'] < 2:
        recommendations.append({
            'type': 'focus_time_blocking',
            'message': f"📅 You have less than 2 hours/day of unscheduled focus time.\n\nWant me to block 9-11 AM daily for deep work?",
            'priority': 1,
            'actions': ['block_focus_time']
        })
    
    if patterns['calendar']['meeting_density'] > 6:
        recommendations.append({
            'type': 'meeting_overload',
            'message': f"⏰ You average {patterns['calendar']['meeting_density']} meetings/day.\n\nWant tips on async alternatives and meeting reduction?",
            'priority': 2,
            'actions': ['meeting_audit', 'async_alternatives']
        })
    
    # Work-life balance recommendations
    if patterns['work']['after_hours_meetings'] > 3:
        recommendations.append({
            'type': 'work_life_boundary',
            'message': f"🌙 You have {patterns['work']['after_hours_meetings']} meetings/week after 6 PM.\n\nWant me to protect your evenings and suggest reschedules?",
            'priority': 1,
            'actions': ['protect_evenings', 'suggest_reschedule']
        })
    
    # Queue all recommendations (stagger delivery over 4-6 hours)
    for i, rec in enumerate(recommendations):
        delay_minutes = i * 90  # 1.5 hour spacing
        queue_delayed(user_id, rec, delay_minutes)
```

### Phase 4: Real-Time Monitoring (4+ hours)

**Enable V6/V7 immediately:**

```python
def enable_real_time_monitoring(user_id: str):
    """Start V6/V7 daemons for new user."""
    
    # V6: Proactive daemon
    subprocess.Popen([
        'python3',
        '~/.openclaw/workspace/integrations/proactive_daemon/daemon_v2.py',
        '--user-id', user_id,
        '--mode', 'bootstrap'  # More aggressive early on
    ])
    
    # V7: Self-healing
    # (shares daemon across all users, just register user)
    register_user_for_self_healing(user_id)
    
    # COS: Enable webhooks
    enable_gmail_push(user_id)
    enable_calendar_watch(user_id)
```

### Phase 5: V8 Learning (Background, 7+ days)

**V8 runs in background, improves over time:**

```python
def start_v8_learning(user_id: str):
    """Start V8 meta-learning in background."""
    
    # V8 learns incrementally
    # Day 1-7: Bootstrap recommendations (from Phase 3)
    # Day 7-14: Higher confidence patterns emerge
    # Day 14+: Full V8 autonomous recommendations
    
    # No user-facing change, just better recommendations over time
    schedule_v8_analysis(user_id, interval='daily')
```

---

## Implementation: Onboarding Flow

### Step 1: OAuth Complete Webhook

```python
# In oauth_manager.py
@app.route('/oauth/callback/<provider>')
def oauth_callback(provider: str):
    """Handle OAuth completion."""
    
    user_id = session['user_id']
    credentials = exchange_code_for_token(request.args['code'])
    
    # Save credentials
    save_user_credentials(user_id, provider, credentials)
    
    # TRIGGER BOOTSTRAP
    if is_first_oauth(user_id):
        trigger_bootstrap_onboarding(user_id)
    
    return redirect('/dashboard?onboarding=success')
```

### Step 2: Bootstrap Orchestrator

```python
# New file: transmogrifier/onboarding/bootstrap.py
import asyncio
from datetime import datetime, timedelta

async def trigger_bootstrap_onboarding(user_id: str):
    """Orchestrate fast-path onboarding."""
    
    logger.info(f"Starting bootstrap for {user_id}")
    
    # 1. Historical pull (background, 15-30 min)
    asyncio.create_task(pull_historical_data(user_id))
    
    # 2. Wait for enough data (15 min)
    await asyncio.sleep(15 * 60)
    
    # 3. Run fast analysis (10 min)
    patterns = await run_bootstrap_analysis(user_id)
    
    # 4. Queue recommendations (immediate)
    await queue_bootstrap_recommendations(user_id, patterns)
    
    # 5. Enable real-time monitoring
    await enable_real_time_monitoring(user_id)
    
    # 6. Send welcome message
    await send_welcome_message(user_id, patterns)
    
    # 7. Start V8 background learning
    start_v8_learning(user_id)
    
    logger.info(f"Bootstrap complete for {user_id}")
```

### Step 3: Welcome Message

```python
def send_welcome_message(user_id: str, patterns: Dict):
    """Send personalized welcome with first insights."""
    
    message = f"""🎉 Welcome to Transmogrifier!

I've analyzed your last 30 days and found some quick wins:

📧 **Email:** {patterns['email']['avg_response_time']:.1f} hour avg response time
📅 **Calendar:** {patterns['calendar']['meeting_density']} meetings/day average
⏰ **Work hours:** {patterns['work']['work_hours_start']} - {patterns['work']['work_hours_end']}

**First recommendations coming in next 4-6 hours.**

I'm also monitoring your inbox and calendar in real-time now. You'll get proactive suggestions as patterns emerge.

Questions? Just ask! 🐯
"""
    
    send_notification(user_id, message)
```

---

## Timeline: User Perspective

**Minute 0:** Complete OAuth
**Minute 15:** "Analyzing your last 30 days..." notification
**Hour 1:** First recommendation (most critical issue)
**Hour 2.5:** Second recommendation
**Hour 4:** Third recommendation
**Hour 5.5:** Fourth recommendation
**Day 2+:** Real-time V6/V7 recommendations
**Day 7+:** Full V8 autonomous recommendations

---

## Technical Requirements

### Database Schema

```sql
-- Track onboarding state
CREATE TABLE user_onboarding (
    user_id TEXT PRIMARY KEY,
    oauth_completed_at TIMESTAMP,
    historical_pull_started_at TIMESTAMP,
    historical_pull_completed_at TIMESTAMP,
    bootstrap_analysis_completed_at TIMESTAMP,
    first_recommendation_sent_at TIMESTAMP,
    onboarding_completed_at TIMESTAMP,
    status TEXT -- 'oauth', 'pulling', 'analyzing', 'recommending', 'complete'
);

-- Store bootstrap patterns (temporary, 30 days)
CREATE TABLE bootstrap_patterns (
    user_id TEXT,
    pattern_type TEXT,
    pattern_data JSONB,
    confidence TEXT, -- 'bootstrap', 'learning', 'confident'
    created_at TIMESTAMP,
    expires_at TIMESTAMP
);
```

### Background Jobs

```python
# Add to cron or task queue
BOOTSTRAP_JOBS = [
    {
        'name': 'historical_data_pull',
        'trigger': 'on_oauth_complete',
        'duration': '15-30 min',
        'priority': 'high'
    },
    {
        'name': 'bootstrap_analysis',
        'trigger': 'after_historical_pull',
        'duration': '10 min',
        'priority': 'high'
    },
    {
        'name': 'recommendation_queue',
        'trigger': 'after_analysis',
        'duration': 'immediate',
        'priority': 'high'
    }
]
```

### API Endpoints

```python
# For user dashboard
@app.get('/api/onboarding/status')
def get_onboarding_status(user_id: str):
    """Get current onboarding progress."""
    return {
        'status': 'analyzing',
        'progress': 65,  # percentage
        'current_step': 'Analyzing email patterns',
        'eta_minutes': 25,
        'recommendations_queued': 3
    }
```

---

## Edge Cases

### 1. Limited Historical Data

**Problem:** User has <7 days of emails/calendar
**Solution:** 
- Still run bootstrap with available data
- Lower confidence thresholds
- More conservative recommendations
- Notify user: "I'll improve as I learn more"

### 2. OAuth Partial (Email Only)

**Problem:** User only grants email access, not calendar
**Solution:**
- Run email-only bootstrap
- Recommend calendar connection for more insights
- Still deliver value from email patterns

### 3. Multiple Account Connections

**Problem:** User adds second account after onboarding
**Solution:**
- Re-run bootstrap for new account
- Merge patterns across accounts
- Update existing recommendations

---

## Success Metrics

**Onboarding quality:**
- Time to first recommendation: <4 hours (target: 2 hours)
- Bootstrap recommendations accepted: >60%
- User satisfaction: >4/5 stars

**Long-term engagement:**
- Users still active after 30 days: >80%
- Recommendations accepted over time: increasing trend
- User-initiated questions/requests: >5/month

---

## Comparison: Bootstrap vs Standard V8

| Metric | Bootstrap (30-day) | Standard V8 (7-day) |
|--------|-------------------|---------------------|
| **Time to first rec** | 2-4 hours | 7+ days |
| **Confidence** | Medium (60-70%) | High (80-90%) |
| **Data source** | Historical batch | Real-time stream |
| **Recommendation types** | Low-hanging fruit | Deep patterns |
| **User value** | Immediate | Sustained |

**Key insight:** Bootstrap gets users value FAST, V8 improves quality over time.

---

## Future: Federated Bootstrap (V8.5)

**With Hobbes Control:**

When new user onboards, query federated patterns:
```python
def get_federated_bootstrap_insights(user_id: str, user_profile: Dict):
    """Get cross-user insights for faster bootstrap."""
    
    # Query Hobbes Control for similar users
    insights = hobbes_control.query_patterns({
        'role': user_profile['role'],  # e.g., 'software_engineer'
        'company_size': user_profile['company_size'],
        'industry': user_profile['industry']
    })
    
    # Use network patterns as baseline
    # User's personal patterns refine over time
    return insights
```

**Result:** Day 1 recommendations based on network learning + user's 30-day history = even higher quality bootstrap.

---

## Implementation Priority

**Phase 1 (MVP - Week 1):**
1. ✅ Historical data pull on OAuth
2. ✅ Bootstrap analysis pipeline
3. ✅ First 3-4 recommendations queued
4. ✅ Welcome message

**Phase 2 (Polish - Week 2):**
5. Onboarding progress UI
6. Confidence scoring
7. Recommendation staggering
8. Edge case handling

**Phase 3 (V8.5 Integration - Month 2):**
9. Federated bootstrap insights
10. Cross-user pattern matching
11. Network-enhanced recommendations

---

## Summary

**Current:** 7+ days to first recommendation (too slow)

**Proposed:** 2-4 hours to first recommendation via:
1. 30-day historical analysis (not just 7-day real-time)
2. Aggressive pattern detection on bootstrap
3. Queue safe, high-value recommendations immediately
4. V8 improves quality over time (transparent to user)

**User experience:**
- Hour 1: First valuable insight
- Day 1: Multiple recommendations
- Week 1: Real-time monitoring active
- Month 1: Full V8 autonomous intelligence

**Key principle:** Get users value FAST, improve quality over TIME.
