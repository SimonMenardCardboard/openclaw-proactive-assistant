#!/usr/bin/env python3
"""
V8 Notification System

Surfaces V8's recommendations to the user via Telegram.
Sends daily/weekly summaries of:
- New optimization suggestions
- High-risk actions detected
- Patterns learned
- Automation opportunities
"""

import sqlite3
import json
import logging
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('v8.notifier')


class V8Notifier:
    """Send V8 recommendations to user via Telegram."""
    
    def __init__(self, workspace_root: str = None):
        if workspace_root is None:
            workspace_root = str(Path.home() / 'workspace')
        
        self.workspace_root = Path(workspace_root)
        self.optimizer_db = self.workspace_root / 'integrations' / 'intelligence' / 'v8_meta_learning' / 'workflow_optimizer.db'
        self.patterns_db = self.workspace_root / 'integrations' / 'intelligence' / 'v8_meta_learning' / 'patterns.db'
        self.policy_db = self.workspace_root / 'integrations' / 'intelligence' / 'v8_meta_learning' / 'policy_tuner.db'
        
        # Telegram config
        self.telegram_id = "8451730454"
    
    def send_telegram(self, message: str):
        """Send message via Python Telegram bot."""
        try:
            # Use the Telegram bot that's already configured for training recs
            sys.path.insert(0, str(Path.home() / 'workspace' / 'integrations' / 'adaptive_training'))
            import telegram_bot
            
            telegram_bot.send_telegram_message(message, parse_mode='Markdown')
            logger.info("Telegram notification sent via telegram_bot")
            return True
            
        except Exception as e:
            logger.error(f"Error sending via telegram_bot: {e}")
            
            # Fallback: try telegram-send
            try:
                result = subprocess.run(
                    ['telegram-send', '--format', 'markdown', message],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                if result.returncode == 0:
                    logger.info("Telegram notification sent via telegram-send")
                    return True
            except:
                pass
            
            # Last resort: write to file and log
            try:
                notification_file = Path.home() / '.openclaw' / 'workspace' / 'integrations' / 'intelligence' / 'v8_notifications.txt'
                notification_file.parent.mkdir(parents=True, exist_ok=True)
                with open(notification_file, 'w') as f:
                    f.write(f"{datetime.now().isoformat()}\n{message}\n")
                logger.info(f"Wrote notification to {notification_file} (will need manual delivery)")
                # Print to stdout so cron can capture it
                print("\n" + "="*50)
                print("V8 INTELLIGENCE REPORT (manual delivery needed)")
                print("="*50)
                print(message)
                print("="*50)
                return True
            except Exception as e2:
                logger.error(f"Could not write notification file: {e2}")
                return False
    
    def get_new_optimizations(self, hours: int = 24) -> List[Dict[str, Any]]:
        """Get optimization suggestions created in last N hours."""
        try:
            cutoff = (datetime.now() - timedelta(hours=hours)).isoformat()
            
            conn = sqlite3.connect(str(self.optimizer_db))
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT 
                    oc.optimization_type,
                    oc.description,
                    oc.expected_improvement_pct,
                    oc.confidence,
                    ws.actions,
                    oc.created_at
                FROM optimization_candidates oc
                JOIN workflow_sequences ws ON oc.sequence_hash = ws.sequence_hash
                WHERE oc.status = 'candidate'
                  AND oc.created_at >= ?
                ORDER BY oc.expected_improvement_pct DESC
            ''', (cutoff,))
            
            rows = cursor.fetchall()
            conn.close()
            
            optimizations = []
            for row in rows:
                optimizations.append({
                    'type': row[0],
                    'description': row[1],
                    'improvement_pct': row[2],
                    'confidence': row[3],
                    'actions': json.loads(row[4]),
                    'created_at': row[5]
                })
            
            return optimizations
            
        except Exception as e:
            logger.error(f"Error getting optimizations: {e}")
            return []
    
    def get_bottlenecks(self, hours: int = 24) -> List[Dict[str, Any]]:
        """Get bottlenecks detected in last N hours."""
        try:
            cutoff = (datetime.now() - timedelta(hours=hours)).isoformat()
            
            conn = sqlite3.connect(str(self.optimizer_db))
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT 
                    bottleneck_step,
                    avg_delay_ms,
                    frequency,
                    severity,
                    detected_at
                FROM bottlenecks
                WHERE detected_at >= ?
                  AND severity IN ('high', 'medium')
                ORDER BY avg_delay_ms DESC
            ''', (cutoff,))
            
            rows = cursor.fetchall()
            conn.close()
            
            bottlenecks = []
            for row in rows:
                bottlenecks.append({
                    'action': row[0],
                    'delay_ms': row[1],
                    'frequency': row[2],
                    'severity': row[3],
                    'detected_at': row[4]
                })
            
            return bottlenecks
            
        except Exception as e:
            logger.error(f"Error getting bottlenecks: {e}")
            return []
    
    def format_daily_report(self) -> str:
        """Generate daily V8 report."""
        # Get data from last 24 hours
        optimizations = self.get_new_optimizations(hours=24)
        bottlenecks = self.get_bottlenecks(hours=24)
        
        if not optimizations and not bottlenecks:
            return None  # Nothing to report
        
        lines = ["🧠 *V8 Daily Intelligence Report*\n"]
        
        # Optimizations
        if optimizations:
            lines.append(f"📈 *{len(optimizations)} Optimization{'s' if len(optimizations) > 1 else ''} Detected*\n")
            for i, opt in enumerate(optimizations[:3], 1):  # Top 3
                actions_str = " → ".join(opt['actions'])
                lines.append(f"{i}. *{opt['type'].title()}*")
                lines.append(f"   {opt['description']}")
                lines.append(f"   Workflow: `{actions_str}`")
                lines.append(f"   💡 Expected: {opt['improvement_pct']:.0f}% faster")
                lines.append(f"   🎯 Confidence: {opt['confidence']:.0%}\n")
        
        # Bottlenecks
        if bottlenecks:
            lines.append(f"⚠️  *{len(bottlenecks)} Bottleneck{'s' if len(bottlenecks) > 1 else ''} Found*\n")
            for i, bn in enumerate(bottlenecks[:3], 1):  # Top 3
                lines.append(f"{i}. `{bn['action']}`")
                lines.append(f"   Delay: {bn['delay_ms']}ms ({bn['severity']} severity)")
                lines.append(f"   Frequency: {bn['frequency']}x in 24h\n")
        
        lines.append("_V8 is learning your workflows and finding optimization opportunities._")
        
        return "\n".join(lines)
    
    def send_daily_report(self):
        """Send daily report if there's new intelligence."""
        report = self.format_daily_report()
        
        if report:
            logger.info("Sending daily V8 report...")
            # Always print report to stdout for cron to capture
            print("\n" + "="*60)
            print("V8 META-LEARNING DAILY INTELLIGENCE REPORT")
            print("="*60)
            print(report)
            print("="*60 + "\n")
            
            # Try to send via Telegram too
            success = self.send_telegram(report)
            if success:
                logger.info("✅ Daily report sent")
            else:
                logger.warning("⚠️  Telegram send failed, report printed to stdout")
        else:
            logger.info("No new V8 intelligence to report")


if __name__ == '__main__':
    # Test notifier
    import sys
    
    notifier = V8Notifier()
    
    if len(sys.argv) > 1 and sys.argv[1] == '--daily':
        notifier.send_daily_report()
    else:
        # Show what would be sent
        report = notifier.format_daily_report()
        if report:
            print(report)
        else:
            print("No new V8 intelligence to report")
