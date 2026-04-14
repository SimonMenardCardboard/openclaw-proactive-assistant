#!/usr/bin/env python3
"""
Multi-Account Email Pattern Analyzer

Analyzes email patterns across multiple Gmail accounts:
- simon@legalmensch.com (work)
- lacrosseguy76665@gmail.com (personal)

Combines patterns to generate comprehensive optimizations.
"""

import sys
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List

# Import the single-account analyzer
sys.path.insert(0, str(Path(__file__).parent))
from email_pattern_analyzer import EmailPatternAnalyzer

# Add direct_api to path
WORKSPACE = Path.home() / '.openclaw/workspace'
sys.path.insert(0, str(WORKSPACE / 'integrations/direct_api'))


class MultiAccountEmailAnalyzer:
    """Analyze patterns across multiple email accounts"""
    
    ACCOUNTS = {
        'work': {
            'email': 'simon@legalmensch.com',
            'token_file': WORKSPACE / 'integrations/direct_api/token_simon_at_legalmensch_com.json',
            'label': 'Work (Legal Mensch)'
        },
        'personal': {
            'email': 'lacrosseguy76665@gmail.com',
            'token_file': None,  # Will try default auth
            'label': 'Personal'
        }
    }
    
    def __init__(self, days_back=30):
        self.days_back = days_back
        self.account_patterns = {}
        self.combined_patterns = None
    
    def analyze_all(self):
        """Analyze all configured accounts"""
        print("=" * 70)
        print("MULTI-ACCOUNT EMAIL PATTERN ANALYSIS")
        print("=" * 70)
        print(f"\nAnalyzing last {self.days_back} days across all accounts...\n")
        
        for account_key, account_info in self.ACCOUNTS.items():
            print(f"\n{'─' * 70}")
            print(f"Account: {account_info['label']} ({account_info['email']})")
            print(f"{'─' * 70}")
            
            try:
                # Check if token exists
                if account_info['token_file'] and not account_info['token_file'].exists():
                    print(f"⚠️  Skipping - no token file found")
                    print(f"   Expected: {account_info['token_file']}")
                    continue
                
                # Create analyzer for this account
                analyzer = EmailPatternAnalyzer(days_back=self.days_back)
                
                # TODO: Modify EmailPatternAnalyzer to accept token_file parameter
                # For now, it uses default auth
                
                patterns = analyzer.analyze()
                self.account_patterns[account_key] = {
                    'info': account_info,
                    'patterns': patterns
                }
                
                # Quick summary
                print(f"\n  ✓ {patterns['total_emails']} emails analyzed")
                print(f"  ✓ {len(patterns['optimizations'])} optimizations found")
                
            except Exception as e:
                print(f"  ✗ Error analyzing account: {e}")
                import traceback
                traceback.print_exc()
        
        # Combine patterns
        if self.account_patterns:
            self._combine_patterns()
    
    def _combine_patterns(self):
        """Combine patterns from all accounts"""
        print(f"\n{'=' * 70}")
        print("COMBINED ANALYSIS")
        print(f"{'=' * 70}\n")
        
        total_emails = sum(
            p['patterns']['total_emails']
            for p in self.account_patterns.values()
        )
        
        all_optimizations = []
        for account_key, data in self.account_patterns.items():
            account_label = data['info']['label']
            for opt in data['patterns']['optimizations']:
                opt['account'] = account_label
                opt['account_key'] = account_key
                all_optimizations.append(opt)
        
        self.combined_patterns = {
            'analyzed_at': datetime.now().isoformat(),
            'period_days': self.days_back,
            'accounts_analyzed': len(self.account_patterns),
            'total_emails': total_emails,
            'optimizations': all_optimizations,
            'by_account': self.account_patterns
        }
        
        print(f"📊 Total emails across all accounts: {total_emails}")
        print(f"💡 Total optimization opportunities: {len(all_optimizations)}")
        
        # Group by priority
        high_priority = [o for o in all_optimizations if o['priority'] == 'high']
        medium_priority = [o for o in all_optimizations if o['priority'] == 'medium']
        low_priority = [o for o in all_optimizations if o['priority'] == 'low']
        
        print(f"\n  High priority:   {len(high_priority)}")
        print(f"  Medium priority: {len(medium_priority)}")
        print(f"  Low priority:    {len(low_priority)}")
    
    def print_combined_summary(self):
        """Print summary of all accounts"""
        if not self.combined_patterns:
            print("No patterns to summarize")
            return
        
        print(f"\n{'=' * 70}")
        print("OPTIMIZATION RECOMMENDATIONS (ALL ACCOUNTS)")
        print(f"{'=' * 70}\n")
        
        # Sort by priority and confidence
        priority_order = {'high': 0, 'medium': 1, 'low': 2}
        sorted_opts = sorted(
            self.combined_patterns['optimizations'],
            key=lambda o: (priority_order.get(o['priority'], 99), -o['confidence'])
        )
        
        for i, opt in enumerate(sorted_opts, 1):
            print(f"{i}. [{opt['priority'].upper()}] {opt['title']}")
            print(f"   Account: {opt['account']}")
            print(f"   {opt['description']}")
            print(f"   Action: {opt['action']}")
            print(f"   Impact: {opt['impact']}")
            print(f"   Confidence: {int(opt['confidence'] * 100)}%")
            print()
    
    def save_results(self, output_file=None):
        """Save combined results"""
        if output_file is None:
            output_file = Path(__file__).parent / f'email_patterns_multi_{datetime.now().strftime("%Y%m%d")}.json'
        
        with open(output_file, 'w') as f:
            json.dump(self.combined_patterns, f, indent=2)
        
        print(f"\n✓ Combined results saved to: {output_file}")
        return output_file


def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Analyze email patterns across multiple accounts')
    parser.add_argument('--days', type=int, default=7, help='Days of history to analyze (default: 7)')
    parser.add_argument('--output', type=str, help='Output JSON file')
    parser.add_argument('--accounts', nargs='+', choices=['work', 'personal', 'all'], 
                       default=['all'], help='Which accounts to analyze')
    
    args = parser.parse_args()
    
    try:
        analyzer = MultiAccountEmailAnalyzer(days_back=args.days)
        analyzer.analyze_all()
        
        if analyzer.account_patterns:
            analyzer.print_combined_summary()
            analyzer.save_results(args.output)
            return 0
        else:
            print("\n✗ No accounts could be analyzed")
            print("\nTroubleshooting:")
            print("1. Run: cd ~/.openclaw/workspace/integrations/direct_api && python3 auth/setup.py")
            print("2. Authenticate both accounts when prompted")
            print("3. Retry this script")
            return 1
        
    except Exception as e:
        print(f"\n✗ Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
