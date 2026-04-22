#!/usr/bin/env python3
"""
Email Intelligence - Analyze emails via OAuth

Supports:
- Gmail (via Google OAuth)
- Outlook (via Microsoft OAuth)
- IMAP (via credentials)

Features:
- Unread count
- Important emails detection
- Smart categorization
- Reply suggestions
- Deadline detection
"""

import os
import json
import pickle
from datetime import datetime, timedelta
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import base64
import re

# Paths
GOOGLE_TOKEN_PATH = os.path.expanduser('~/workspace/integrations/direct_api/token.json')
GOOGLE_TOKEN_PATH_2 = os.path.expanduser('~/workspace/integrations/direct_api/token_simon_at_legalmensch_com.json')

def load_google_credentials():
    """Load Google OAuth credentials"""
    creds = None
    
    # Try multiple token paths
    token_paths = [GOOGLE_TOKEN_PATH, GOOGLE_TOKEN_PATH_2]
    
    for token_path in token_paths:
        if os.path.exists(token_path):
            try:
                creds = Credentials.from_authorized_user_file(token_path)
                
                # Refresh if expired
                if creds and creds.expired and creds.refresh_token:
                    creds.refresh(Request())
                    
                    # Save refreshed token
                    with open(token_path, 'w') as token:
                        token.write(creds.to_json())
                
                if creds and creds.valid:
                    return creds
            except Exception as e:
                print(f"Error loading {token_path}: {e}")
                continue
    
    return None

def get_gmail_messages(max_results=20):
    """Fetch recent Gmail messages"""
    try:
        creds = load_google_credentials()
        if not creds:
            return None
        
        service = build('gmail', 'v1', credentials=creds)
        
        # Get unread messages
        results = service.users().messages().list(
            userId='me',
            maxResults=max_results,
            q='is:unread'
        ).execute()
        
        messages = results.get('messages', [])
        
        detailed_messages = []
        for msg in messages:
            try:
                message = service.users().messages().get(
                    userId='me',
                    id=msg['id'],
                    format='full'
                ).execute()
                
                detailed_messages.append(message)
            except Exception as e:
                print(f"Error fetching message {msg['id']}: {e}")
                continue
        
        return detailed_messages
    except HttpError as error:
        print(f'Gmail API error: {error}')
        return None
    except Exception as e:
        print(f'Error: {e}')
        return None

def extract_email_data(message):
    """Extract relevant data from Gmail message"""
    try:
        headers = message.get('payload', {}).get('headers', [])
        
        # Extract headers
        subject = next((h['value'] for h in headers if h['name'] == 'Subject'), 'No subject')
        sender = next((h['value'] for h in headers if h['name'] == 'From'), 'Unknown')
        date_str = next((h['value'] for h in headers if h['name'] == 'Date'), '')
        
        # Parse date
        try:
            date = datetime.strptime(date_str.split('(')[0].strip(), '%a, %d %b %Y %H:%M:%S %z')
        except:
            date = datetime.now()
        
        # Extract snippet
        snippet = message.get('snippet', '')
        
        # Get body (simplified)
        body = ''
        if 'parts' in message.get('payload', {}):
            for part in message['payload']['parts']:
                if part.get('mimeType') == 'text/plain':
                    body_data = part.get('body', {}).get('data', '')
                    if body_data:
                        body = base64.urlsafe_b64decode(body_data).decode('utf-8', errors='ignore')
                        break
        
        if not body:
            body = snippet
        
        return {
            'id': message['id'],
            'subject': subject,
            'sender': sender,
            'date': date.isoformat(),
            'snippet': snippet,
            'body': body[:500],  # First 500 chars
        }
    except Exception as e:
        print(f"Error extracting email data: {e}")
        return None

