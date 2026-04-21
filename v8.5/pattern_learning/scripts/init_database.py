#!/usr/bin/env python3
"""
V8.5 Pattern Learning Database Initialization

Initialize all tables and seed with sample data.
"""

import sqlite3
import os
import sys

# Add parent dir to path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

def init_database(db_path: str = None):
    """
    Initialize pattern learning database.
    
    Creates:
    - All required tables
    - Indexes for performance
    - Sample aggregate patterns
    - Views for analytics
    """
    if not db_path:
        # Default to v8.5_pattern_learning directory
        script_dir = os.path.dirname(os.path.abspath(__file__))
        parent_dir = os.path.dirname(script_dir)
        db_path = os.path.join(parent_dir, 'pattern_learning.db')
    
    print(f"Initializing database: {db_path}")
    
    # Read schema file
    schema_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'database_schema.sql')
    
    if not os.path.exists(schema_path):
        print(f"ERROR: Schema file not found: {schema_path}")
        return False
    
    with open(schema_path, 'r') as f:
        schema_sql = f.read()
    
    # Connect and execute schema
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Execute schema (creates all tables, indexes, views)
        cursor.executescript(schema_sql)
        conn.commit()
        
        print("✓ Tables created")
        print("✓ Indexes created")
        print("✓ Views created")
        print("✓ Sample data inserted")
        
        # Verify tables
        cursor.execute("""
            SELECT name FROM sqlite_master WHERE type='table' ORDER BY name
        """)
        tables = [row[0] for row in cursor.fetchall()]
        
        print(f"\nCreated {len(tables)} tables:")
        for table in tables:
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            count = cursor.fetchone()[0]
            print(f"  - {table} ({count} rows)")
        
        conn.close()
        
        print(f"\n✓ Database initialized successfully: {db_path}")
        return True
        
    except sqlite3.Error as e:
        print(f"ERROR initializing database: {e}")
        conn.close()
        return False


