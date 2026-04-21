#!/usr/bin/env python3
"""
Generate Email Optimization Recommendations

Takes email pattern analysis and generates actionable V8 optimizations.
"""

import sys
import json
from pathlib import Path
from typing import List, Dict

def generate_optimizations(patterns: Dict) -> List[Dict]:
    """Generate optimization recommendations from patterns"""
    
    optimizations = []
    
    if not patterns.get('combined'):
        print("No combined patterns found")
        return optimizations
    
    combined = patterns['combined']
    total_emails = patterns['total_emails']
    
    # 1. High-volume sender filters
    if combined.get('top_senders'):
        for sender in combined['top_senders'][:5]:
            if sender['percentage'] > 5.0:  # More than 5% of all email
                optimizations.append({
                    'type': 'email_filter',
                    'priority': 'high',
                    'title': f"Auto-filter high-volume sender: {sender['email']}",
                    'description': f"{sender['email']} sends {sender['percentage']}% of your email ({sender['count']} in 7 days)",
                    'action': f"Create Gmail filter: from:{sender['email']} → [Auto-archive after 7 days OR Apply label 'Newsletter']",
                    'impact': f"Reduce inbox clutter by {sender['percentage']}% ({sender['count']/7:.1f} emails/day)",
                    'confidence': 0.9,
                    'estimated_time_saved_minutes_per_week': int(sender['count'] * 0.5)  # 30 seconds per email
                })
            elif sender['percentage'] > 2.0:  # 2-5%
                optimizations.append({
                    'type': 'email_filter',
                    'priority': 'medium',
                    'title': f"Consider filtering: {sender['email']}",
                    'description': f"{sender['email']} sends {sender['count']} emails/week ({sender['percentage']}%)",
                    'action': f"Review and decide: Keep, Filter, or Unsubscribe",
                    'impact': f"Potential {sender['count']/7:.1f} emails/day reduction",
                    'confidence': 0.7,
                    'estimated_time_saved_minutes_per_week': int(sender['count'] * 0.3)
                })
    
    # 2. Newsletter cleanup
    newsletter_count = combined.get('newsletters', {}).get('count', 0)
    newsletter_pct = combined.get('newsletters', {}).get('percentage', 0)
    
    if newsletter_count > 50:  # More than 50 newsletters/week
        optimizations.append({
            'type': 'email_filter',
            'priority': 'high',
            'title': 'Auto-archive old newsletters',
            'description': f"{newsletter_count} newsletters detected ({newsletter_pct}% of email)",
            'action': 'Create filter: subject:(newsletter OR digest OR weekly) older_than:7d → archive',
            'impact': f"Auto-cleanup ~{newsletter_count} newsletters/week after reading window",
            'confidence': 0.85,
            'estimated_time_saved_minutes_per_week': int(newsletter_count * 0.25)
        })
    elif newsletter_count > 20:
        optimizations.append({
            'type': 'email_filter',
            'priority': 'medium',
            'title': 'Newsletter management',
            'description': f"{newsletter_count} newsletters/week",
            'action': 'Consider: Unsubscribe from low-value newsletters OR create auto-archive rule',
            'impact': f"Reduce {newsletter_count/7:.1f} newsletters/day",
            'confidence': 0.75,
            'estimated_time_saved_minutes_per_week': int(newsletter_count * 0.2)
        })
    
    # 3. Peak hour email batching
    peak_hour = combined.get('time_patterns', {}).get('peak_hour')
    if peak_hour is not None:
        optimizations.append({
            'type': 'notification_management',
            'priority': 'medium',
            'title': f'Batch email checking around peak hours',
            'description': f"Most emails arrive at {peak_hour}:00. Consider batching email checks.",
            'action': f"Turn off real-time notifications. Check email at: {peak_hour}:00, {(peak_hour+4)%24}:00, {(peak_hour+8)%24}:00",
            'impact': 'Reduce interruptions by ~60-70% while staying responsive',
            'confidence': 0.8,
            'estimated_time_saved_minutes_per_week': 120  # 2 hours/week from reduced context switching
        })
    
    # 4. Multi-account consolidation
    sources = patterns.get('sources', [])
    if len(sources) > 2:
        personal_count = sum(s['email_count'] for s in sources if 'gmail' in s['id'].lower() or 'mail.app' in s['id'])
        work_count = sum(s['email_count'] for s in sources if 'legalmensch' in s['id'].lower())
        
        optimizations.append({
            'type': 'workflow_optimization',
            'priority': 'low',
            'title': f'Email account consolidation awareness',
            'description': f"Managing {len(sources)} email sources: Personal (~{personal_count} emails/week), Work (~{work_count} emails/week)",
            'action': 'Consider: Unified inbox OR separate processing times for work vs personal',
            'impact': 'Mental clarity and reduced context switching',
            'confidence': 0.6,
            'estimated_time_saved_minutes_per_week': 30
        })
    
    # 5. Unsubscribe candidates (senders with high volume, low engagement)
    # Would need reply/open tracking for accurate recommendations
    
    # Sort by priority and confidence
    priority_order = {'high': 0, 'medium': 1, 'low': 2}
    optimizations.sort(key=lambda o: (priority_order.get(o['priority'], 99), -o['confidence']))
    
    return optimizations


