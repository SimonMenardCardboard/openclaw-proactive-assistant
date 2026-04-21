-- V8.5 Pattern Learning Database Schema
-- Complete schema for personalized AI assistant

-- ============================================================================
-- User Interactions Table
-- Track ALL user actions for pattern learning
-- ============================================================================

CREATE TABLE IF NOT EXISTS user_interactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    event_type TEXT NOT NULL,  -- recommendation_shown, recommendation_clicked, email_opened, etc.
    event_data JSON,           -- Context-specific data
    timestamp TEXT NOT NULL,
    session_id TEXT,           -- Group interactions by app session
    device_id TEXT,
    
    -- Indexes for fast querying
    FOREIGN KEY (user_id) REFERENCES user_profiles(user_id)
);

CREATE INDEX IF NOT EXISTS idx_interactions_user_time ON user_interactions(user_id, timestamp);
CREATE INDEX IF NOT EXISTS idx_interactions_type ON user_interactions(event_type);
CREATE INDEX IF NOT EXISTS idx_interactions_session ON user_interactions(session_id);

-- ============================================================================
-- User Patterns Table
-- Learned behavioral patterns per user
-- ============================================================================

CREATE TABLE IF NOT EXISTS user_patterns (
    user_id TEXT PRIMARY KEY,
    
    -- Email patterns
    email_patterns JSON,       -- VIP senders, urgent keywords, response times
    
    -- Calendar patterns
    calendar_patterns JSON,    -- Meeting prep time, skip patterns, focus time
    
    -- Work patterns
    work_patterns JSON,        -- Deep work hours, distraction patterns, productivity
    
    -- Metadata
    last_updated TEXT NOT NULL,
    confidence_score REAL DEFAULT 0.5,  -- 0.0 - 1.0 (how confident in patterns)
    interaction_count INTEGER DEFAULT 0, -- Number of interactions analyzed
    
    FOREIGN KEY (user_id) REFERENCES user_profiles(user_id)
);

CREATE INDEX IF NOT EXISTS idx_patterns_updated ON user_patterns(last_updated);

-- ============================================================================
-- Aggregate Patterns Table
-- Cross-user patterns (federated learning)
-- ============================================================================

CREATE TABLE IF NOT EXISTS aggregate_patterns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pattern_type TEXT NOT NULL,    -- universal, industry, role
    industry TEXT,                 -- legal, tech, finance, healthcare, etc.
    role TEXT,                     -- executive, IC, manager, etc.
    pattern_data JSON NOT NULL,    -- Aggregated pattern insights
    sample_size INTEGER DEFAULT 0, -- Number of users contributing
    last_updated TEXT NOT NULL,
    confidence_score REAL DEFAULT 0.5
);

CREATE INDEX IF NOT EXISTS idx_aggregate_type ON aggregate_patterns(pattern_type);
CREATE INDEX IF NOT EXISTS idx_aggregate_industry ON aggregate_patterns(industry);
CREATE INDEX IF NOT EXISTS idx_aggregate_role ON aggregate_patterns(role);

-- ============================================================================
-- Recommendation Effectiveness Table
-- Track recommendation quality and user actions
-- ============================================================================

CREATE TABLE IF NOT EXISTS recommendation_effectiveness (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    recommendation_id TEXT NOT NULL,
    recommendation_type TEXT,      -- email, calendar, task, etc.
    priority_score REAL,           -- 0.0 - 1.0
    
    -- Lifecycle timestamps
    shown_at TEXT NOT NULL,
    clicked_at TEXT,
    dismissed_at TEXT,
    snoozed_at TEXT,
    completed_at TEXT,
    
    -- Effectiveness metrics
    time_to_action INTEGER,        -- Seconds from shown to action
    effectiveness_score REAL,      -- 0.0 - 1.0 (calculated post-action)
    user_feedback TEXT,            -- Optional user rating/comment
    
    FOREIGN KEY (user_id) REFERENCES user_profiles(user_id)
);

CREATE INDEX IF NOT EXISTS idx_effectiveness_user ON recommendation_effectiveness(user_id);
CREATE INDEX IF NOT EXISTS idx_effectiveness_type ON recommendation_effectiveness(recommendation_type);
CREATE INDEX IF NOT EXISTS idx_effectiveness_shown ON recommendation_effectiveness(shown_at);

-- ============================================================================
-- A/B Testing Table
-- Track experiments and variants
-- ============================================================================

CREATE TABLE IF NOT EXISTS ab_tests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    test_name TEXT NOT NULL,
    variant TEXT NOT NULL,         -- control, variant_a, variant_b, etc.
    user_id TEXT NOT NULL,
    started_at TEXT NOT NULL,
    ended_at TEXT,
    
    -- Results
    success_count INTEGER DEFAULT 0,
    failure_count INTEGER DEFAULT 0,
    effectiveness_score REAL,
    
    FOREIGN KEY (user_id) REFERENCES user_profiles(user_id)
);

CREATE INDEX IF NOT EXISTS idx_ab_test_name ON ab_tests(test_name);
CREATE INDEX IF NOT EXISTS idx_ab_user ON ab_tests(user_id);

-- ============================================================================
-- Pattern Override Table
-- Manual corrections from users
-- ============================================================================

