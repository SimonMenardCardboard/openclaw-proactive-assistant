#!/usr/bin/env python3
"""
Test Bootstrap Onboarding with Real Proactive Queue Delivery
Simulates new user onboarding and delivers recommendations
"""

import asyncio
import logging
import sys
from pathlib import Path
from datetime import datetime, timedelta

# Add paths
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'integrations/intelligence'))
sys.path.insert(0, str(Path(__file__).parent))

from bootstrap import BootstrapOnboarding
from proactive_queue import ProactiveQueue

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)


async def test_bootstrap_onboarding():
    """Test full bootstrap flow with recommendation delivery."""
    
    user_id = 'test_user_simon'
    
    print("\n" + "="*60)
    print("🧪 TESTING BOOTSTRAP ONBOARDING")
    print("="*60 + "\n")
    
    # Step 1: Trigger bootstrap
    print("📝 Step 1: Trigger bootstrap onboarding...")
    onboarding = BootstrapOnboarding(user_id)
    await onboarding.trigger()
    
    print("\n" + "-"*60)
    print("✅ Bootstrap complete! Recommendations queued.")
    print("-"*60 + "\n")
    
    # Step 2: Check queue
    print("📋 Step 2: Checking proactive queue...")
    queue = ProactiveQueue()
    
    # Get all queued items
    import sqlite3
    db_path = Path.home() / '.openclaw/workspace/integrations/intelligence/proactive_queue.db'
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT id, source, message, priority, created_at, context
        FROM proactive_queue
        WHERE source IN ('bootstrap', 'onboarding')
        ORDER BY created_at ASC
    """)
    
    items = cursor.fetchall()
    conn.close()
    
    print(f"\n📬 Found {len(items)} queued recommendations:\n")
    
    for i, (item_id, source, message, priority, created_at, context) in enumerate(items, 1):
        # Parse message to get first line (title)
        first_line = message.split('\n')[0]
        print(f"   {i}. [{source}] {first_line} (Priority: {priority})")
    
    print("\n" + "-"*60)
    print("✅ Queue check complete")
    print("-"*60 + "\n")
    
    # Step 3: Simulate delivery (what V6 daemon would do)
    print("🚀 Step 3: Simulating spontaneous delivery...\n")
    
    # In real system, V6 daemon checks queue every 30 min
    # For testing, we'll deliver immediately and show what user sees
    
    for i, (item_id, source, message, priority, created_at, context) in enumerate(items, 1):
        # Simulate time passing
        if i > 1:
            await asyncio.sleep(2)  # 2 sec instead of hours for testing
        
        # Format as spontaneous notification
        print("\n" + "┌" + "─"*58 + "┐")
        print("│ 🐯 Transmogrifier - Spontaneous Recommendation          │")
        print("├" + "─"*58 + "┤")
        
        # Show message
        for line in message.split('\n'):
            if len(line) <= 56:
                print(f"│ {line:<56} │")
            else:
                # Word wrap long lines
                words = line.split()
                current_line = ""
                for word in words:
                    if len(current_line + word) <= 55:
                        current_line += word + " "
                    else:
                        print(f"│ {current_line:<56} │")
                        current_line = word + " "
                if current_line:
                    print(f"│ {current_line:<56} │")
        
        print("└" + "─"*58 + "┘")
        
        # Mark as delivered
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        cursor.execute("UPDATE proactive_queue SET delivered = 1, delivered_at = ? WHERE id = ?", 
                      (datetime.now().isoformat(), item_id))
        conn.commit()
        conn.close()
    
    print("\n" + "="*60)
    print("✅ TEST COMPLETE - All recommendations delivered!")
    print("="*60 + "\n")
    
    # Summary
    print("📊 Summary:")
    print(f"   • User: {user_id}")
    print(f"   • Recommendations generated: {len(items)}")
    print(f"   • Delivery method: Spontaneous via proactive queue")
    print(f"   • Timeline: Staggered over 4-6 hours (simulated)")
    print(f"   • Integration: V6 daemon picks up and delivers")
    print()


async def test_real_delivery():
    """Test with actual openclaw message delivery."""
    
    user_id = 'simon'  # Real user
    
    print("\n" + "="*60)
    print("🚀 REAL DELIVERY TEST - Sending to Telegram")
    print("="*60 + "\n")
    
    # Queue a test bootstrap recommendation
    queue = ProactiveQueue()
    
    test_message = """🎉 **Bootstrap Test - Email Optimization**

I analyzed your last 30 days and found a quick win:

📧 You respond to emails in 18.5 hours on average.

**Suggested improvement:**
• Flag urgent emails from VIPs
• Remind you of pending replies after 24h
• Auto-archive newsletters daily

Want me to set this up?

(This is a test of the bootstrap onboarding system)"""
    
    queue.add(
        source='bootstrap-test',
        message=test_message,
        priority=2,
        context={
            'user_id': user_id,
            'type': 'test_recommendation',
            'test': True
        }
    )
    
    print("✅ Test recommendation queued")
    print("📬 V6 daemon will deliver within 30 minutes")
    print("   (or run: cd ~/.openclaw/workspace/integrations/intelligence && python3 proactive_v6_deliver.py)")
    print()


if __name__ == '__main__':
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == '--real':
        # Real delivery to Telegram
        asyncio.run(test_real_delivery())
    else:
        # Simulation mode
        asyncio.run(test_bootstrap_onboarding())
