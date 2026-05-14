-- Extend context.db for intelligence layer features
-- Run: sqlite3 context.db < extend_context_db.sql

-- Unified contacts (master records)
CREATE TABLE IF NOT EXISTS unified_contacts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    primary_name TEXT NOT NULL,
    primary_email TEXT,
    phone TEXT,
    company TEXT,
    role TEXT,
    relationship TEXT,
    is_vip BOOLEAN DEFAULT 0,
    importance_score REAL DEFAULT 0.0,
    total_emails INTEGER DEFAULT 0,
    total_meetings INTEGER DEFAULT 0,
    first_contact TIMESTAMP,
    last_contact TIMESTAMP,
    notes TEXT,
    metadata TEXT,  -- JSON for additional fields
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Contact emails (one person → many emails)
CREATE TABLE IF NOT EXISTS contact_emails (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    unified_contact_id INTEGER NOT NULL,
    email TEXT NOT NULL UNIQUE,
    is_primary BOOLEAN DEFAULT 0,
    source TEXT,  -- 'google', 'microsoft', 'email_headers', 'icloud'
    source_account TEXT,  -- which account this came from
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (unified_contact_id) REFERENCES unified_contacts(id)
);

-- Communication events (detailed logs for relationship scoring)
CREATE TABLE IF NOT EXISTS communication_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT NOT NULL,
    event_type TEXT NOT NULL,  -- email_sent, email_received, meeting_attended
    subject TEXT,
    timestamp TIMESTAMP NOT NULL,
    response_time_minutes INTEGER,  -- for replies
    is_group BOOLEAN DEFAULT 0,
    metadata TEXT,  -- JSON
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Dynamic relationship scores (calculated from events)
CREATE TABLE IF NOT EXISTS dynamic_relationship_scores (
    email TEXT PRIMARY KEY,
    importance_score REAL DEFAULT 0.0,
    recency_score REAL DEFAULT 0.0,
    frequency_score REAL DEFAULT 0.0,
    responsiveness_score REAL DEFAULT 0.0,
    meeting_score REAL DEFAULT 0.0,
    
    -- Stats
    total_emails_sent INTEGER DEFAULT 0,
    total_emails_received INTEGER DEFAULT 0,
    total_meetings INTEGER DEFAULT 0,
    avg_response_time_minutes REAL,
    last_contact TIMESTAMP,
    first_contact TIMESTAMP,
    
    -- Adaptive weights (learned per user)
    weight_recency REAL DEFAULT 0.25,
    weight_frequency REAL DEFAULT 0.30,
    weight_responsiveness REAL DEFAULT 0.25,
    weight_meeting REAL DEFAULT 0.20,
    
    calculated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Follow-up suggestions
CREATE TABLE IF NOT EXISTS follow_up_suggestions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT NOT NULL,
    suggestion_type TEXT NOT NULL,  -- no_contact, slow_reply, missed_meeting
    days_since_contact INTEGER,
    importance_score REAL,
    message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    dismissed_at TIMESTAMP,
    acted_on_at TIMESTAMP
);

-- Task actions (user feedback for learning)
CREATE TABLE IF NOT EXISTS task_actions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id INTEGER NOT NULL,
    action TEXT NOT NULL,  -- confirmed, dismissed, completed
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (task_id) REFERENCES tasks(id)
);

-- Add confidence field to existing tasks table (if not exists)
ALTER TABLE tasks ADD COLUMN confidence REAL DEFAULT 0.7;
ALTER TABLE tasks ADD COLUMN status TEXT DEFAULT 'pending';  -- pending, confirmed, dismissed

-- Indexes
CREATE INDEX IF NOT EXISTS idx_contact_emails_email ON contact_emails(email);
CREATE INDEX IF NOT EXISTS idx_contact_emails_unified ON contact_emails(unified_contact_id);
CREATE INDEX IF NOT EXISTS idx_unified_contacts_name ON unified_contacts(primary_name);
CREATE INDEX IF NOT EXISTS idx_unified_contacts_importance ON unified_contacts(importance_score DESC);
CREATE INDEX IF NOT EXISTS idx_comm_events_email ON communication_events(email);
CREATE INDEX IF NOT EXISTS idx_comm_events_timestamp ON communication_events(timestamp);
CREATE INDEX IF NOT EXISTS idx_relationship_scores_importance ON dynamic_relationship_scores(importance_score DESC);
CREATE INDEX IF NOT EXISTS idx_follow_ups_email ON follow_up_suggestions(email);
CREATE INDEX IF NOT EXISTS idx_task_actions_task_id ON task_actions(task_id);