CREATE TABLE IF NOT EXISTS pattern_overrides (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    override_type TEXT NOT NULL,   -- vip_sender, urgent_keyword, ignore_sender, etc.
    override_value TEXT NOT NULL,
    created_at TEXT NOT NULL,
    expires_at TEXT,               -- Optional expiration
    
    FOREIGN KEY (user_id) REFERENCES user_profiles(user_id)
);

CREATE INDEX IF NOT EXISTS idx_override_user ON pattern_overrides(user_id);
CREATE INDEX IF NOT EXISTS idx_override_type ON pattern_overrides(override_type);

-- ============================================================================
-- Pattern Learning Metrics Table
-- Track pattern learning quality over time
-- ============================================================================

CREATE TABLE IF NOT EXISTS pattern_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    metric_type TEXT NOT NULL,     -- vip_accuracy, priority_accuracy, response_time_accuracy
    metric_value REAL NOT NULL,    -- 0.0 - 1.0
    sample_size INTEGER,
    measured_at TEXT NOT NULL,
    
    FOREIGN KEY (user_id) REFERENCES user_profiles(user_id)
);

CREATE INDEX IF NOT EXISTS idx_metrics_user ON pattern_metrics(user_id);
CREATE INDEX IF NOT EXISTS idx_metrics_type ON pattern_metrics(metric_type);
CREATE INDEX IF NOT EXISTS idx_metrics_time ON pattern_metrics(measured_at);

-- ============================================================================
-- User Profiles Table (if not exists from main system)
-- Basic user information for pattern learning
-- ============================================================================

CREATE TABLE IF NOT EXISTS user_profiles (
    user_id TEXT PRIMARY KEY,
    email TEXT,
    industry TEXT,                 -- legal, tech, finance, healthcare, etc.
    role TEXT,                     -- executive, IC, manager, etc.
    timezone TEXT,
    created_at TEXT NOT NULL,
    last_active TEXT
);

-- ============================================================================
-- Views for Analytics
-- ============================================================================

-- View: User pattern summary
CREATE VIEW IF NOT EXISTS v_user_pattern_summary AS
SELECT 
    up.user_id,
    up.confidence_score,
    up.interaction_count,
    up.last_updated,
    COUNT(DISTINCT ui.event_type) as event_types_tracked,
    COUNT(ui.id) as total_interactions,
    AVG(re.effectiveness_score) as avg_effectiveness
FROM user_patterns up
LEFT JOIN user_interactions ui ON up.user_id = ui.user_id
LEFT JOIN recommendation_effectiveness re ON up.user_id = re.user_id
GROUP BY up.user_id;

-- View: Recommendation effectiveness by type
CREATE VIEW IF NOT EXISTS v_recommendation_effectiveness AS
SELECT 
    recommendation_type,
    COUNT(*) as total_shown,
    SUM(CASE WHEN clicked_at IS NOT NULL THEN 1 ELSE 0 END) as clicked,
    SUM(CASE WHEN dismissed_at IS NOT NULL THEN 1 ELSE 0 END) as dismissed,
    AVG(effectiveness_score) as avg_effectiveness,
    AVG(time_to_action) as avg_time_to_action
FROM recommendation_effectiveness
GROUP BY recommendation_type;

-- View: Pattern learning progress
CREATE VIEW IF NOT EXISTS v_pattern_learning_progress AS
SELECT 
    user_id,
    metric_type,
    AVG(metric_value) as avg_value,
    MIN(measured_at) as first_measured,
    MAX(measured_at) as last_measured,
    COUNT(*) as measurement_count
FROM pattern_metrics
GROUP BY user_id, metric_type;

-- ============================================================================
-- Sample Data for Testing
-- ============================================================================

-- Insert sample aggregate patterns (universal)
INSERT OR IGNORE INTO aggregate_patterns (pattern_type, industry, role, pattern_data, sample_size, last_updated, confidence_score)
VALUES 
    ('universal', NULL, NULL, '{"vip_indicators": ["CEO", "founder", "director", "president"], "urgent_keywords": ["URGENT", "EOD", "ASAP", "deadline", "critical"]}', 1000, datetime('now'), 0.9),
    ('industry', 'legal', NULL, '{"urgent_keywords": ["filing", "deadline", "motion", "court", "discovery"], "meeting_prep_time": 30}', 150, datetime('now'), 0.8),
    ('industry', 'tech', NULL, '{"urgent_keywords": ["outage", "bug", "incident", "P0", "SEV1"], "meeting_prep_time": 5}', 500, datetime('now'), 0.85),
    ('role', NULL, 'executive', '{"email_volume_tolerance": "high", "meeting_priority": "high", "delegate_threshold": 0.6}', 200, datetime('now'), 0.75),
    ('role', NULL, 'individual_contributor', '{"focus_time_importance": "high", "meeting_priority": "low", "deep_work_hours": ["9-11", "14-16"]}', 800, datetime('now'), 0.8);

-- ============================================================================
-- Indexes for Performance
-- ============================================================================

-- Additional composite indexes for common queries
CREATE INDEX IF NOT EXISTS idx_interactions_user_type_time ON user_interactions(user_id, event_type, timestamp);
CREATE INDEX IF NOT EXISTS idx_effectiveness_user_type ON recommendation_effectiveness(user_id, recommendation_type);
