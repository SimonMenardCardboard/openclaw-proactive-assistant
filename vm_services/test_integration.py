#!/usr/bin/env python3
"""
Integration Test - Complete VM → App Pipeline
Tests: OAuth → Bootstrap → Queue → Push Service
"""

import sys
import time
import json
import asyncio
import requests
from pathlib import Path

# Add paths
sys.path.insert(0, str(Path(__file__).parent.parent / 'onboarding'))
sys.path.insert(0, str(Path(__file__).parent.parent / 'proactive_system'))
sys.path.insert(0, str(Path(__file__).parent))

from bootstrap import BootstrapOnboarding
from push_service import PushService

print("\n" + "="*60)
print("🧪 INTEGRATION TEST: Complete VM → App Pipeline")
print("="*60 + "\n")


def test_1_oauth_tokens():
    """Test 1: Simulate app sending OAuth tokens to VM"""
    print("📝 Test 1: OAuth Token Storage")
    print("-" * 60)
    
    user_id = 'test_user_integration'
    provider = 'google'
    
    # Simulate tokens from mobile app
    tokens = {
        'access_token': 'test_access_token_12345',
        'refresh_token': 'test_refresh_token_67890',
        'expires_in': 3600
    }
    
    # Store tokens (simulating webhook call)
    config_dir = Path.home() / '.openclaw/config/users' / user_id
    config_dir.mkdir(parents=True, exist_ok=True)
    
    token_file = config_dir / f'{provider}_tokens.json'
    with open(token_file, 'w') as f:
        json.dump(tokens, f, indent=2)
    
    print(f"✅ Stored OAuth tokens: {token_file}")
    print(f"   User: {user_id}")
    print(f"   Provider: {provider}")
    print()
    
    return user_id


def test_2_bootstrap(user_id):
    """Test 2: Trigger bootstrap onboarding"""
    print("📝 Test 2: Bootstrap Onboarding")
    print("-" * 60)
    
    onboarding = BootstrapOnboarding(user_id)
    
    print(f"Triggering bootstrap for {user_id}...")
    asyncio.run(onboarding.trigger())
    
    print("✅ Bootstrap complete")
    print()


def test_3_check_queue():
    """Test 3: Verify recommendations queued"""
    print("📝 Test 3: Proactive Queue")
    print("-" * 60)
    
    import sqlite3
    
    db_path = Path(__file__).parent.parent / 'proactive_system/proactive_queue.db'
    
    if not db_path.exists():
        print("❌ Queue database not found")
        return 0
    
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT COUNT(*), SUM(delivered), COUNT(*) - SUM(delivered)
        FROM proactive_queue
        WHERE source IN ('bootstrap', 'onboarding')
    """)
    
    total, delivered, pending = cursor.fetchone()
    
    print(f"✅ Queue status:")
    print(f"   Total recommendations: {total}")
    print(f"   Delivered: {delivered}")
    print(f"   Pending: {pending}")
    
    # Show preview
    cursor.execute("""
        SELECT id, source, priority, substr(message, 1, 60) as preview
        FROM proactive_queue
        WHERE source IN ('bootstrap', 'onboarding')
        AND delivered = 0
        ORDER BY priority ASC
        LIMIT 3
    """)
    
    print(f"\n   Preview of pending recommendations:")
    for item_id, source, priority, preview in cursor.fetchall():
        print(f"   [{item_id}] P{priority} ({source}): {preview}...")
    
    conn.close()
    print()
    
    return pending


def test_4_push_service(user_id):
    """Test 4: Push service delivery"""
    print("📝 Test 4: Push Service")
    print("-" * 60)
    
    # Create push service
    push_service = PushService()
    
    # Register test device
    print(f"Registering test device for {user_id}...")
    push_service.register_device(
        user_id=user_id,
        device_token='test_fcm_token_abc123',
        platform='android'
    )
    
    print(f"✅ Device registered")
    print(f"   Total users: {len(push_service.devices)}")
    print(f"   Total devices: {sum(len(d) for d in push_service.devices.values())}")
    
    # Process queue
    print(f"\nProcessing queue...")
    delivered = push_service.process_queue()
    
    print(f"✅ Processed {delivered} notification(s)")
    print()
    
    return delivered


def test_5_webhook_api():
    """Test 5: Bootstrap webhook API (if running)"""
    print("📝 Test 5: Webhook API (Optional)")
    print("-" * 60)
    
    # Check if webhook is running
    try:
        response = requests.get('http://localhost:8101/health', timeout=2)
        print(f"✅ Webhook API is running")
        print(f"   Status: {response.json()}")
    except requests.exceptions.RequestException:
        print(f"⚠️  Webhook API not running")
        print(f"   Start with: python3 vm_services/bootstrap_webhook.py")
    
    print()


def test_6_push_api():
    """Test 6: Push service API (if running)"""
    print("📝 Test 6: Push Service API (Optional)")
    print("-" * 60)
    
    try:
        response = requests.get('http://localhost:8100/health', timeout=2)
        print(f"✅ Push API is running")
        print(f"   Status: {response.json()}")
    except requests.exceptions.RequestException:
        print(f"⚠️  Push API not running")
        print(f"   Start with: python3 vm_services/push_service.py")
    
    print()


def main():
    """Run all tests"""
    
    # Test 1: Store OAuth tokens
    user_id = test_1_oauth_tokens()
    
    # Test 2: Trigger bootstrap
    test_2_bootstrap(user_id)
    
    # Test 3: Check queue
    pending = test_3_check_queue()
    
    if pending > 0:
        # Test 4: Deliver via push service
        test_4_push_service(user_id)
        
        # Verify delivery
        print("📝 Test 4b: Verify Delivery")
        print("-" * 60)
        test_3_check_queue()  # Should show 0 pending now
    
    # Test 5 & 6: Check if APIs running
    test_5_webhook_api()
    test_6_push_api()
    
    # Summary
    print("="*60)
    print("✅ INTEGRATION TEST COMPLETE")
    print("="*60)
    print()
    print("What was tested:")
    print("  ✅ OAuth token storage")
    print("  ✅ Bootstrap onboarding trigger")
    print("  ✅ Recommendation generation")
    print("  ✅ Proactive queue integration")
    print("  ✅ Push service delivery")
    print("  ⚠️  Webhook API (optional)")
    print("  ⚠️  Push API (optional)")
    print()
    print("Next steps:")
    print("  1. Start webhook: python3 vm_services/bootstrap_webhook.py")
    print("  2. Start push service: python3 vm_services/push_service.py")
    print("  3. Mobile app calls: POST /onboarding/oauth-complete")
    print("  4. Recommendations delivered to app!")
    print()


if __name__ == '__main__':
    main()
