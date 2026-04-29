#!/usr/bin/env python3
"""
OAuth Webhook Integration for Bootstrap Onboarding
Triggers bootstrap when user completes first OAuth
"""

import asyncio
import logging
from pathlib import Path
import sys

# Add paths
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'integrations/intelligence'))

from bootstrap import BootstrapOnboarding

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class OAuthWebhookHandler:
    """Handle OAuth completion and trigger bootstrap."""
    
    def __init__(self):
        self.user_bootstrap_status = {}  # Track who's been bootstrapped
    
    def is_first_oauth_complete(self, user_id: str) -> bool:
        """Check if this is the user's first complete OAuth."""
        # TODO: Check database for user's OAuth status
        # For now, check if we've already bootstrapped them
        return user_id not in self.user_bootstrap_status
    
    async def on_oauth_complete(self, user_id: str, provider: str, credentials: dict):
        """
        Called when user completes OAuth for any provider.
        
        Args:
            user_id: Unique user identifier
            provider: OAuth provider (gmail, outlook, etc)
            credentials: OAuth credentials dict
        """
        logger.info(f"OAuth complete: {user_id} → {provider}")
        
        # Check if this is first OAuth
        if self.is_first_oauth_complete(user_id):
            logger.info(f"First OAuth for {user_id} - triggering bootstrap")
            
            # Mark as bootstrapped (prevent duplicate triggers)
            self.user_bootstrap_status[user_id] = 'in_progress'
            
            # Trigger bootstrap asynchronously
            try:
                onboarding = BootstrapOnboarding(user_id)
                await onboarding.trigger()
                
                self.user_bootstrap_status[user_id] = 'complete'
                logger.info(f"✅ Bootstrap complete for {user_id}")
                
            except Exception as e:
                logger.error(f"❌ Bootstrap failed for {user_id}: {e}")
                self.user_bootstrap_status[user_id] = 'failed'
        else:
            logger.info(f"Additional OAuth for {user_id} - bootstrap already triggered")
    
    def get_bootstrap_status(self, user_id: str) -> str:
        """Get bootstrap status for a user."""
        return self.user_bootstrap_status.get(user_id, 'not_started')


# Global handler instance
webhook_handler = OAuthWebhookHandler()


# Flask integration (for COS oauth_manager.py)
def create_flask_route(app):
    """
    Add bootstrap webhook to Flask app.
    
    Usage in oauth_manager.py:
        from onboarding.oauth_webhook import create_flask_route
        create_flask_route(app)
    """
    
    @app.route('/oauth/webhook/bootstrap', methods=['POST'])
    async def bootstrap_webhook():
        """Webhook endpoint for OAuth completion."""
        from flask import request, jsonify
        
        data = request.json
        user_id = data.get('user_id')
        provider = data.get('provider')
        credentials = data.get('credentials')
        
        if not user_id or not provider:
            return jsonify({'error': 'Missing user_id or provider'}), 400
        
        # Trigger bootstrap
        await webhook_handler.on_oauth_complete(user_id, provider, credentials)
        
        return jsonify({
            'status': 'success',
            'bootstrap_status': webhook_handler.get_bootstrap_status(user_id)
        })
    
    @app.route('/oauth/webhook/bootstrap/status/<user_id>')
    def bootstrap_status(user_id: str):
        """Check bootstrap status for a user."""
        from flask import jsonify
        
        status = webhook_handler.get_bootstrap_status(user_id)
        
        return jsonify({
            'user_id': user_id,
            'bootstrap_status': status,
            'details': {
                'not_started': 'User has not completed OAuth',
                'in_progress': 'Bootstrap onboarding in progress',
                'complete': 'Bootstrap complete, recommendations queued',
                'failed': 'Bootstrap failed, check logs'
            }.get(status, 'Unknown status')
        })


if __name__ == '__main__':
    # Test the webhook handler
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python oauth_webhook.py <user_id>")
        sys.exit(1)
    
    user_id = sys.argv[1]
    
    print(f"\n🧪 Testing webhook handler for {user_id}...\n")
    
    # Simulate OAuth complete
    asyncio.run(webhook_handler.on_oauth_complete(
        user_id=user_id,
        provider='gmail',
        credentials={'access_token': 'test_token'}
    ))
    
    print(f"\n✅ Test complete!")
    print(f"   Status: {webhook_handler.get_bootstrap_status(user_id)}")
