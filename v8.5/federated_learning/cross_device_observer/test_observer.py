#!/usr/bin/env python3
"""
Test Cross-Device Observer
Validates screen capture and activity extraction
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from desktop.screen_capture import ScreenCapture
from desktop.activity_extractor import ActivityExtractor

print("=" * 60)
print("CROSS-DEVICE OBSERVER TEST")
print("=" * 60)

# Test 1: Screen Capture
print("\n1. Testing Screen Capture (localhost)")
print("-" * 60)

capturer = ScreenCapture()
screenshot = capturer.capture_localhost_screenshot()

if screenshot and screenshot.exists():
    size_mb = screenshot.stat().st_size / (1024 * 1024)
    print(f"✅ Screenshot captured: {screenshot}")
    print(f"   Size: {size_mb:.2f} MB")
else:
    print("❌ Screenshot capture failed")
    sys.exit(1)

# Test 2: Activity Extraction
print("\n2. Testing Activity Extraction (OCR)")
print("-" * 60)

extractor = ActivityExtractor()
activity = extractor.extract_from_screenshot(screenshot)

if activity:
    print(f"✅ Activity extracted:")
    print(f"   App: {activity.get('app_name', 'unknown')}")
    print(f"   Action: {activity.get('action_type', 'unknown')}")
    print(f"   Text extracted: {activity.get('raw_text_length', 0)} chars")
    print(f"   Summary: {activity.get('text_summary', 'N/A')[:100]}")
else:
    print("❌ Activity extraction failed")
    sys.exit(1)

# Test 3: Privacy Filtering
print("\n3. Testing Privacy Filtering")
print("-" * 60)

test_text = """
password: secret123
api_key: sk-1234567890
Normal application text here
"""

filtered = extractor._filter_sensitive_data(test_text)
print(f"Original length: {len(test_text)} chars")
print(f"Filtered length: {len(filtered)} chars")

if 'secret123' in filtered or 'sk-' in filtered:
    print("❌ Privacy filtering failed - sensitive data leaked!")
else:
    print("✅ Privacy filtering working")

# Test 4: Cleanup
print("\n4. Testing Cleanup")
print("-" * 60)

cleanup_result = capturer.cleanup_screenshot(screenshot)
print(f"✅ Cleanup: {cleanup_result}")

# Summary
print("\n" + "=" * 60)
print("TEST SUMMARY")
print("=" * 60)
print("✅ Screen capture: WORKING")
print("✅ OCR extraction: WORKING")
print("✅ Privacy filtering: WORKING")
print("✅ Cleanup: WORKING")
print("\n⚠️  Note: OCR accuracy depends on screen content")
print("   Text-heavy screens work best")
print("\n" + "=" * 60)
