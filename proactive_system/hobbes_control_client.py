#!/usr/bin/env python3
"""
Hobbes Control Client - V8.5 Federated Pattern Learning
Syncs patterns with central Hobbes Control for cross-user learning
"""

import requests
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class HobbesControlClient:
    """Client for Hobbes Control API - Federated pattern learning."""
    
    # Production Hobbes Control endpoint
    CONTROL_URL = "https://control.getcardboardai.com"
    
    def __init__(self, user_id: str = 'default', token: Optional[str] = None):
        self.user_id = user_id
        self.token = token or self._load_token()
        self.control_url = self.CONTROL_URL
    
    def _load_token(self) -> str:
        """Load Hobbes Control token from config."""
        token_file = Path.home() / '.openclaw/config/hobbes_control_token'
        
        if token_file.exists():
            return token_file.read_text().strip()
        
        # Generate and save if doesn't exist
        import secrets
        token = secrets.token_urlsafe(32)
        token_file.parent.mkdir(parents=True, exist_ok=True)
        token_file.write_text(token)
        logger.info(f"Generated new Hobbes Control token: {token_file}")
        return token
    
    def _headers(self) -> Dict:
        """Get request headers with auth."""
        return {
            'Authorization': f'Bearer {self.token}',
            'Content-Type': 'application/json',
            'X-User-ID': self.user_id
        }
    
    # Pattern Submission
    
    def submit_patterns(self, patterns: List[Dict]) -> bool:
        """
        Submit anonymized patterns to Hobbes Control.
        
        Args:
            patterns: List of pattern dicts (anonymized, no PII)
        
        Returns:
            Success boolean
        """
        try:
            response = requests.post(
                f"{self.control_url}/api/patterns/submit",
                headers=self._headers(),
                json={'patterns': patterns, 'user_id': self.user_id},
                timeout=30
            )
            
            if response.status_code == 200:
                logger.info(f"✅ Submitted {len(patterns)} patterns to Hobbes Control")
                return True
            else:
                logger.error(f"❌ Pattern submission failed: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Failed to submit patterns: {e}")
            return False
    
    # Federated Insights
    
    def get_federated_insights(self) -> List[Dict]:
        """
        Get cross-user insights from Hobbes Control.
        
        Returns:
            List of federated pattern insights
        """
        try:
            response = requests.get(
                f"{self.control_url}/api/patterns/insights",
                headers=self._headers(),
                params={'user_id': self.user_id},
                timeout=30
            )
            
            if response.status_code == 200:
                insights = response.json().get('insights', [])
                logger.info(f"✅ Retrieved {len(insights)} federated insights")
                return insights
            else:
                logger.warning(f"⚠️  No insights available: {response.status_code}")
                return []
                
        except Exception as e:
            logger.error(f"❌ Failed to get insights: {e}")
            return []
    
    # Shell Optimization Routing (NEW for Transmogrifier)
    
    def submit_shell_optimization(self, pattern: Dict, generated_code: Dict, user_id: str) -> str:
        """
        Submit shell command optimization to Hobbes Control for automated approval.
        
        Control plane will:
        1. Validate security (no sudo, no network, no PII access)
        2. Sandbox test on control VM
        3. Auto-approve if safe + beneficial
        4. Deploy to user VM if approved
        5. Notify user AFTER deployment (not before)
        
        Args:
            pattern: Detected shell pattern
            generated_code: Generated automation script
            user_id: User identifier
        
        Returns:
            control_id: Tracking ID from control plane
        """
        try:
            response = requests.post(
                f"{self.control_url}/api/shell/submit",
                headers=self._headers(),
                json={
                    'pattern': pattern,
                    'generated_code': generated_code,
                    'user_id': user_id,
                    'timestamp': datetime.now().isoformat()
                },
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                control_id = result.get('control_id', 'unknown')
                logger.info(f"✅ Shell optimization submitted to control: {control_id}")
                return control_id
            else:
                logger.error(f"❌ Shell optimization submission failed: {response.status_code}")
                raise Exception(f"Control plane returned {response.status_code}")
                
        except Exception as e:
            logger.error(f"❌ Failed to submit shell optimization: {e}")
            raise
    
    # Question Routing
    
    def route_question(self, question: str, context: Dict) -> Optional[Dict]:
        """
        Route edge case question to Hobbes Prime via Control.
        
        Args:
            question: User question
            context: Question context
        
        Returns:
            Response from Hobbes Prime or None
        """
        try:
            response = requests.post(
                f"{self.control_url}/api/questions/route",
                headers=self._headers(),
                json={
                    'question': question,
                    'context': context,
                    'user_id': self.user_id,
                    'timestamp': datetime.now().isoformat()
                },
                timeout=60  # Longer timeout for AI processing
            )
            
            if response.status_code == 200:
                result = response.json()
                logger.info(f"✅ Question routed to Hobbes Prime")
                return result
            else:
                logger.warning(f"⚠️  Question routing failed: {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"❌ Failed to route question: {e}")
            return None
    
    # Health Check
    
    def check_health(self) -> bool:
        """Check if Hobbes Control is reachable."""
        try:
            response = requests.get(
                f"{self.control_url}/api/health",
                timeout=10
            )
            
            return response.status_code == 200
            
        except Exception as e:
            logger.error(f"❌ Hobbes Control health check failed: {e}")
            return False
    
    # Stats
    
    def get_stats(self) -> Dict:
        """Get Hobbes Control network stats."""
        try:
            response = requests.get(
                f"{self.control_url}/api/stats",
                headers=self._headers(),
                timeout=10
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                return {}
                
        except Exception as e:
            logger.error(f"❌ Failed to get stats: {e}")
            return {}


if __name__ == '__main__':
    # Test Hobbes Control client
    client = HobbesControlClient(user_id='test_user')
    
    print("Testing Hobbes Control connection...")
    
    # Health check
    healthy = client.check_health()
    print(f"Health: {'✅ OK' if healthy else '❌ DOWN'}")
    
    if healthy:
        # Get stats
        stats = client.get_stats()
        print(f"\n📊 Network Stats:")
        print(json.dumps(stats, indent=2))
        
        # Test pattern submission (anonymized)
        test_patterns = [
            {
                'type': 'email_response_time',
                'avg_hours': 2.5,
                'confidence': 0.85
            },
            {
                'type': 'meeting_prep_time',
                'avg_minutes': 15,
                'confidence': 0.90
            }
        ]
        
        submitted = client.submit_patterns(test_patterns)
        print(f"\nPattern submission: {'✅ SUCCESS' if submitted else '❌ FAILED'}")
        
        # Get federated insights
        insights = client.get_federated_insights()
        print(f"\nFederated insights: {len(insights)} available")
        
    else:
        print("\n⚠️  Hobbes Control is not deployed yet")
        print("Run: See DEPLOY_NOW.md for deployment instructions")
