#!/usr/bin/env python3
"""
Unit Tests for Pattern Analyzer

Tests:
- VIP detection accuracy
- Urgent keyword learning
- Response time prediction
- Meeting pattern detection
- Pattern confidence scoring
"""

import unittest
import sqlite3
import json
import os
import sys
from datetime import datetime, timedelta

# Add parent dir to path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from pattern_learning.pattern_analyzer import UserPatternAnalyzer

class TestPatternAnalyzer(unittest.TestCase):
    """Test suite for pattern analyzer."""
    
    @classmethod
    def setUpClass(cls):
        """Set up test database."""
        cls.db_path = ':memory:'  # In-memory database for tests
        cls.analyzer = UserPatternAnalyzer(cls.db_path)
        cls._create_schema()
        cls._insert_test_data()
    
    @classmethod
    def _create_schema(cls):
        """Create test schema."""
        conn = sqlite3.connect(cls.db_path)
        cursor = conn.cursor()
        
        cursor.executescript("""
            CREATE TABLE user_interactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                event_data JSON,
                timestamp TEXT NOT NULL,
                session_id TEXT,
                device_id TEXT
            );
            
            CREATE TABLE user_patterns (
                user_id TEXT PRIMARY KEY,
                email_patterns JSON,
                calendar_patterns JSON,
                work_patterns JSON,
                last_updated TEXT,
                confidence_score REAL,
                interaction_count INTEGER
            );
            
            CREATE TABLE user_profiles (
                user_id TEXT PRIMARY KEY,
                email TEXT,
                industry TEXT,
                role TEXT,
                timezone TEXT,
                created_at TEXT NOT NULL,
                last_active TEXT
            );
        """)
        
        conn.commit()
        conn.close()
    
    @classmethod
    def _insert_test_data(cls):
        """Insert test interaction data."""
        conn = sqlite3.connect(cls.db_path)
        cursor = conn.cursor()
        
        user_id = 'test_user'
        now = datetime.now()
        
        # VIP sender pattern: boss@company.com (fast responses)
        for i in range(20):
            day = now - timedelta(days=i)
            email_id = f"vip_email_{i}"
            
            # Email received
            cursor.execute("""
                INSERT INTO user_interactions
                (user_id, event_type, event_data, timestamp)
                VALUES (?, ?, ?, ?)
            """, (
                user_id,
                'email_received',
                json.dumps({
                    'email_id': email_id,
                    'sender': 'boss@company.com',
                    'subject': 'URGENT Task' if i % 3 == 0 else 'Regular email',
                    'action': 'received'
                }),
                day.isoformat()
            ))
            
            # Fast reply (within 1 hour)
            cursor.execute("""
                INSERT INTO user_interactions
                (user_id, event_type, event_data, timestamp)
                VALUES (?, ?, ?, ?)
            """, (
                user_id,
                'email_replied',
                json.dumps({
                    'email_id': email_id,
                    'sender': 'boss@company.com',
                    'action': 'replied'
                }),
                (day + timedelta(hours=0.5)).isoformat()
            ))
        
        # Regular sender pattern: coworker@company.com (slow responses)
        for i in range(20):
            day = now - timedelta(days=i)
            email_id = f"regular_email_{i}"
            
            cursor.execute("""
                INSERT INTO user_interactions
                (user_id, event_type, event_data, timestamp)
                VALUES (?, ?, ?, ?)
            """, (
                user_id,
                'email_received',
                json.dumps({
                    'email_id': email_id,
                    'sender': 'coworker@company.com',
                    'subject': 'FYI update',
                    'action': 'received'
                }),
                day.isoformat()
            ))
            
            # Slow reply (within 24 hours)
            if i % 2 == 0:  # Only reply to half
                cursor.execute("""
                    INSERT INTO user_interactions
                    (user_id, event_type, event_data, timestamp)
                    VALUES (?, ?, ?, ?)
                """, (
                    user_id,
                    'email_replied',
                    json.dumps({
                        'email_id': email_id,
                        'sender': 'coworker@company.com',
                        'action': 'replied'
                    }),
                    (day + timedelta(hours=12)).isoformat()
                ))
        
        # Ignored sender pattern: newsletter@spam.com (never replied)
        for i in range(10):
            day = now - timedelta(days=i)
            email_id = f"spam_email_{i}"
            
            cursor.execute("""
                INSERT INTO user_interactions
                (user_id, event_type, event_data, timestamp)
                VALUES (?, ?, ?, ?)
            """, (
                user_id,
                'email_received',
                json.dumps({
                    'email_id': email_id,
                    'sender': 'newsletter@spam.com',
                    'subject': 'Weekly newsletter',
                    'action': 'received'
                }),
                day.isoformat()
            ))
        
        # Meeting patterns
        for i in range(20):
            day = now - timedelta(days=i)
            meeting_id = f"meeting_{i}"
            
            # Daily standup (often late)
            cursor.execute("""
                INSERT INTO user_interactions
                (user_id, event_type, event_data, timestamp)
                VALUES (?, ?, ?, ?)
            """, (
                user_id,
                'meeting_scheduled',
                json.dumps({
                    'meeting_id': meeting_id,
                    'meeting_title': 'Daily Standup',
                    'action': 'scheduled'
                }),
                (day + timedelta(hours=10)).isoformat()
            ))
            
            # Join late (3+ minutes)
            cursor.execute("""
                INSERT INTO user_interactions
                (user_id, event_type, event_data, timestamp)
                VALUES (?, ?, ?, ?)
            """, (
                user_id,
                'meeting_joined',
                json.dumps({
                    'meeting_id': meeting_id,
                    'meeting_title': 'Daily Standup',
                    'action': 'joined',
                    'duration_minutes': 15
                }),
                (day + timedelta(hours=10, minutes=5)).isoformat()
            ))
        
        conn.commit()
        conn.close()
    
    # ========================================================================
    # Email Pattern Tests
    # ========================================================================
    
    def test_vip_detection(self):
        """Test VIP sender detection."""
        patterns = self.analyzer.analyze_email_patterns('test_user')
        
        # boss@company.com should be detected as VIP (fast responses)
        self.assertIn('boss@company.com', patterns['vip_senders'])
        
        # coworker should not be VIP (slow responses)
        self.assertNotIn('coworker@company.com', patterns['vip_senders'])
    
    def test_ignored_sender_detection(self):
        """Test ignored sender detection."""
        patterns = self.analyzer.analyze_email_patterns('test_user')
        
        # newsletter should be ignored (never replied)
        self.assertIn('newsletter@spam.com', patterns['ignored_senders'])
    
    def test_urgent_keyword_detection(self):
        """Test urgent keyword learning."""
        patterns = self.analyzer.analyze_email_patterns('test_user')
        
        # URGENT should be detected in subjects
        self.assertIn('URGENT', patterns['urgent_keywords'])
    
    def test_response_time_calculation(self):
        """Test average response time calculation."""
        patterns = self.analyzer.analyze_email_patterns('test_user')
        
        # VIP sender (boss) should have fast response time (< 2 hours)
        self.assertIn('boss@company.com', patterns['response_time_by_sender'])
        self.assertLess(patterns['response_time_by_sender']['boss@company.com'], 2.0)
    
    def test_confidence_score(self):
        """Test confidence score increases with interactions."""
        patterns = self.analyzer.analyze_email_patterns('test_user')
        
        # With 50+ interactions, confidence should be > 0.5
        self.assertGreater(patterns['confidence_score'], 0.5)
    
    # ========================================================================
    # Calendar Pattern Tests
    # ========================================================================
    
    def test_late_meeting_detection(self):
        """Test late meeting pattern detection."""
        patterns = self.analyzer.analyze_calendar_patterns('test_user')
        
        # Daily Standup should be detected as late meeting
        self.assertIn('Daily Standup', patterns['late_meetings'])
    
    def test_prep_time_calculation(self):
        """Test meeting prep time calculation."""
        patterns = self.analyzer.analyze_calendar_patterns('test_user')
        
        # Prep time should be > 0
        self.assertGreater(patterns['prep_time_needed_minutes'], 0)
    
    # ========================================================================
    # Priority Prediction Tests
    # ========================================================================
    
    def test_priority_prediction_vip(self):
        """Test priority prediction for VIP sender."""
        email = {
            'type': 'email',
            'sender': 'boss@company.com',
            'subject': 'URGENT: Review needed'
        }
        
        priority = self.analyzer.predict_priority('test_user', email)
        
        # VIP + urgent keyword = high priority
        self.assertGreater(priority, 0.7)
    
    def test_priority_prediction_ignored(self):
        """Test priority prediction for ignored sender."""
        email = {
            'type': 'email',
            'sender': 'newsletter@spam.com',
            'subject': 'Weekly update'
        }
        
        priority = self.analyzer.predict_priority('test_user', email)
        
        # Ignored sender = low priority
        self.assertLess(priority, 0.3)
    
    # ========================================================================
    # Pattern Save/Load Tests
    # ========================================================================
    
    def test_save_and_load_patterns(self):
        """Test pattern persistence."""
        # Save patterns
        self.analyzer.save_patterns('test_user')
        
        # Load patterns
        patterns = self.analyzer.get_patterns('test_user')
        
        self.assertIsNotNone(patterns)
        self.assertIn('email_patterns', patterns)
        self.assertIn('calendar_patterns', patterns)
        self.assertIn('work_patterns', patterns)
        self.assertGreater(patterns['confidence_score'], 0.0)


if __name__ == '__main__':
    unittest.main(verbosity=2)
