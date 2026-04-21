#!/usr/bin/env python3
"""
V8.5 Cross-Device Pattern Detection Integration

Connects desktop observer to V8 pattern learner:
1. Captures screen activities via observer
2. Detects repeated workflows
3. Generates workflow signatures
4. Stores in V8 patterns database

This is Phase 1.1 of V8.5 Federated Learning build.
"""

import sys
import json
import logging
import sqlite3
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict
import hashlib

# Add V8 pattern learner to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'v8_meta_learning'))

from pattern_learner.detector import PatternDetector

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('v8.5.cross_device_patterns')


@dataclass
class WorkflowActivity:
    """Single activity in a workflow."""
    device_id: str
    timestamp: str
    app_name: str
    action_type: str
    context_hash: str
    text_summary: Optional[str] = None


@dataclass
class WorkflowPattern:
    """Detected workflow pattern."""
    workflow_id: str
    pattern_signature: Dict[str, Any]
    devices_involved: List[str]
    activities: List[WorkflowActivity]
    frequency: float  # Times per day
    success_rate: float
    first_seen: str
    last_seen: str


class CrossDevicePatternDetector:
    """Detects workflow patterns from cross-device observations."""
    
    def __init__(self, workspace_root: Optional[Path] = None):
        if workspace_root is None:
            workspace_root = Path.home() / '.openclaw' / 'workspace'
        
        self.workspace_root = Path(workspace_root)
        
        # V8.5 database for cross-device activities
        self.v85_db_path = self.workspace_root / 'integrations' / 'intelligence' / 'v8.5_federated_learning' / 'cross_device_activities.db'
        self.v85_db_path.parent.mkdir(parents=True, exist_ok=True)
        
        # V8 pattern learner (for storage)
        self.pattern_learner = PatternDetector()
        
        self._init_db()
    
    def _init_db(self):
        """Initialize cross-device activities database."""
        with sqlite3.connect(self.v85_db_path) as conn:
            # Devices table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS devices (
                    device_id TEXT PRIMARY KEY,
                    device_type TEXT,
                    device_name TEXT,
                    last_seen TEXT,
                    observer_enabled INTEGER DEFAULT 1
                )
            """)
            
            # Cross-device activities table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS cross_device_activities (
                    activity_id TEXT PRIMARY KEY,
                    device_id TEXT,
                    timestamp TEXT,
                    app_name TEXT,
                    action_type TEXT,
                    context_hash TEXT,
                    text_summary TEXT,
                    workflow_id TEXT,
                    FOREIGN KEY (device_id) REFERENCES devices(device_id)
                )
            """)
            
            # Workflow patterns table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS workflow_patterns (
                    workflow_id TEXT PRIMARY KEY,
                    pattern_signature TEXT,
                    devices_involved TEXT,
                    frequency REAL,
                    success_rate REAL,
                    first_seen TEXT,
                    last_seen TEXT
                )
            """)
            
            # Indexes
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_activities_timestamp
                ON cross_device_activities(timestamp)
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_activities_device
                ON cross_device_activities(device_id)
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_activities_workflow
                ON cross_device_activities(workflow_id)
            """)
            
            conn.commit()
    
    def register_device(self, device_id: str, device_type: str, device_name: str):
        """Register a device for observation."""
        with sqlite3.connect(self.v85_db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO devices (device_id, device_type, device_name, last_seen)
                VALUES (?, ?, ?, ?)
            """, (device_id, device_type, device_name, datetime.now().isoformat()))
            conn.commit()
        
        logger.info(f"Registered device: {device_name} ({device_type})")
    
    def record_activity(self, activity: WorkflowActivity):
        """Record a single activity."""
        activity_id = hashlib.sha256(
            f"{activity.device_id}:{activity.timestamp}:{activity.app_name}".encode()
        ).hexdigest()[:16]
        
        with sqlite3.connect(self.v85_db_path) as conn:
            conn.execute("""
                INSERT OR IGNORE INTO cross_device_activities
                (activity_id, device_id, timestamp, app_name, action_type, context_hash, text_summary)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                activity_id,
                activity.device_id,
                activity.timestamp,
                activity.app_name,
                activity.action_type,
                activity.context_hash,
                activity.text_summary
            ))
            conn.commit()
        
        # Update device last_seen
        with sqlite3.connect(self.v85_db_path) as conn:
            conn.execute("""
                UPDATE devices SET last_seen = ? WHERE device_id = ?
            """, (activity.timestamp, activity.device_id))
            conn.commit()
    
    def detect_workflow_patterns(self, lookback_days: int = 7) -> List[WorkflowPattern]:
        """
        Detect repeated workflow patterns from activities.
        
        A workflow is a sequence of activities that occur together repeatedly.
        
        Args:
            lookback_days: Number of days to analyze
            
        Returns:
            List of detected workflow patterns
        """
        cutoff = (datetime.now() - timedelta(days=lookback_days)).isoformat()
        
        # Get all activities in window
        with sqlite3.connect(self.v85_db_path) as conn:
            cursor = conn.execute("""
                SELECT activity_id, device_id, timestamp, app_name, action_type, context_hash, text_summary
                FROM cross_device_activities
                WHERE timestamp >= ?
                ORDER BY timestamp
            """, (cutoff,))
            
            activities = []
            for row in cursor:
                activities.append(WorkflowActivity(
                    device_id=row[1],
                    timestamp=row[2],
                    app_name=row[3],
                    action_type=row[4],
                    context_hash=row[5],
                    text_summary=row[6]
                ))
        
        if not activities:
            logger.info("No activities found in lookback window")
            return []
        
        # Group activities into sequences (5-minute windows)
        sequences = self._group_into_sequences(activities, window_minutes=5)
        
        # Find repeated sequences
        patterns = self._find_repeated_sequences(sequences)
        
        logger.info(f"Detected {len(patterns)} workflow patterns from {len(activities)} activities")
        
        # Save patterns
        self._save_patterns(patterns)
        
        return patterns
    
    def _group_into_sequences(self, activities: List[WorkflowActivity], window_minutes: int = 5) -> List[List[WorkflowActivity]]:
        """Group activities into sequences based on time proximity."""
        if not activities:
            return []
        
        sequences = []
        current_sequence = [activities[0]]
        
        for activity in activities[1:]:
            # Check if within window of last activity in current sequence
            last_time = datetime.fromisoformat(current_sequence[-1].timestamp)
            current_time = datetime.fromisoformat(activity.timestamp)
            
            if (current_time - last_time).total_seconds() <= window_minutes * 60:
                current_sequence.append(activity)
            else:
                # Start new sequence
                if len(current_sequence) > 1:
                    sequences.append(current_sequence)
                current_sequence = [activity]
        
        # Add final sequence
        if len(current_sequence) > 1:
            sequences.append(current_sequence)
        
        return sequences
    
    def _find_repeated_sequences(self, sequences: List[List[WorkflowActivity]]) -> List[WorkflowPattern]:
        """Find sequences that repeat."""
        # Generate signatures for each sequence
        sequence_signatures = {}
        
        for seq in sequences:
            # Create signature from app names + action types
            sig = tuple((act.app_name, act.action_type) for act in seq)
            
            if sig not in sequence_signatures:
                sequence_signatures[sig] = []
            
            sequence_signatures[sig].append(seq)
        
        # Filter for repeated patterns (occurred ≥2 times)
        patterns = []
        
        for sig, occurrences in sequence_signatures.items():
            if len(occurrences) < 2:
                continue
            
            # Calculate metrics
            first_seen = min(occ[0].timestamp for occ in occurrences)
            last_seen = max(occ[-1].timestamp for occ in occurrences)
            
            # Frequency (times per day)
            days_span = (datetime.fromisoformat(last_seen) - datetime.fromisoformat(first_seen)).days
            if days_span == 0:
                days_span = 1
            frequency = len(occurrences) / days_span
            
            # Devices involved
            devices = list(set(act.device_id for occ in occurrences for act in occ))
            
            # Pattern signature
            pattern_sig = {
                'sequence': [{'app': app, 'action': action} for app, action in sig],
                'length': len(sig),
                'cross_device': len(devices) > 1
            }
            
            # Workflow ID
            workflow_id = hashlib.sha256(json.dumps(pattern_sig, sort_keys=True).encode()).hexdigest()[:16]
            
            pattern = WorkflowPattern(
                workflow_id=workflow_id,
                pattern_signature=pattern_sig,
                devices_involved=devices,
                activities=occurrences[0],  # Use first occurrence as example
                frequency=frequency,
                success_rate=1.0,  # Default (will be updated with outcome tracking)
                first_seen=first_seen,
                last_seen=last_seen
            )
            
            patterns.append(pattern)
        
        return patterns
    
    def _save_patterns(self, patterns: List[WorkflowPattern]):
        """Save detected patterns to database."""
        with sqlite3.connect(self.v85_db_path) as conn:
            for pattern in patterns:
                conn.execute("""
                    INSERT OR REPLACE INTO workflow_patterns
                    (workflow_id, pattern_signature, devices_involved, frequency, success_rate, first_seen, last_seen)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    pattern.workflow_id,
                    json.dumps(pattern.pattern_signature),
                    json.dumps(pattern.devices_involved),
                    pattern.frequency,
                    pattern.success_rate,
                    pattern.first_seen,
                    pattern.last_seen
                ))
            conn.commit()
        
        logger.info(f"Saved {len(patterns)} workflow patterns to database")
    
    def get_workflow_patterns(self, min_frequency: float = 0.5) -> List[WorkflowPattern]:
        """Get all detected workflow patterns."""
        with sqlite3.connect(self.v85_db_path) as conn:
            cursor = conn.execute("""
                SELECT workflow_id, pattern_signature, devices_involved, frequency, success_rate, first_seen, last_seen
                FROM workflow_patterns
                WHERE frequency >= ?
                ORDER BY frequency DESC
            """, (min_frequency,))
            
            patterns = []
            for row in cursor:
                patterns.append(WorkflowPattern(
                    workflow_id=row[0],
                    pattern_signature=json.loads(row[1]),
                    devices_involved=json.loads(row[2]),
                    activities=[],  # Not loaded for listing
                    frequency=row[3],
                    success_rate=row[4],
                    first_seen=row[5],
                    last_seen=row[6]
                ))
            
            return patterns


if __name__ == '__main__':
    # Test pattern detector
    detector = CrossDevicePatternDetector()
    
    # Register test device
    detector.register_device(
        device_id='mac-localhost',
        device_type='mac',
        device_name='MacBook Pro'
    )
    
    # Create test activities (simulating repeated morning workflow)
    test_activities = [
        WorkflowActivity(
            device_id='mac-localhost',
            timestamp=(datetime.now() - timedelta(days=2, hours=9)).isoformat(),
            app_name='Calendar',
            action_type='view',
            context_hash='morning_check',
            text_summary='Opened calendar at 9 AM'
        ),
        WorkflowActivity(
            device_id='mac-localhost',
            timestamp=(datetime.now() - timedelta(days=2, hours=9, minutes=2)).isoformat(),
            app_name='Mail',
            action_type='view',
            context_hash='morning_check',
            text_summary='Checked inbox'
        ),
        # Repeated pattern next day
        WorkflowActivity(
            device_id='mac-localhost',
            timestamp=(datetime.now() - timedelta(days=1, hours=9)).isoformat(),
            app_name='Calendar',
            action_type='view',
            context_hash='morning_check',
            text_summary='Opened calendar at 9 AM'
        ),
        WorkflowActivity(
            device_id='mac-localhost',
            timestamp=(datetime.now() - timedelta(days=1, hours=9, minutes=2)).isoformat(),
            app_name='Mail',
            action_type='view',
            context_hash='morning_check',
            text_summary='Checked inbox'
        ),
    ]
    
    # Record activities
    for activity in test_activities:
        detector.record_activity(activity)
    
    print("\n=== Cross-Device Pattern Detector Test ===")
    print(f"Recorded {len(test_activities)} test activities")
    
    # Detect patterns
    patterns = detector.detect_workflow_patterns(lookback_days=7)
    
    print(f"\nDetected {len(patterns)} workflow patterns:")
    for pattern in patterns:
        print(f"\nWorkflow ID: {pattern.workflow_id}")
        print(f"  Frequency: {pattern.frequency:.2f} times/day")
        print(f"  Devices: {', '.join(pattern.devices_involved)}")
        print(f"  Sequence:")
        for step in pattern.pattern_signature['sequence']:
            print(f"    → {step['app']}: {step['action']}")
    
    print("\n✅ Pattern detection test complete")
