"""
Smart Alert Escalation for V6
Replaces naive deduplication with state-machine based alerts
"""

from datetime import datetime
import sqlite3
from typing import List, Dict

class AlertEscalation:
    """Manages alert state and escalation logic"""
    
    def __init__(self, db_path):
        self.db_path = db_path
        
        # Monitor-specific escalation thresholds (hours)
        self.escalation_thresholds = {
            'recovery': 24,  # WHOOP updates once per day
            'whoop_data': 48,  # Stale data, no rush
            'default': 6  # Most monitors: 6 hours
        }
    
    def process_alerts(self, observations: List[Dict]) -> List[Dict]:
        """
        Smart alert deduplication with escalation.
        
        States:
        1. NEW: First detection → alert immediately
        2. PERSISTENT: Ongoing <6h → suppress
        3. ESCALATED: Ongoing >6h → alert with escalation
        4. RESOLVED: Fixed → alert resolution
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        now = datetime.now()
        
        alerts_to_send = []
        
        for obs in observations:
            monitor_type = obs['monitor_type']
            obs_type = obs['observation_type']
            severity = obs.get('severity', 'medium')
            
            # Get alert state
            cursor.execute("""
                SELECT state, first_seen, last_alerted, escalation_count
                FROM alert_state
                WHERE monitor_type = ? AND observation_type = ?
            """, (monitor_type, obs_type))
            
            state_row = cursor.fetchone()
            
            if state_row is None:
                # NEW: First time seeing this
                if severity in ['critical', 'high']:
                    obs['_alert_type'] = 'NEW'
                    alerts_to_send.append(obs)
                    
                    # Record alert state
                    cursor.execute("""
                        INSERT INTO alert_state 
                        (monitor_type, observation_type, state, first_seen, last_alerted, escalation_count)
                        VALUES (?, ?, 'ALERTED', ?, ?, 1)
                    """, (monitor_type, obs_type, now.isoformat(), now.isoformat()))
            
            else:
                state, first_seen_str, last_alerted_str, esc_count = state_row
                first_seen = datetime.fromisoformat(first_seen_str)
                last_alerted = datetime.fromisoformat(last_alerted_str) if last_alerted_str else None
                
                duration_hours = (now - first_seen).total_seconds() / 3600
                hours_since_alert = (now - last_alerted).total_seconds() / 3600 if last_alerted else 999
                
                # Get monitor-specific threshold
                threshold_hours = self.escalation_thresholds.get(monitor_type, self.escalation_thresholds['default'])
                
                # ESCALATION: Issue persists >threshold, not alerted recently
                if duration_hours > threshold_hours and hours_since_alert > threshold_hours:
                    obs['_alert_type'] = 'ESCALATION'
                    obs['_duration_hours'] = int(duration_hours)
                    obs['_escalation_count'] = esc_count + 1
                    alerts_to_send.append(obs)
                    
                    # Update alert state
                    cursor.execute("""
                        UPDATE alert_state
                        SET last_alerted = ?, escalation_count = escalation_count + 1
                        WHERE monitor_type = ? AND observation_type = ?
                    """, (now.isoformat(), monitor_type, obs_type))
        
        # Check for RESOLVED issues
        cursor.execute("SELECT monitor_type, observation_type, first_seen FROM alert_state WHERE state = 'ALERTED'")
        alerted_issues = cursor.fetchall()
        observed_keys = {(o['monitor_type'], o['observation_type']) for o in observations}
        
        for mon_type, obs_type, first_seen_str in alerted_issues:
            if (mon_type, obs_type) not in observed_keys:
                first_seen = datetime.fromisoformat(first_seen_str)
                duration_hours = (now - first_seen).total_seconds() / 3600
                
                resolution_alert = {
                    'monitor_type': mon_type,
                    'observation_type': obs_type,
                    'severity': 'info',
                    'confidence': 1.0,
                    'data': {
                        'message': f'{obs_type} resolved (was failing for {int(duration_hours)}h)'
                    },
                    '_alert_type': 'RESOLVED',
                    '_duration_hours': int(duration_hours)
                }
                alerts_to_send.append(resolution_alert)
                
                # Delete resolved alert state
                cursor.execute("DELETE FROM alert_state WHERE monitor_type = ? AND observation_type = ?",
                             (mon_type, obs_type))
        
        conn.commit()
        conn.close()
        
        return alerts_to_send