def categorize_email(email_data):
    """Categorize email by importance and type"""
    subject = email_data.get('subject', '').lower()
    body = email_data.get('body', '').lower()
    sender = email_data.get('sender', '').lower()
    
    # Important keywords
    urgent_keywords = ['urgent', 'asap', 'important', 'critical', 'deadline', 'immediate']
    action_keywords = ['action required', 'please review', 'needs attention', 'approval needed']
    meeting_keywords = ['meeting', 'call', 'zoom', 'teams', 'calendar invite']
    newsletter_keywords = ['unsubscribe', 'newsletter', 'digest', 'weekly update']
    
    category = {
        'importance': 'normal',
        'type': 'general',
        'action_required': False,
        'has_deadline': False,
    }
    
    # Check importance
    if any(keyword in subject or keyword in body for keyword in urgent_keywords):
        category['importance'] = 'high'
        category['action_required'] = True
    
    if any(keyword in subject or keyword in body for keyword in action_keywords):
        category['action_required'] = True
    
    # Check type
    if any(keyword in subject for keyword in meeting_keywords):
        category['type'] = 'meeting'
    elif any(keyword in subject or keyword in body for keyword in newsletter_keywords):
        category['type'] = 'newsletter'
        category['importance'] = 'low'
    elif 'noreply' in sender or 'no-reply' in sender:
        category['type'] = 'automated'
        category['importance'] = 'low'
    
    # Detect deadlines
    deadline_patterns = [
        r'by (\w+ \d+)',
        r'due (\w+ \d+)',
        r'deadline[:\s]+(\w+ \d+)',
        r'expires? (\w+ \d+)',
    ]
    
    for pattern in deadline_patterns:
        match = re.search(pattern, body, re.IGNORECASE)
        if match:
            category['has_deadline'] = True
            category['deadline_text'] = match.group(1)
            break
    
    return category

def generate_email_summary(messages):
    """Generate intelligence summary from emails"""
    if not messages:
        return {
            'unread_count': 0,
            'important_emails': [],
            'upcoming_deadlines': [],
            'meeting_invites': [],
            'suggested_replies': [],
            'categories': {
                'high_importance': 0,
                'action_required': 0,
                'meetings': 0,
                'newsletters': 0,
            }
        }
    
    important_emails = []
    deadlines = []
    meetings = []
    categories_count = {
        'high_importance': 0,
        'action_required': 0,
        'meetings': 0,
        'newsletters': 0,
    }
    
    for msg in messages:
        email_data = extract_email_data(msg)
        if not email_data:
            continue
        
        category = categorize_email(email_data)
        
        # Add category to email data
        email_data['category'] = category
        
        # Count categories
        if category['importance'] == 'high':
            categories_count['high_importance'] += 1
            important_emails.append(email_data)
        
        if category['action_required']:
            categories_count['action_required'] += 1
        
        if category['type'] == 'meeting':
            categories_count['meetings'] += 1
            meetings.append(email_data)
        
        if category['type'] == 'newsletter':
            categories_count['newsletters'] += 1
        
        if category['has_deadline']:
            deadlines.append({
                'subject': email_data['subject'],
                'deadline': category.get('deadline_text', 'Unknown'),
                'sender': email_data['sender'],
            })
    
    # Sort by importance
    important_emails.sort(key=lambda x: x['category']['importance'], reverse=True)
    
    return {
        'unread_count': len(messages),
        'important_emails': important_emails[:5],  # Top 5
        'upcoming_deadlines': deadlines[:5],
        'meeting_invites': meetings[:5],
        'suggested_replies': [],  # TODO: Generate reply suggestions
        'categories': categories_count,
        'oauth_status': 'connected',
        'last_check': datetime.utcnow().isoformat(),
    }

def get_email_intelligence():
    """Main function to get email intelligence"""
    try:
        messages = get_gmail_messages(max_results=50)
        
        if messages is None:
            return {
                'success': False,
                'error': 'OAuth not configured or expired',
                'hint': 'Please reconnect your email account in Settings'
            }
        
        summary = generate_email_summary(messages)
        
        return {
            'success': True,
            'email_summary': summary
        }
    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }

if __name__ == '__main__':
    # Test
    result = get_email_intelligence()
    print(json.dumps(result, indent=2))
