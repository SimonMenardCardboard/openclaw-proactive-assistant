#!/usr/bin/env python3
"""
User Preferences Management
Handles multi-account, multi-device configuration per user
"""

import json
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime


class UserPreferences:
    """Manage user preferences, connected accounts, and devices."""
    
    def __init__(self, user_id: str = 'default'):
        self.user_id = user_id
        self.config_dir = Path.home() / '.openclaw/config'
        self.config_dir.mkdir(parents=True, exist_ok=True)
        
        self.prefs_file = self.config_dir / f'{user_id}_preferences.json'
        self.prefs = self._load_or_create()
    
    def _load_or_create(self) -> Dict:
        """Load existing preferences or create default."""
        if self.prefs_file.exists():
            with open(self.prefs_file) as f:
                return json.load(f)
        
        # Default preferences
        default = {
            'user_id': self.user_id,
            'created_at': datetime.now().isoformat(),
            'primary_email': None,
            'timezone': 'America/Los_Angeles',
            
            'connected_accounts': {
                'google': [],
                'microsoft': [],
                'icloud': [],
                'imap': []
            },
            
            'notification_delivery': {
                'channel': 'telegram',  # telegram, push, sms, email
                'telegram': {
                    'chat_id': None
                },
                'push': {
                    'devices': []
                }
            },
            
            'quiet_hours': {
                'enabled': False,
                'start': '23:00',
                'end': '08:00'
            },
            
            'pattern_learning': {
                'enabled': True,
                'recommendation_frequency': 'every_4_hours'
            }
        }
        
        self.save(default)
        return default
    
    def save(self, prefs: Optional[Dict] = None):
        """Save preferences to disk."""
        if prefs is None:
            prefs = self.prefs
        
        with open(self.prefs_file, 'w') as f:
            json.dump(prefs, f, indent=2)
    
    # Account management
    
    def add_account(self, provider: str, email: str, label: str, token_file: str, 
                    features: Dict = None) -> bool:
        """Add a connected account."""
        if features is None:
            features = {'calendar': True, 'email': True}
        
        if provider not in self.prefs['connected_accounts']:
            self.prefs['connected_accounts'][provider] = []
        
        # Check if account already exists
        existing = next((a for a in self.prefs['connected_accounts'][provider] 
                        if a['email'] == email), None)
        
        account_entry = {
            'email': email,
            'label': label,
            'token_file': token_file,
            'features': features,
            'connected_at': datetime.now().isoformat()
        }
        
        if existing:
            # Update existing
            idx = self.prefs['connected_accounts'][provider].index(existing)
            self.prefs['connected_accounts'][provider][idx] = account_entry
        else:
            # Add new
            self.prefs['connected_accounts'][provider].append(account_entry)
        
        self.save()
        return True
    
    def remove_account(self, provider: str, email: str) -> bool:
        """Remove a connected account."""
        if provider not in self.prefs['connected_accounts']:
            return False
        
        accounts = self.prefs['connected_accounts'][provider]
        self.prefs['connected_accounts'][provider] = [
            a for a in accounts if a['email'] != email
        ]
        
        self.save()
        return True
    
    def get_accounts(self, provider: Optional[str] = None, feature: Optional[str] = None) -> List[Dict]:
        """
        Get connected accounts.
        
        Args:
            provider: Filter by provider (google, microsoft, icloud, imap)
            feature: Filter by feature (calendar, email)
        """
        if provider:
            accounts = self.prefs['connected_accounts'].get(provider, [])
        else:
            # All accounts
            accounts = []
            for accts in self.prefs['connected_accounts'].values():
                accounts.extend(accts)
        
        if feature:
            accounts = [a for a in accounts if a.get('features', {}).get(feature, False)]
        
        return accounts
    
    def get_token_path(self, provider: str, email: str) -> Optional[Path]:
        """Get token file path for an account."""
        accounts = self.prefs['connected_accounts'].get(provider, [])
        account = next((a for a in accounts if a['email'] == email), None)
        
        if account:
            token_dir = Path.home() / '.openclaw/tokens'
            return token_dir / account['token_file']
        
        return None
    
    # Device management
    
    def add_device(self, device_id: str, platform: str, token: str, name: str):
        """Add a device for push notifications."""
        devices = self.prefs['notification_delivery']['push']['devices']
        
        # Check if device exists
        existing = next((d for d in devices if d['id'] == device_id), None)
        
        device_entry = {
            'id': device_id,
            'platform': platform,  # ios, android, macos
            'token': token,
            'name': name,
            'added_at': datetime.now().isoformat()
        }
        
        if existing:
            idx = devices.index(existing)
            devices[idx] = device_entry
        else:
            devices.append(device_entry)
        
        self.save()
    
    def remove_device(self, device_id: str):
        """Remove a device."""
        devices = self.prefs['notification_delivery']['push']['devices']
        self.prefs['notification_delivery']['push']['devices'] = [
            d for d in devices if d['id'] != device_id
        ]
        self.save()
    
    def get_devices(self) -> List[Dict]:
        """Get all registered devices."""
        return self.prefs['notification_delivery']['push']['devices']


if __name__ == '__main__':
    # Test user preferences
    prefs = UserPreferences(user_id='test_user')
    
    # Add accounts
    prefs.add_account(
        provider='google',
        email='personal@gmail.com',
        label='Personal Gmail',
        token_file='test_user_google_personal.json',
        features={'calendar': True, 'email': True}
    )
    
    prefs.add_account(
        provider='google',
        email='work@company.com',
        label='Work Gmail',
        token_file='test_user_google_work.json',
        features={'calendar': True, 'email': True}
    )
    
    prefs.add_account(
        provider='imap',
        email='custom@domain.com',
        label='Custom Domain',
        token_file='test_user_imap_custom.json',
        features={'calendar': False, 'email': True}
    )
    
    # Add devices
    prefs.add_device(
        device_id='iphone_123',
        platform='ios',
        token='apns_token_...',
        name="User's iPhone"
    )
    
    prefs.add_device(
        device_id='mac_456',
        platform='macos',
        token='apns_token_...',
        name="User's MacBook"
    )
    
    print(f"✅ Created preferences for {prefs.user_id}")
    print(f"📧 Google accounts: {len(prefs.get_accounts('google'))}")
    print(f"📧 IMAP accounts: {len(prefs.get_accounts('imap'))}")
    print(f"📱 Devices: {len(prefs.get_devices())}")
    print(f"📁 Saved to: {prefs.prefs_file}")
