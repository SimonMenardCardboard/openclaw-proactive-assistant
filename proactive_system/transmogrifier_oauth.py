"""
Transmogrifier OAuth Configuration

All OAuth tokens for Transmogrifier app (publishing-ready product).
Directory: ~/.openclaw/workspace/transmogrifier/openclaw-proactive-assistant/config/

NOT COS-specific, NOT CLI - pure Transmogrifier app OAuth.
"""

from pathlib import Path
from typing import Dict

TRANSMOGRIFIER_CONFIG_DIR = Path.home() / '.openclaw/workspace/transmogrifier/openclaw-proactive-assistant/config'

TRANSMOGRIFIER_TOKENS = {
    'lacrosseguy76665@gmail.com': TRANSMOGRIFIER_CONFIG_DIR / 'default_google_personal.json',
    'simon@legalmensch.com': TRANSMOGRIFIER_CONFIG_DIR / 'default_google_work.json',
    'simon@sigmasight.ai': TRANSMOGRIFIER_CONFIG_DIR / 'default_google_sigmasight.json',
    'tmenard1@tulane.edu': TRANSMOGRIFIER_CONFIG_DIR / 'default_google_school.json',
}

def get_transmogrifier_token_path(email: str) -> Path:
    return TRANSMOGRIFIER_TOKENS.get(email, TRANSMOGRIFIER_CONFIG_DIR / 'default_google_personal.json')

def get_all_accounts() -> Dict[str, Path]:
    return TRANSMOGRIFIER_TOKENS.copy()
