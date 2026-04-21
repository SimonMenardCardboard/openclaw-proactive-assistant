#!/usr/bin/env python3
"""
V8.5 Pattern Learning REST API
Provides endpoints for mobile app to:
- Track user interactions
- Get personalized recommendations
- View learned patterns
- Manual pattern overrides
"""

import sys
import os
from pathlib import Path
from flask import Flask, request, jsonify
from flask_cors import CORS
import sqlite3
import json
from datetime import datetime, timedelta
import logging

# Add parent directory to path for imports
parent_dir = Path(__file__).parent.parent
sys.path.append(str(parent_dir))

from pattern_learning.pattern_analyzer import UserPatternAnalyzer
from pattern_learning.feedback_loop import FeedbackLoop
from pattern_learning.federated_learning import FederatedPatternLearning
from recommendations.personalized_generator import PersonalizedRecommendationGenerator
from recommendations.context_aware_delivery import ContextAwareDelivery

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
CORS(app)  # Enable CORS for mobile app

# Database path
DB_PATH = parent_dir / 'pattern_learning.db'

# Initialize V8.5 components
pattern_analyzer = UserPatternAnalyzer(str(DB_PATH))
feedback_loop = FeedbackLoop(str(DB_PATH))
federated_learning = FederatedPatternLearning(str(DB_PATH))
recommendation_generator = PersonalizedRecommendationGenerator(str(DB_PATH))
context_delivery = ContextAwareDelivery(str(DB_PATH))


# ============================================================================
# INTERACTION TRACKING
# ============================================================================

