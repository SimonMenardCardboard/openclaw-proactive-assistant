#!/usr/bin/env python3
"""
Test Email + Calendar Integration with V8

Tests:
1. Multi-account email analyzer
2. Multi-account calendar analyzer
3. Pattern detection
4. Code generation
5. End-to-end proposal workflow
"""

import sys
from pathlib import Path

# Add modules to path
sys.path.insert(0, str(Path(__file__).parent))

from multi_account_email_analyzer import MultiAccountEmailAnalyzer
from multi_account_calendar_analyzer import MultiAccountCalendarAnalyzer
from auto_optimizer import AutoOptimizer
from code_generator import CodeGenerator


def test_email_patterns():
    """Test email pattern detection"""
    print("\n" + "="*60)
    print("TEST 1: Email Pattern Detection")
    print("="*60)
    
    analyzer = MultiAccountEmailAnalyzer()
    
    try:
        results = analyzer.analyze_all_accounts()
        
        print(f"✅ Email accounts analyzed: {len(results.get('accounts', {}))}")
        print(f"✅ Patterns detected: {len(results.get('patterns', []))}")
        
        for pattern in results.get('patterns', [])[:3]:
            print(f"   - {pattern.get('type')}: {pattern.get('description', 'N/A')}")
        
        return True
    
    except Exception as e:
        print(f"❌ Email test failed: {e}")
        return False


def test_calendar_patterns():
    """Test calendar pattern detection"""
    print("\n" + "="*60)
    print("TEST 2: Calendar Pattern Detection")
    print("="*60)
    
    analyzer = MultiAccountCalendarAnalyzer()
    
    try:
        results = analyzer.analyze_all_accounts()
        
        print(f"✅ Calendar accounts analyzed: {len(results.get('accounts', {}))}")
        print(f"✅ Patterns detected: {len(results.get('patterns', []))}")
        
        for pattern in results.get('patterns', [])[:3]:
            print(f"   - {pattern.get('type')}: {pattern.get('description', 'N/A')}")
        
        return True
    
    except Exception as e:
        print(f"❌ Calendar test failed: {e}")
        return False


def test_code_generation():
    """Test code generation for email/calendar patterns"""
    print("\n" + "="*60)
    print("TEST 3: Code Generation")
    print("="*60)
    
    generator = CodeGenerator()
    
    # Test email template
    email_pattern = {
        'type': 'email_template',
        'subject_pattern': 'Weekly Status Update',
        'count': 8,
        'confidence': 0.85,
        'source': 'email'
    }
    
    try:
        result = generator.generate(email_pattern)
        
        if result:
            print(f"✅ Generated: {result['script_name']}")
            print(f"   Language: {result['language']}")
            print(f"   Savings: {result['estimated_savings']}")
        else:
            print(f"❌ No code generated")
            return False
        
        return True
    
    except Exception as e:
        print(f"❌ Code generation test failed: {e}")
        return False


def test_full_integration():
    """Test end-to-end: patterns → code → proposals"""
    print("\n" + "="*60)
    print("TEST 4: Full Integration (Patterns → Proposals)")
    print("="*60)
    
    optimizer = AutoOptimizer()
    
    try:
        # Scan all sources (V6, shell, email, calendar)
        print("\n📊 Scanning for patterns...")
        patterns = optimizer.scan_for_patterns()
        
        print(f"✅ Total patterns found: {len(patterns)}")
        
        # Filter patterns suitable for code generation
        print("\n🔍 Filtering patterns...")
        suitable = optimizer.filter_patterns(patterns)
        
        print(f"✅ Suitable for automation: {len(suitable)}")
        
        # Show sample patterns by source
        sources = {}
        for p in patterns:
            source = p.get('source', 'unknown')
            sources[source] = sources.get(source, 0) + 1
        
        print("\n📈 Patterns by source:")
        for source, count in sources.items():
            print(f"   {source}: {count}")
        
        # Show email/calendar patterns specifically
        email_patterns = [p for p in patterns if p.get('source') == 'email']
        calendar_patterns = [p for p in patterns if p.get('source') == 'calendar']
        
        if email_patterns:
            print(f"\n📧 Email patterns ({len(email_patterns)}):")
            for p in email_patterns[:3]:
                print(f"   - {p.get('description')}")
        
        if calendar_patterns:
            print(f"\n📅 Calendar patterns ({len(calendar_patterns)}):")
            for p in calendar_patterns[:3]:
                print(f"   - {p.get('description')}")
        
        return True
    
    except Exception as e:
        print(f"❌ Full integration test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests"""
    print("\n" + "="*60)
    print("V8 EMAIL + CALENDAR INTEGRATION TESTS")
    print("="*60)
    
    tests = [
        ("Email Patterns", test_email_patterns),
        ("Calendar Patterns", test_calendar_patterns),
        ("Code Generation", test_code_generation),
        ("Full Integration", test_full_integration)
    ]
    
    results = []
    
    for name, test_func in tests:
        try:
            success = test_func()
            results.append((name, success))
        except Exception as e:
            print(f"❌ {name} crashed: {e}")
            results.append((name, False))
    
    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    
    passed = sum(1 for _, success in results if success)
    total = len(results)
    
    for name, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status}: {name}")
    
    print(f"\n{passed}/{total} tests passed ({passed/total*100:.0f}%)")
    
    if passed == total:
        print("\n🎉 All tests passed! Email + Calendar integration working.")
    else:
        print("\n⚠️ Some tests failed. Check errors above.")


if __name__ == '__main__':
    main()
