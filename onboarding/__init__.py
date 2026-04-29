"""
Transmogrifier Bootstrap Onboarding Package
Fast-path to value: 2-4 hour recommendations instead of 7+ days
"""

from .bootstrap import BootstrapOnboarding
from .oauth_webhook import OAuthWebhookHandler, webhook_handler, create_flask_route

__all__ = [
    'BootstrapOnboarding',
    'OAuthWebhookHandler',
    'webhook_handler',
    'create_flask_route',
]

__version__ = '1.0.0'