@app.route('/api/v8.5/interactions/track', methods=['POST'])
def track_interaction():
    """
    Track user interaction (mobile app → backend)
    
    Request body:
    {
        "user_id": "simon",
        "event_type": "email_opened",
        "event_data": {
            "email_id": "123",
            "sender": "vip@example.com",
            "subject": "Urgent: ...",
            ...
        },
        "timestamp": "2026-04-20T14:30:00Z",
        "session_id": "abc123",
        "device_id": "iphone_15_pro"
    }
    """
    try:
        data = request.json
        
        # Validate required fields
        required_fields = ['user_id', 'event_type', 'event_data']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'Missing required field: {field}'}), 400
        
        user_id = data['user_id']
        event_type = data['event_type']
        event_data = data['event_data']
        timestamp = data.get('timestamp', datetime.utcnow().isoformat())
        session_id = data.get('session_id')
        device_id = data.get('device_id')
        
        # Store in database
        conn = sqlite3.connect(str(DB_PATH))
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO user_interactions 
            (user_id, event_type, event_data, timestamp, session_id, device_id)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (user_id, event_type, json.dumps(event_data), timestamp, session_id, device_id))
        
        conn.commit()
        conn.close()
        
        logger.info(f"Tracked interaction: {event_type} for user {user_id}")
        
        return jsonify({
            'status': 'ok',
            'message': 'Interaction tracked successfully'
        }), 200
        
    except Exception as e:
        logger.error(f"Error tracking interaction: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/v8.5/interactions/batch', methods=['POST'])
def track_interactions_batch():
    """
    Track multiple interactions at once (efficient batching)
    
    Request body:
    {
        "user_id": "simon",
        "interactions": [
            {
                "event_type": "email_opened",
                "event_data": {...},
                "timestamp": "..."
            },
            ...
        ],
        "session_id": "abc123",
        "device_id": "iphone_15_pro"
    }
    """
    try:
        data = request.json
        user_id = data['user_id']
        interactions = data['interactions']
        session_id = data.get('session_id')
        device_id = data.get('device_id')
        
        conn = sqlite3.connect(str(DB_PATH))
        cursor = conn.cursor()
        
        for interaction in interactions:
            event_type = interaction['event_type']
            event_data = interaction['event_data']
            timestamp = interaction.get('timestamp', datetime.utcnow().isoformat())
            
            cursor.execute('''
                INSERT INTO user_interactions 
                (user_id, event_type, event_data, timestamp, session_id, device_id)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (user_id, event_type, json.dumps(event_data), timestamp, session_id, device_id))
        
        conn.commit()
        conn.close()
        
        logger.info(f"Tracked {len(interactions)} interactions for user {user_id}")
        
        return jsonify({
            'status': 'ok',
            'message': f'Tracked {len(interactions)} interactions successfully'
        }), 200
        
    except Exception as e:
        logger.error(f"Error tracking batch: {e}")
        return jsonify({'error': str(e)}), 500


# ============================================================================
# RECOMMENDATIONS
# ============================================================================

@app.route('/api/v8.5/recommendations/personalized', methods=['GET'])
def get_recommendations():
    """
    Get personalized recommendations (backend → mobile app)
    
    Query params:
    - user_id: User identifier
    - limit: Number of recommendations (default 10)
    - context: JSON string with current context (location, time, etc.)
    
    Response:
    {
        "recommendations": [
            {
                "id": "rec_123",
                "type": "meeting_prep",
                "priority": 0.95,
                "title": "Prepare for Legal Strategy Meeting",
                "description": "Meeting in 30 min with John (VIP)",
                "action": "open_calendar",
                "action_data": {...},
                "expires_at": "2026-04-20T15:00:00Z"
            },
            ...
        ],
        "context": {
            "location": "office",
            "time": "work_hours",
            "device": "iphone"
        }
    }
    """
    try:
        user_id = request.args.get('user_id')
        limit = int(request.args.get('limit', 10))
        context_str = request.args.get('context', '{}')
        context = json.loads(context_str)
        
        if not user_id:
            return jsonify({'error': 'Missing user_id'}), 400
        
        # For now, return demo recommendations
        # TODO: Implement full recommendation generation pipeline
        recommendations = [
            {
                "id": "rec_email_001",
                "type": "email",
                "priority": 0.9,
                "title": "High Priority: Legal Strategy Meeting Prep",
                "description": "Meeting with John (VIP) in 30 min. Prepare talking points based on previous discussions.",
                "action": {
                    "type": "open_email",
                    "data": {"email_id": "12345"}
                },
                "context": {
                    "sender": "john@company.com",
                    "vip": True,
                    "meeting_soon": True
                },
                "created_at": datetime.utcnow().isoformat(),
                "expires_at": (datetime.utcnow() + timedelta(hours=1)).isoformat()
            },
            {
                "id": "rec_calendar_001",
                "type": "calendar",
                "priority": 0.75,
                "title": "Meeting Tomorrow: Q2 Budget Review",
                "description": "Review budget documents before tomorrow's meeting at 2 PM.",
                "action": {
                    "type": "open_calendar",
                    "data": {"event_id": "67890"}
                },
                "context": {
                    "meeting_time": "tomorrow",
                    "requires_prep": True
                },
                "created_at": datetime.utcnow().isoformat(),
                "expires_at": (datetime.utcnow() + timedelta(days=1)).isoformat()
            },
            {
                "id": "rec_insight_001",
                "type": "insight",
                "priority": 0.5,
                "title": "Productivity Insight",
                "description": "You're most productive between 9-11 AM. Block this time for deep work.",
                "action": {
                    "type": "view_insights",
                    "data": {}
                },
                "context": {
                    "based_on": "30_days_of_data"
                },
                "created_at": datetime.utcnow().isoformat()
            }
        ][:limit]
        
        logger.info(f"Generated {len(recommendations)} demo recommendations for user {user_id}")
        
        return jsonify({
            'recommendations': recommendations,
            'context': context,
            'generated_at': datetime.utcnow().isoformat()
        }), 200
        
    except Exception as e:
        logger.error(f"Error generating recommendations: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/v8.5/recommendations/feedback', methods=['POST'])
def record_feedback():
    """
    Record recommendation feedback (clicked, dismissed, snoozed, completed)
    
    Request body:
    {
        "user_id": "simon",
        "recommendation_id": "rec_123",
        "action": "clicked",  # clicked | dismissed | snoozed | completed
        "context": {
            "location": "office",
            "device": "iphone",
            ...
        }
    }
    """
    try:
        data = request.json
        user_id = data['user_id']
        rec_id = data['recommendation_id']
        action = data['action']
        context = data.get('context', {})
        
        # Record feedback in feedback loop
        feedback_loop.record_feedback(
            user_id=user_id,
            recommendation_id=rec_id,
            action=action,
            context=context
        )
        
        logger.info(f"Recorded feedback: {action} for rec {rec_id} by user {user_id}")
        
        return jsonify({
            'status': 'ok',
            'message': 'Feedback recorded successfully'
        }), 200
        
    except Exception as e:
        logger.error(f"Error recording feedback: {e}")
        return jsonify({'error': str(e)}), 500


# ============================================================================
# PATTERN VIEWING & MANAGEMENT
# ============================================================================

@app.route('/api/v8.5/patterns/<user_id>', methods=['GET'])
def get_patterns(user_id):
    """
    Get learned patterns for user
    
    Response:
    {
        "user_id": "simon",
        "email_patterns": {
            "vip_senders": ["boss@example.com", "client@big.com"],
            "urgent_keywords": ["urgent", "asap", "deadline"],
            "avg_response_time_hours": 2.5,
            ...
        },
        "calendar_patterns": {
            "prep_time_needed_minutes": 15,
            "late_meetings_threshold_minutes": 5,
            "focus_time_blocks": ["9:00-11:00", "14:00-16:00"],
            ...
        },
        "work_patterns": {
            "deep_work_hours": ["9:00-11:00"],
            "productivity_peak": "morning",
            "notification_quiet_hours": ["23:00-08:00"],
            ...
        },
        "last_updated": "2026-04-20T14:30:00Z",
        "confidence_score": 0.85
    }
    """
    try:
        # Get all patterns
        email_patterns = pattern_analyzer.analyze_email_patterns(user_id)
        calendar_patterns = pattern_analyzer.analyze_calendar_patterns(user_id)
        work_patterns = pattern_analyzer.analyze_work_patterns(user_id)
        
        # Get metadata
        conn = sqlite3.connect(str(DB_PATH))
        cursor = conn.cursor()
        cursor.execute('''
            SELECT last_updated, confidence_score
            FROM user_patterns
            WHERE user_id = ?
        ''', (user_id,))
        row = cursor.fetchone()
        conn.close()
        
        last_updated = row[0] if row else datetime.utcnow().isoformat()
        confidence_score = row[1] if row else 0.0
        
        return jsonify({
            'user_id': user_id,
            'email_patterns': email_patterns,
            'calendar_patterns': calendar_patterns,
            'work_patterns': work_patterns,
            'last_updated': last_updated,
            'confidence_score': confidence_score
        }), 200
        
    except Exception as e:
        logger.error(f"Error getting patterns: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/v8.5/patterns/<user_id>/override', methods=['POST'])
def override_pattern(user_id):
    """
    Manual pattern override (user corrections)
    
    Request body:
    {
        "pattern_type": "email_patterns",
        "pattern_key": "vip_senders",
        "action": "add",  # add | remove | replace
        "value": "newvip@example.com"
    }
    """
    try:
        data = request.json
        pattern_type = data['pattern_type']
        pattern_key = data['pattern_key']
        action = data['action']
        value = data['value']
        
        # Record override in database
        conn = sqlite3.connect(str(DB_PATH))
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO pattern_overrides
            (user_id, pattern_type, pattern_key, action, value, timestamp)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (user_id, pattern_type, pattern_key, action, json.dumps(value), datetime.utcnow().isoformat()))
        
        conn.commit()
        conn.close()
        
        # Apply override immediately
        pattern_analyzer.apply_override(user_id, pattern_type, pattern_key, action, value)
        
        logger.info(f"Applied pattern override: {pattern_type}.{pattern_key} for user {user_id}")
        
        return jsonify({
            'status': 'ok',
            'message': 'Pattern override applied successfully'
        }), 200
        
    except Exception as e:
        logger.error(f"Error applying override: {e}")
        return jsonify({'error': str(e)}), 500


# ============================================================================
# EFFECTIVENESS & METRICS
# ============================================================================

@app.route('/api/v8.5/effectiveness/<user_id>', methods=['GET'])
def get_effectiveness(user_id):
    """
    Get recommendation effectiveness metrics
    
    Query params:
    - days: Number of days to analyze (default 7)
    
    Response:
    {
        "user_id": "simon",
        "period_days": 7,
        "metrics": {
            "total_recommendations": 150,
            "clicked": 45,
            "dismissed": 30,
            "snoozed": 20,
            "completed": 25,
            "click_rate": 0.30,
            "completion_rate": 0.17,
            "effectiveness_score": 0.75
        },
        "improvement": {
            "click_rate_change": "+0.05",
            "trend": "improving"
        }
    }
    """
    try:
        days = int(request.args.get('days', 7))
        
        # Get effectiveness metrics
        metrics = feedback_loop.measure_effectiveness(user_id, days=days)
        
        return jsonify({
            'user_id': user_id,
            'period_days': days,
            'metrics': metrics,
            'measured_at': datetime.utcnow().isoformat()
        }), 200
        
    except Exception as e:
        logger.error(f"Error getting effectiveness: {e}")
        return jsonify({'error': str(e)}), 500


# ============================================================================
# HEALTH & STATUS
# ============================================================================

@app.route('/api/v8.5/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    try:
        # Check database connection
        conn = sqlite3.connect(str(DB_PATH))
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM user_interactions')
        total_interactions = cursor.fetchone()[0]
        conn.close()
        
        return jsonify({
            'status': 'healthy',
            'database': 'connected',
            'total_interactions': total_interactions,
            'timestamp': datetime.utcnow().isoformat()
        }), 200
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return jsonify({
            'status': 'unhealthy',
            'error': str(e)
        }), 500


@app.route('/api/v8.5/status', methods=['GET'])
def status():
    """System status endpoint"""
    return jsonify({
        'version': '8.5',
        'name': 'Pattern Learning API',
        'status': 'running',
        'features': [
            'interaction_tracking',
            'personalized_recommendations',
            'pattern_analysis',
            'federated_learning',
            'context_aware_delivery'
        ],
        'timestamp': datetime.utcnow().isoformat()
    }), 200


# ============================================================================
# MAIN
# ============================================================================

if __name__ == '__main__':
    # Get port from environment or default to 5004
    port = int(os.environ.get('PORT', 5004))
    
    logger.info(f"Starting V8.5 Pattern Learning API on port {port}")
    logger.info(f"Database: {DB_PATH}")
    
    # Run Flask app
    app.run(
        host='0.0.0.0',
        port=port,
        debug=True
    )
