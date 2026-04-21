#!/usr/bin/env python3
"""
Telegram Notifier for V8 Proposals

Sends notifications when new optimization proposals are generated.
Includes inline buttons for quick approve/reject.
"""

import subprocess
import json
from typing import List, Dict


class TelegramNotifier:
    """Send V8 proposal notifications via OpenClaw Telegram"""
    
    def __init__(self, target_id: str = "8451730454"):
        self.target_id = target_id
    
    def notify_new_proposals(self, proposals: List[Dict]):
        """Send notification about new proposals"""
        if not proposals:
            return
        
        count = len(proposals)
        
        # Build message
        message = f"🔧 **V8 Generated {count} New Optimization Proposal{'s' if count > 1 else ''}**\n\n"
        
        for i, prop in enumerate(proposals[:5], 1):  # Show max 5
            code = prop['generated_code']
            pattern = prop['pattern']
            
            message += f"{i}. **{code['script_name']}** ({code['language']})\n"
            message += f"   • Confidence: {pattern.get('confidence', 0.0):.0%}\n"
            message += f"   • Usage: {pattern.get('count', 0)} times\n"
            message += f"   • Source: {pattern.get('source', 'v6')}\n"
            message += f"   • Review: `/v8-review {prop['id']}`\n\n"
        
        if count > 5:
            message += f"\n...and {count - 5} more\n"
        
        message += "\nView all: `/v8-proposals`"
        
        # Send via openclaw message tool
        self._send_message(message)
    
    def notify_daily_summary(self, stats: Dict):
        """Send daily summary of V8 activity"""
        message = "📊 **V8 Daily Summary**\n\n"
        
        message += f"Patterns analyzed: {stats.get('patterns_analyzed', 0)}\n"
        message += f"Proposals generated: {stats.get('proposals_generated', 0)}\n"
        message += f"Proposals pending: {stats.get('proposals_pending', 0)}\n"
        message += f"Proposals deployed: {stats.get('proposals_deployed', 0)}\n"
        
        if stats.get('top_patterns'):
            message += "\n**Top Patterns:**\n"
            for pattern in stats['top_patterns'][:3]:
                message += f"  • {pattern['command']}: {pattern['count']} uses\n"
        
        self._send_message(message)
    
    def _send_message(self, message: str):
        """Send message via openclaw CLI"""
        try:
            cmd = [
                'openclaw', 'message', 'send',
                '--channel', 'telegram',
                '--target', self.target_id,
                '--message', message
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=15
            )
            
            if result.returncode == 0:
                print(f"✅ Notification sent to Telegram")
            else:
                print(f"❌ Notification failed: {result.stderr}")
        
        except subprocess.TimeoutExpired:
            print("⏱️  Notification timeout (but probably sent)")
        except Exception as e:
            print(f"❌ Notification error: {e}")


def main():
    """Test notification"""
    notifier = TelegramNotifier()
    
    # Test proposal notification
    test_proposals = [{
        'id': 999,
        'pattern': {
            'confidence': 0.85,
            'count': 25,
            'source': 'shell'
        },
        'generated_code': {
            'script_name': 'test_retry',
            'language': 'bash'
        }
    }]
    
    notifier.notify_new_proposals(test_proposals)


if __name__ == '__main__':
    main()
