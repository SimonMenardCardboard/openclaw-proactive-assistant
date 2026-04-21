#!/usr/bin/env python3
"""
V8 Meta-Learning Daemon (Dry-Run Mode)

Continuously learns from V6/V7 operations:
1. Pattern detection - identify repeated actions
2. Workflow optimization - find inefficiencies
3. Policy tuning - adjust risk thresholds
4. Goal planning - decompose complex goals
5. Meta-reasoning - diagnose failures

Dry-run mode: Observes and logs without modifying V6 config
"""

import time
import logging
import signal
import sys
import json
from pathlib import Path
from datetime import datetime
import sqlite3

# Add component paths
sys.path.insert(0, str(Path(__file__).parent))

from pattern_learner.detector import PatternDetector
from workflow_optimizer.analyzer import WorkflowAnalyzer
from policy_tuner.outcome_tracker import OutcomeTracker
from policy_tuner.risk_model import RiskModel
from meta_reasoner.reasoner import MetaReasoner
from auto_optimizer import AutoOptimizer

# Logging
LOG_DIR = Path.home() / '.openclaw' / 'workspace' / 'logs'
LOG_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_DIR / 'v8_meta_learning.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('v8.daemon')


class V8Daemon:
    """V8 meta-learning daemon."""
    
    def __init__(self, dry_run: bool = True, interval_minutes: int = 30, enable_auto_deploy: bool = False):
        self.dry_run = dry_run
        self.interval_seconds = interval_minutes * 60
        self.running = False
        self.enable_auto_deploy = enable_auto_deploy
        
        # Components
        self.pattern_detector = PatternDetector()
        self.workflow_analyzer = WorkflowAnalyzer()
        self.outcome_tracker = OutcomeTracker()
        self.risk_model = RiskModel()
        self.meta_reasoner = MetaReasoner()
        self.auto_optimizer = AutoOptimizer(enable_auto_deploy=enable_auto_deploy)  # Phase 2+3: Auto-generate + deploy
        
        # Stats
        self.cycles = 0
        self.patterns_found = 0
        self.workflows_optimized = 0
        self.risk_adjustments = 0
        self.proposals_generated = 0  # Phase 2
        
        logger.info(f"V8 Daemon initialized (dry_run={dry_run}, interval={interval_minutes}m)")
    
    def run_cycle(self):
        """Run one learning cycle."""
        cycle_start = datetime.now()
        logger.info(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        logger.info(f"V8 LEARNING CYCLE #{self.cycles + 1}")
        logger.info(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        
        try:
            # 1. Pattern Detection
            logger.info("1️⃣  Running pattern detection...")
            patterns = self.pattern_detector.run_detection_cycle(lookback_days=7)
            # Update total patterns found
            pattern_count = len(patterns) if patterns else 0
            self.patterns_found += pattern_count
            logger.info(f"   Pattern detection cycle complete ({pattern_count} new patterns)")
            
            # 2. Workflow Optimization
            logger.info("2️⃣  Analyzing workflows...")
            sequences = self.workflow_analyzer.analyze_sequences(days=7)
            optimizations = self.workflow_analyzer.suggest_optimizations(sequences)
            logger.info(f"   Analyzed {len(sequences)} workflows, found {len(optimizations)} optimizations")
            
            # 3. Outcome Tracking & Risk Tuning
            logger.info("3️⃣  Tracking outcomes and updating risk scores...")
            outcomes = self.outcome_tracker.track_outcomes(days=7)
            logger.info(f"   Tracked outcomes for {len(outcomes)} actions")
            
            # Calculate risk scores for tracked actions
            high_risk = []
            for action_name in outcomes.keys():
                try:
                    risk_score = self.risk_model.calculate_risk(action_name, outcomes[action_name])
                    if risk_score > 0.7:
                        high_risk.append({'action_name': action_name, 'risk': risk_score})
                except Exception as e:
                    logger.debug(f"   Could not calculate risk for {action_name}: {e}")
            
            if high_risk:
                logger.warning(f"   ⚠️  {len(high_risk)} high-risk actions detected:")
                for action in high_risk[:3]:
                    logger.warning(f"      • {action.get('action_name')}: {action.get('risk', 0):.2f} risk")
            
            # 4. Auto-Optimizer (Phase 2: Generate code from patterns)
            logger.info("4️⃣  Auto-generating optimizations...")
            try:
                optimizer_result = self.auto_optimizer.run_cycle()
                new_proposals = optimizer_result.get('proposals_generated', 0)
                self.proposals_generated += new_proposals
                if new_proposals > 0:
                    logger.info(f"   🔧 Generated {new_proposals} new optimization proposal(s)")
                    logger.info(f"   📋 Review with: python3 v8_commands.py proposals")
                else:
                    logger.info(f"   ✅ No new optimization opportunities")
            except Exception as e:
                logger.warning(f"   Auto-optimizer error: {e}")
            
            # 5. Meta-Reasoning (only on failures)
            logger.info("5️⃣  Checking for recent failures...")
            recent_failures = self._get_recent_failures(hours=24)
            if recent_failures:
                logger.info(f"   Found {len(recent_failures)} recent failures, analyzing...")
                for failure in recent_failures[:3]:  # Analyze top 3
                    try:
                        context = json.loads(failure.get('context', '{}')) if isinstance(failure.get('context'), str) else failure.get('context', {})
                        solution = self.meta_reasoner.reason({'action': failure.get('action_name'), **context})
                        if solution:
                            logger.info(f"   💡 {failure.get('action_name')}: {solution.get('solution', 'No solution')} (confidence: {solution.get('confidence', 0):.2f})")
                    except Exception as e:
                        logger.warning(f"   Failed to reason about {failure.get('action_name')}: {e}")
            else:
                logger.info("   No recent failures to analyze")
            
            # 6. Summary
            cycle_duration = (datetime.now() - cycle_start).total_seconds()
            self.cycles += 1
            
            logger.info(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
            logger.info(f"Cycle #{self.cycles} complete in {cycle_duration:.1f}s")
            logger.info(f"Total patterns: {self.patterns_found} | Proposals: {self.proposals_generated} | High-risk: {len(high_risk)}")
            logger.info(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
            
            if self.dry_run:
                logger.info("🔍 DRY-RUN MODE: No changes written to V6 config")
            
        except Exception as e:
            logger.error(f"Error in learning cycle: {e}", exc_info=True)
    
    def _get_recent_failures(self, hours: int = 24) -> list:
        """Get recent failed actions from V6."""
        v6_db = Path('/Users/tsmolty/workspace/integrations/autonomous_executor/execution_log.db')
        if not v6_db.exists():
            return []
        
        try:
            conn = sqlite3.connect(str(v6_db))
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT action_name, context, timestamp
                FROM executions
                WHERE status = 'failed'
                AND timestamp > datetime('now', ? || ' hours')
                ORDER BY timestamp DESC
                LIMIT 10
            ''', (-hours,))
            
            failures = []
            for row in cursor.fetchall():
                failures.append({
                    'action_name': row[0],
                    'context': row[1],
                    'timestamp': row[2]
                })
            
            conn.close()
            return failures
            
        except Exception as e:
            logger.error(f"Error fetching recent failures: {e}")
            return []
    
    def start(self):
        """Start the daemon."""
        self.running = True
        
        # Signal handlers
        signal.signal(signal.SIGTERM, self._handle_shutdown)
        signal.signal(signal.SIGINT, self._handle_shutdown)
        
        logger.info("🚀 V8 Meta-Learning Daemon started")
        logger.info(f"   Mode: {'DRY-RUN' if self.dry_run else 'LIVE'}")
        logger.info(f"   Interval: {self.interval_seconds}s ({self.interval_seconds // 60}m)")
        
        while self.running:
            try:
                self.run_cycle()
                
                if self.running:
                    logger.info(f"💤 Sleeping for {self.interval_seconds // 60} minutes...")
                    time.sleep(self.interval_seconds)
                    
            except KeyboardInterrupt:
                logger.info("Keyboard interrupt received, shutting down...")
                break
            except Exception as e:
                logger.error(f"Unexpected error: {e}", exc_info=True)
                time.sleep(60)  # Wait 1 min before retry
    
    def _handle_shutdown(self, signum, frame):
        """Handle shutdown signals."""
        logger.info(f"Received signal {signum}, shutting down gracefully...")
        self.running = False
    
    def stop(self):
        """Stop the daemon."""
        self.running = False
        logger.info("V8 Daemon stopped")


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description='V8 Meta-Learning Daemon')
    parser.add_argument('--live', action='store_true', help='Live mode (write to V6 config)')
    parser.add_argument('--interval', type=int, default=30, help='Cycle interval in minutes (default: 30)')
    parser.add_argument('--auto-deploy', action='store_true', help='Enable automatic deployment (Phase 3)')
    
    args = parser.parse_args()
    
    daemon = V8Daemon(
        dry_run=not args.live, 
        interval_minutes=args.interval,
        enable_auto_deploy=args.auto_deploy
    )
    
    try:
        daemon.start()
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
