#!/usr/bin/env python3
"""
V8 Productivity Scoring Algorithm

Calculates daily productivity scores based on:
- Desktop app usage (productive vs unproductive)
- Location patterns (office vs home vs travel)
- Mobile app usage (focused vs distracted)
- Work-life balance metrics

Score: 0.0 - 1.0 (higher = more productive)
"""

import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Tuple, Optional

class ProductivityScorer:
    """Calculate productivity scores from activity data."""
    
    def __init__(self, workspace: Path):
        self.workspace = workspace
        
        # Database paths
        self.desktop_db = workspace / 'transmogrifier/openclaw-proactive-assistant/app_usage/desktop_usage.db'
        self.mobile_db = workspace / 'transmogrifier/openclaw-proactive-assistant/app_usage/mobile_usage.db'
        self.location_db = workspace / 'transmogrifier/openclaw-proactive-assistant/location_tracking/locations.db'
        
        # App category mappings
        self.app_scores = {
            # Highly productive (0.9-1.0)
            'VS Code': 1.0,
            'Visual Studio Code': 1.0,
            'IntelliJ': 1.0,
            'PyCharm': 1.0,
            'Xcode': 0.95,
            'Sublime': 0.95,
            'Terminal': 0.9,
            'iTerm': 0.9,
            
            # Moderately productive (0.6-0.8)
            'Notion': 0.8,
            'Obsidian': 0.8,
            'Notes': 0.75,
            'Mail': 0.7,
            'Gmail': 0.7,
            'Slack': 0.65,
            'Calendar': 0.7,
            
            # Neutral (0.4-0.6)
            'Finder': 0.5,
            'Safari': 0.5,
            'Chrome': 0.5,
            'Firefox': 0.5,
            
            # Unproductive (0.1-0.3)
            'YouTube': 0.2,
            'Netflix': 0.1,
            'Instagram': 0.15,
            'Twitter': 0.2,
            'Reddit': 0.2,
            'TikTok': 0.1,
        }
    
    def calculate_daily_score(self, user_id: str = 'simon', user_email: str = 'lacrosseguy76665@gmail.com', date: Optional[str] = None) -> Dict:
        """
        Calculate productivity score for a specific day.
        
        Returns:
            {
                'date': '2026-04-29',
                'overall_score': 0.75,
                'desktop_score': 0.80,
                'mobile_score': 0.65,
                'location_score': 0.80,
                'work_life_balance': 0.70,
                'total_hours': 8.5,
                'productive_hours': 6.2,
                'breakdown': {...}
            }
        """
        if date is None:
            date = datetime.now().strftime('%Y-%m-%d')
        
        # Calculate component scores
        desktop_score, desktop_hours = self._calculate_desktop_score(user_id, date)
        mobile_score, mobile_hours = self._calculate_mobile_score(user_id, date)
        location_score = self._calculate_location_score(user_email, date)
        balance_score = self._calculate_work_life_balance(user_id, date)
        
        # Weighted overall score
        weights = {
            'desktop': 0.5,    # Desktop usage most important
            'mobile': 0.2,     # Mobile usage moderate weight
            'location': 0.15,  # Location context
            'balance': 0.15,   # Work-life balance
        }
        
        overall_score = (
            desktop_score * weights['desktop'] +
            mobile_score * weights['mobile'] +
            location_score * weights['location'] +
            balance_score * weights['balance']
        )
        
        total_hours = desktop_hours + mobile_hours
        productive_hours = (desktop_hours * desktop_score) + (mobile_hours * mobile_score)
        
        return {
            'date': date,
            'overall_score': round(overall_score, 2),
            'desktop_score': round(desktop_score, 2),
            'mobile_score': round(mobile_score, 2),
            'location_score': round(location_score, 2),
            'work_life_balance': round(balance_score, 2),
            'total_hours': round(total_hours, 1),
            'productive_hours': round(productive_hours, 1),
            'breakdown': {
                'weights': weights,
                'desktop_hours': round(desktop_hours, 1),
                'mobile_hours': round(mobile_hours, 1),
            }
        }
    
    def _calculate_desktop_score(self, user_id: str, date: str) -> Tuple[float, float]:
        """Calculate desktop productivity score for the day."""
        if not self.desktop_db.exists():
            return 0.5, 0.0
        
        conn = sqlite3.connect(self.desktop_db)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT app_name, SUM(duration_seconds) as total_seconds
            FROM desktop_usage
            WHERE user_id = ?
              AND date(timestamp) = ?
            GROUP BY app_name
        ''', (user_id, date))
        
        total_time = 0
        weighted_time = 0
        
        for app_name, seconds in cursor.fetchall():
            total_time += seconds
            score = self.app_scores.get(app_name, 0.5)  # Default to neutral
            weighted_time += seconds * score
        
        conn.close()
        
        if total_time == 0:
            return 0.5, 0.0
        
        score = weighted_time / total_time
        hours = total_time / 3600.0
        
        return score, hours
    
    def _calculate_mobile_score(self, user_id: str, date: str) -> Tuple[float, float]:
        """Calculate mobile productivity score for the day."""
        if not self.mobile_db.exists():
            return 0.5, 0.0
        
        # Same logic as desktop
        # (Would use mobile-specific app scores)
        return 0.5, 0.0  # Placeholder until mobile native modules
    
    def _calculate_location_score(self, user_email: str, date: str) -> float:
        """Calculate location-based productivity score."""
        if not self.location_db.exists():
            return 0.5
        
        conn = sqlite3.connect(self.location_db)
        cursor = conn.cursor()
        
        # Check if user was at productive locations (office, coworking, etc.)
        cursor.execute('''
            SELECT COUNT(DISTINCT l.id)
            FROM locations l
            JOIN places p ON 
                ABS(l.lat - p.lat) < 0.001 AND
                ABS(l.lon - p.lon) < 0.001
            WHERE l.user_email = ?
              AND date(l.timestamp) = ?
              AND (p.name LIKE '%office%' OR p.name LIKE '%work%')
        ''', (user_email, date))
        
        office_points = cursor.fetchone()[0]
        
        # More time at productive locations = higher score
        if office_points > 20:  # Significant time at office
            score = 0.85
        elif office_points > 10:
            score = 0.75
        else:
            score = 0.6  # Working from home (neutral)
        
        conn.close()
        return score
    
    def _calculate_work_life_balance(self, user_id: str, date: str) -> float:
        """Calculate work-life balance score (lower after-hours work = higher score)."""
        if not self.desktop_db.exists():
            return 0.75
        
        conn = sqlite3.connect(self.desktop_db)
        cursor = conn.cursor()
        
        # Count work app usage after 6 PM
        cursor.execute('''
            SELECT SUM(duration_seconds)
            FROM desktop_usage
            WHERE user_id = ?
              AND date(timestamp) = ?
              AND CAST(strftime('%H', timestamp) AS INTEGER) >= 18
              AND app_name IN ('Slack', 'Email', 'Gmail', 'Outlook', 'VS Code', 'Terminal')
        ''', (user_id, date))
        
        after_hours_seconds = cursor.fetchone()[0] or 0
        after_hours_hours = after_hours_seconds / 3600.0
        
        conn.close()
        
        # Score decreases with more after-hours work
        if after_hours_hours == 0:
            return 1.0  # Perfect balance
        elif after_hours_hours < 1:
            return 0.9
        elif after_hours_hours < 2:
            return 0.75
        elif after_hours_hours < 3:
            return 0.6
        else:
            return 0.4  # Poor balance
    
    def get_weekly_trend(self, user_id: str = 'simon', days: int = 7) -> List[Dict]:
        """Get productivity scores for the last N days."""
        scores = []
        
        for i in range(days):
            date = (datetime.now() - timedelta(days=i)).strftime('%Y-%m-%d')
            score_data = self.calculate_daily_score(user_id, date)
            scores.append(score_data)
        
        return list(reversed(scores))  # Oldest to newest
    
    def get_insights(self, user_id: str = 'simon') -> List[str]:
        """Generate insights based on productivity trends."""
        insights = []
        
        # Get last 7 days
        trend = self.get_weekly_trend(user_id, 7)
        
        if len(trend) < 2:
            return insights
        
        # Check for improving trend
        recent_scores = [day['overall_score'] for day in trend[-3:]]
        earlier_scores = [day['overall_score'] for day in trend[:3]]
        
        if recent_scores and earlier_scores:
            recent_avg = sum(recent_scores) / len(recent_scores)
            earlier_avg = sum(earlier_scores) / len(earlier_scores)
            
            if recent_avg > earlier_avg + 0.1:
                insights.append(f"📈 **Productivity Improving:** +{(recent_avg - earlier_avg) * 100:.0f}% this week vs last week")
            elif recent_avg < earlier_avg - 0.1:
                insights.append(f"📉 **Productivity Declining:** {(earlier_avg - recent_avg) * 100:.0f}% drop this week")
        
        # Check today's score
        today = trend[-1]
        avg_score = sum(day['overall_score'] for day in trend) / len(trend)
        
        if today['overall_score'] > avg_score + 0.15:
            insights.append(f"🌟 **Exceptional Day:** {today['overall_score']:.0%} productivity (vs {avg_score:.0%} avg)")
        elif today['overall_score'] < avg_score - 0.15:
            insights.append(f"⚠️ **Below Average:** {today['overall_score']:.0%} productivity (vs {avg_score:.0%} avg)")
        
        # Check work-life balance
        balance_scores = [day['work_life_balance'] for day in trend]
        avg_balance = sum(balance_scores) / len(balance_scores)
        
        if avg_balance < 0.6:
            insights.append(f"🌙 **Balance Alert:** {avg_balance:.0%} work-life balance this week - consider boundaries")
        
        # Check deep work hours
        productive_hours = [day['productive_hours'] for day in trend]
        avg_productive = sum(productive_hours) / len(productive_hours)
        
        if avg_productive > 6:
            insights.append(f"💪 **Strong Focus:** {avg_productive:.1f}h productive work/day")
        elif avg_productive < 3:
            insights.append(f"⏰ **Low Focus:** Only {avg_productive:.1f}h productive work/day - increase deep work blocks")
        
        return insights


def main():
    """Test productivity scoring."""
    workspace = Path.home() / '.openclaw/workspace'
    scorer = ProductivityScorer(workspace)
    
    print("=== Today's Productivity Score ===")
    today = scorer.calculate_daily_score()
    print(f"Date: {today['date']}")
    print(f"Overall: {today['overall_score']:.0%}")
    print(f"  Desktop: {today['desktop_score']:.0%} ({today['breakdown']['desktop_hours']}h)")
    print(f"  Location: {today['location_score']:.0%}")
    print(f"  Balance: {today['work_life_balance']:.0%}")
    print(f"Productive Hours: {today['productive_hours']:.1f} / {today['total_hours']:.1f}")
    print()
    
    print("=== Weekly Trend ===")
    trend = scorer.get_weekly_trend(days=7)
    for day in trend:
        print(f"{day['date']}: {day['overall_score']:.0%} ({day['productive_hours']:.1f}h productive)")
    print()
    
    print("=== Insights ===")
    insights = scorer.get_insights()
    for insight in insights:
        print(f"  {insight}")


if __name__ == '__main__':
    main()