def print_optimizations(optimizations: List[Dict]):
    """Print optimizations in readable format"""
    
    if not optimizations:
        print("No optimization opportunities found")
        return
    
    print("\n" + "=" * 70)
    print(f"EMAIL OPTIMIZATION RECOMMENDATIONS ({len(optimizations)} total)")
    print("=" * 70)
    
    # Group by priority
    high = [o for o in optimizations if o['priority'] == 'high']
    medium = [o for o in optimizations if o['priority'] == 'medium']
    low = [o for o in optimizations if o['priority'] == 'low']
    
    total_time_saved = sum(o.get('estimated_time_saved_minutes_per_week', 0) for o in optimizations)
    
    print(f"\n💡 Summary:")
    print(f"  High priority:   {len(high)} optimizations")
    print(f"  Medium priority: {len(medium)} optimizations")
    print(f"  Low priority:    {len(low)} optimizations")
    print(f"\n⏱️  Total estimated time saved: {total_time_saved} minutes/week ({total_time_saved/60:.1f} hours/week)")
    
    for i, opt in enumerate(optimizations, 1):
        print(f"\n{'─' * 70}")
        print(f"{i}. [{opt['priority'].upper()}] {opt['title']}")
        print(f"{'─' * 70}")
        print(f"Description: {opt['description']}")
        print(f"Action:      {opt['action']}")
        print(f"Impact:      {opt['impact']}")
        print(f"Confidence:  {int(opt['confidence'] * 100)}%")
        if 'estimated_time_saved_minutes_per_week' in opt:
            print(f"Time saved:  {opt['estimated_time_saved_minutes_per_week']} min/week")
    
    print("\n" + "=" * 70)


def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Generate email optimization recommendations')
    parser.add_argument('--input', type=str, help='Input JSON file from universal_email_analyzer')
    parser.add_argument('--output', type=str, help='Output JSON file for optimizations')
    
    args = parser.parse_args()
    
    # Find most recent patterns file if not specified
    if not args.input:
        pattern_files = sorted(
            Path(__file__).parent.glob('email_patterns_universal_*.json'),
            key=lambda p: p.stat().st_mtime,
            reverse=True
        )
        
        if pattern_files:
            args.input = str(pattern_files[0])
            print(f"Using most recent pattern file: {args.input}\n")
        else:
            print("Error: No pattern files found. Run universal_email_analyzer.py first.")
            return 1
    
    # Load patterns
    try:
        with open(args.input) as f:
            patterns = json.load(f)
    except Exception as e:
        print(f"Error loading patterns: {e}")
        return 1
    
    # Generate optimizations
    optimizations = generate_optimizations(patterns)
    
    # Print
    print_optimizations(optimizations)
    
    # Save
    if args.output:
        output_file = Path(args.output)
    else:
        output_file = Path(__file__).parent / f"email_optimizations_{Path(args.input).stem.replace('email_patterns_', '')}.json"
    
    with open(output_file, 'w') as f:
        json.dump({
            'generated_at': patterns['analyzed_at'],
            'source_file': args.input,
            'total_optimizations': len(optimizations),
            'optimizations': optimizations
        }, f, indent=2)
    
    print(f"\n✓ Optimizations saved to: {output_file}")
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