def create_sample_user(db_path: str, user_id: str = 'demo_user'):
    """
    Create sample user with realistic interaction data.
    """
    from datetime import datetime, timedelta
    import random
    import json
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    print(f"\nCreating sample user: {user_id}")
    
    # Create user profile
    cursor.execute("""
        INSERT OR REPLACE INTO user_profiles
        (user_id, email, industry, role, timezone, created_at, last_active)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        user_id,
        f"{user_id}@example.com",
        'tech',
        'individual_contributor',
        'America/Los_Angeles',
        datetime.now().isoformat(),
        datetime.now().isoformat()
    ))
    
    # Generate sample interactions
    now = datetime.now()
    
    # Email interactions
    vip_senders = ['boss@company.com', 'client@important.com', 'ceo@company.com']
    regular_senders = ['coworker1@company.com', 'coworker2@company.com', 'newsletter@spam.com']
    
    for days_ago in range(30):
        day = now - timedelta(days=days_ago)
        
        # 5-10 emails per day
        for _ in range(random.randint(5, 10)):
            sender = random.choice(vip_senders + regular_senders)
            is_vip = sender in vip_senders
            
            # Email received
            email_id = f"email_{days_ago}_{_}"
            cursor.execute("""
                INSERT INTO user_interactions
                (user_id, event_type, event_data, timestamp, session_id)
                VALUES (?, ?, ?, ?, ?)
            """, (
                user_id,
                'email_received',
                json.dumps({
                    'email_id': email_id,
                    'sender': sender,
                    'subject': 'URGENT: Task' if random.random() < 0.3 else 'Regular email',
                    'action': 'received'
                }),
                (day + timedelta(hours=random.randint(9, 17))).isoformat(),
                f"session_{days_ago}_{_}"
            ))
            
            # Email opened (80% of time)
            if random.random() < 0.8:
                cursor.execute("""
                    INSERT INTO user_interactions
                    (user_id, event_type, event_data, timestamp, session_id)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    user_id,
                    'email_opened',
                    json.dumps({
                        'email_id': email_id,
                        'sender': sender,
                        'action': 'opened'
                    }),
                    (day + timedelta(hours=random.randint(9, 17), minutes=random.randint(5, 30))).isoformat(),
                    f"session_{days_ago}_{_}"
                ))
            
            # Email replied (VIP: 90%, regular: 30%)
            reply_chance = 0.9 if is_vip else 0.3
            if random.random() < reply_chance:
                # VIP: fast reply (< 2 hours), regular: slow (< 24 hours)
                reply_delay_hours = random.uniform(0.5, 2.0) if is_vip else random.uniform(2.0, 24.0)
                
                cursor.execute("""
                    INSERT INTO user_interactions
                    (user_id, event_type, event_data, timestamp, session_id)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    user_id,
                    'email_replied',
                    json.dumps({
                        'email_id': email_id,
                        'sender': sender,
                        'action': 'replied'
                    }),
                    (day + timedelta(hours=reply_delay_hours)).isoformat(),
                    f"session_{days_ago}_{_}"
                ))
    
    # Meeting interactions
    for days_ago in range(30):
        day = now - timedelta(days=days_ago)
        
        # 2-4 meetings per day
        for _ in range(random.randint(2, 4)):
            meeting_id = f"meeting_{days_ago}_{_}"
            meeting_title = random.choice(['Daily Standup', '1:1 with Manager', 'Team Sync', 'Company All-hands'])
            
            # Meeting scheduled
            cursor.execute("""
                INSERT INTO user_interactions
                (user_id, event_type, event_data, timestamp)
                VALUES (?, ?, ?, ?)
            """, (
                user_id,
                'meeting_scheduled',
                json.dumps({
                    'meeting_id': meeting_id,
                    'meeting_title': meeting_title,
                    'action': 'scheduled'
                }),
                (day + timedelta(hours=random.randint(10, 15))).isoformat()
            ))
            
            # Meeting joined (90% of time, sometimes late)
            if random.random() < 0.9:
                late_minutes = random.randint(-2, 5) if 'All-hands' not in meeting_title else random.randint(0, 10)
                
                cursor.execute("""
                    INSERT INTO user_interactions
                    (user_id, event_type, event_data, timestamp)
                    VALUES (?, ?, ?, ?)
                """, (
                    user_id,
                    'meeting_joined',
                    json.dumps({
                        'meeting_id': meeting_id,
                        'meeting_title': meeting_title,
                        'action': 'joined',
                        'duration_minutes': 30
                    }),
                    (day + timedelta(hours=random.randint(10, 15), minutes=late_minutes)).isoformat()
                ))
            else:
                # Skipped
                cursor.execute("""
                    INSERT INTO user_interactions
                    (user_id, event_type, event_data, timestamp)
                    VALUES (?, ?, ?, ?)
                """, (
                    user_id,
                    'meeting_skipped',
                    json.dumps({
                        'meeting_id': meeting_id,
                        'meeting_title': meeting_title,
                        'action': 'skipped'
                    }),
                    (day + timedelta(hours=random.randint(10, 15))).isoformat()
                ))
    
    # App activity
    for days_ago in range(30):
        day = now - timedelta(days=days_ago)
        
        # 5-10 app opens per day
        for _ in range(random.randint(5, 10)):
            cursor.execute("""
                INSERT INTO user_interactions
                (user_id, event_type, event_data, timestamp)
                VALUES (?, ?, ?, ?)
            """, (
                user_id,
                'app_opened',
                json.dumps({'action': 'opened'}),
                (day + timedelta(hours=random.randint(8, 18))).isoformat()
            ))
            
            # Notification check (within 15-30 min of app open)
            cursor.execute("""
                INSERT INTO user_interactions
                (user_id, event_type, event_data, timestamp)
                VALUES (?, ?, ?, ?)
            """, (
                user_id,
                'notification_checked',
                json.dumps({'action': 'notification_checked'}),
                (day + timedelta(hours=random.randint(8, 18), minutes=random.randint(15, 30))).isoformat()
            ))
    
    conn.commit()
    
    # Count interactions
    cursor.execute("""
        SELECT COUNT(*) FROM user_interactions WHERE user_id = ?
    """, (user_id,))
    count = cursor.fetchone()[0]
    
    conn.close()
    
    print(f"✓ Created sample user with {count} interactions")
    return True


def analyze_sample_user(db_path: str, user_id: str = 'demo_user'):
    """
    Analyze sample user patterns.
    """
    from pattern_learning.pattern_analyzer import UserPatternAnalyzer
    import json
    
    print(f"\nAnalyzing patterns for: {user_id}")
    
    analyzer = UserPatternAnalyzer(db_path)
    
    # Analyze and save patterns
    analyzer.save_patterns(user_id)
    
    # Get patterns
    patterns = analyzer.get_patterns(user_id)
    
    if patterns:
        print("\nEmail Patterns:")
        print(f"  VIP Senders: {patterns['email_patterns'].get('vip_senders', [])}")
        print(f"  Urgent Keywords: {patterns['email_patterns'].get('urgent_keywords', [])}")
        print(f"  Avg Response Time: {patterns['email_patterns'].get('avg_response_time_hours', 'N/A')} hours")
        print(f"  Confidence: {patterns['email_patterns'].get('confidence_score', 0.0):.2f}")
        
        print("\nCalendar Patterns:")
        print(f"  Prep Time Needed: {patterns['calendar_patterns'].get('prep_time_needed_minutes', 'N/A')} min")
        print(f"  Late Meetings: {patterns['calendar_patterns'].get('late_meetings', [])}")
        print(f"  Skip Meetings: {patterns['calendar_patterns'].get('skip_meetings', [])}")
        print(f"  Confidence: {patterns['calendar_patterns'].get('confidence_score', 0.0):.2f}")
        
        print("\nWork Patterns:")
        print(f"  Deep Work Hours: {patterns['work_patterns'].get('deep_work_hours', [])}")
        print(f"  Productivity Peak: {patterns['work_patterns'].get('productivity_peak', 'N/A')}")
        print(f"  Confidence: {patterns['work_patterns'].get('confidence_score', 0.0):.2f}")
        
        print(f"\n✓ Overall Confidence: {patterns['confidence_score']:.2f}")
    else:
        print("ERROR: No patterns found")


if __name__ == '__main__':
    import sys
    
    db_path = sys.argv[1] if len(sys.argv) > 1 else None
    
    print("=" * 60)
    print("V8.5 Pattern Learning Database Initialization")
    print("=" * 60)
    
    # Initialize database
    success = init_database(db_path)
    
    if not success:
        sys.exit(1)
    
    # Get actual db path
    if not db_path:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        parent_dir = os.path.dirname(script_dir)
        db_path = os.path.join(parent_dir, 'pattern_learning.db')
    
    # Create sample user
    create_sample_user(db_path, 'demo_user')
    
    # Analyze sample user
    analyze_sample_user(db_path, 'demo_user')
    
    print("\n" + "=" * 60)
    print("✓ Database initialization complete!")
    print("=" * 60)
    print(f"\nDatabase location: {db_path}")
    print("\nNext steps:")
    print("  1. Test pattern analyzer: python pattern_learning/pattern_analyzer.py")
    print("  2. Test feedback loop: python pattern_learning/feedback_loop.py")
    print("  3. Test personalized recs: python recommendations/personalized_generator.py")
    print("  4. Start API server: python api/server.py")
