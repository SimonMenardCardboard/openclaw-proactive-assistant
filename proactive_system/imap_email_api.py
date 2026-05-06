#!/usr/bin/env python3
"""
IMAP Email API Implementation
Generic IMAP support for Yahoo, ProtonMail, custom domains, etc.
"""

import imaplib
import email
import re
from email.header import decode_header
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from collections import defaultdict
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ImapEmailAPI:
    """Generic IMAP email API."""
    
    def __init__(self, email: str, imap_host: str, imap_port: int = 993, password: str = None):
        self.email = email
        self.imap_host = imap_host
        self.imap_port = imap_port
        self.password = password
        self.connection = None
        self._connect()
    
    def _connect(self):
        """Connect to IMAP server."""
        try:
            self.connection = imaplib.IMAP4_SSL(self.imap_host, self.imap_port)
            self.connection.login(self.email, self.password)
            logger.info(f"[IMAP] Connected to {self.imap_host} for {self.email}")
        except Exception as e:
            logger.error(f"[IMAP] Connection failed: {e}")
            self.connection = None
    
    def _decode_header(self, header):
        """Decode email header."""
        if header is None:
            return ""
        
        decoded = decode_header(header)
        parts = []
        for content, encoding in decoded:
            if isinstance(content, bytes):
                parts.append(content.decode(encoding or 'utf-8', errors='ignore'))
            else:
                parts.append(content)
        return ''.join(parts)
    
    def get_unread_messages(self, hours_back: int = 1, max_results: int = 20) -> List[Dict]:
        """Get unread messages from last N hours."""
        if not self.connection:
            return []
        
        try:
            self.connection.select('INBOX')
            
            # Search for unread messages
            status, messages = self.connection.search(None, 'UNSEEN')
            
            if status != 'OK':
                return []
            
            message_ids = messages[0].split()
            parsed_messages = []
            
            for msg_id in message_ids[-max_results:]:
                status, msg_data = self.connection.fetch(msg_id, '(RFC822)')
                
                if status != 'OK':
                    continue
                
                msg = email.message_from_bytes(msg_data[0][1])
                parsed = self._parse_message(msg, msg_id.decode())
                
                # Check if within time range
                msg_date = self._parse_date(parsed['date'])
                if msg_date and msg_date > datetime.now() - timedelta(hours=hours_back):
                    parsed_messages.append(parsed)
            
            logger.info(f"[IMAP] {self.email}: {len(parsed_messages)} unread messages")
            return parsed_messages
            
        except Exception as e:
            logger.error(f"[IMAP] Error fetching messages: {e}")
            return []
    
    def get_all_messages_30_days(self, max_results: int = 500) -> List[Dict]:
        """Get ALL messages from last 30 days."""
        if not self.connection:
            return []
        
        try:
            self.connection.select('INBOX')
            
            # Calculate date 30 days ago
            since_date = (datetime.now() - timedelta(days=30)).strftime('%d-%b-%Y')
            
            # Search for messages since date
            status, messages = self.connection.search(None, f'(SINCE {since_date})')
            
            if status != 'OK':
                return []
            
            message_ids = messages[0].split()
            parsed_messages = []
            
            # Fetch messages (limit to max_results)
            for msg_id in message_ids[-max_results:]:
                try:
                    status, msg_data = self.connection.fetch(msg_id, '(RFC822)')
                    
                    if status != 'OK':
                        continue
                    
                    msg = email.message_from_bytes(msg_data[0][1])
                    parsed = self._parse_message(msg, msg_id.decode())
                    parsed_messages.append(parsed)
                    
                except Exception as e:
                    logger.warning(f"[IMAP] Failed to fetch message {msg_id}: {e}")
                    continue
            
            logger.info(f"[IMAP] {self.email}: {len(parsed_messages)} messages from last 30 days")
            return parsed_messages
            
        except Exception as e:
            logger.error(f"[IMAP] Error fetching 30-day messages: {e}")
            return []
    
    def _parse_message(self, msg, msg_id: str) -> Dict:
        """Parse email message to standard format."""
        # Extract body
        body = ""
        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_type() == "text/plain":
                    body = part.get_payload(decode=True).decode('utf-8', errors='ignore')
                    break
        else:
            body = msg.get_payload(decode=True).decode('utf-8', errors='ignore')
        
        return {
            'id': msg_id,
            'thread_id': msg.get('Message-ID', msg_id),
            'from': self._decode_header(msg.get('From', '')),
            'to': self._decode_header(msg.get('To', '')),
            'subject': self._decode_header(msg.get('Subject', '')),
            'date': msg.get('Date', ''),
            'snippet': body[:200] if body else '',
            'body': body,
            'labels': [],
            '_provider': 'imap',
            '_email': self.email
        }
    
    def _extract_email(self, email_str: str) -> str:
        """Extract email address from 'Name <email@domain.com>' format."""
        match = re.search(r'<(.+?)>', email_str)
        if match:
            return match.group(1).lower()
        return email_str.lower().strip()
    
    def _parse_date(self, date_str: str) -> Optional[datetime]:
        """Parse email date header."""
        try:
            from email.utils import parsedate_to_datetime
            return parsedate_to_datetime(date_str)
        except Exception:
            return datetime.now()
    
    def analyze_response_times(self, messages: List[Dict]) -> Dict[str, float]:
        """Calculate average response time per contact."""
        # Group by thread (Message-ID)
        threads = defaultdict(list)
        for msg in messages:
            threads[msg['thread_id']].append(msg)
        
        # Sort each thread by date
        for thread_id in threads:
            threads[thread_id].sort(key=lambda m: self._parse_date(m['date']))
        
        # Calculate response times
        contact_responses = defaultdict(list)
        
        for thread_id, thread_messages in threads.items():
            for i in range(len(thread_messages) - 1):
                current_msg = thread_messages[i]
                next_msg = thread_messages[i + 1]
                
                current_from = self._extract_email(current_msg['from'])
                next_from = self._extract_email(next_msg['from'])
                
                if current_from != self.email and next_from == self.email:
                    current_time = self._parse_date(current_msg['date'])
                    next_time = self._parse_date(next_msg['date'])
                    
                    if current_time and next_time:
                        response_hours = (next_time - current_time).total_seconds() / 3600
                        
                        if 0 < response_hours < 168:
                            contact_responses[current_from].append(response_hours)
        
        # Calculate averages
        avg_response_times = {}
        for contact, times in contact_responses.items():
            if times:
                avg_response_times[contact] = sum(times) / len(times)
        
        return avg_response_times
    
    def get_important_contacts(self, messages: List[Dict], top_n: int = 20) -> List[Dict]:
        """Score contacts by frequency + response speed."""
        contact_counts = defaultdict(int)
        contact_info = {}
        
        for msg in messages:
            from_email = self._extract_email(msg['from'])
            
            if from_email == self.email:
                continue
            
            contact_counts[from_email] += 1
            
            if from_email not in contact_info:
                contact_info[from_email] = {
                    'email': from_email,
                    'name': msg['from'].split('<')[0].strip() if '<' in msg['from'] else from_email,
                    'first_contact': self._parse_date(msg['date']),
                    'last_contact': self._parse_date(msg['date']),
                    'total_emails': 0
                }
            else:
                msg_date = self._parse_date(msg['date'])
                if msg_date < contact_info[from_email]['first_contact']:
                    contact_info[from_email]['first_contact'] = msg_date
                if msg_date > contact_info[from_email]['last_contact']:
                    contact_info[from_email]['last_contact'] = msg_date
            
            contact_info[from_email]['total_emails'] = contact_counts[from_email]
        
        # Get response times
        response_times = self.analyze_response_times(messages)
        
        # Calculate importance
        scored_contacts = []
        for email, info in contact_info.items():
            frequency_score = contact_counts[email]
            
            response_score = 0
            if email in response_times:
                avg_hours = response_times[email]
                response_score = max(1, 24 / max(avg_hours, 0.1))
            
            importance_score = frequency_score + (response_score * 2)
            
            scored_contacts.append({
                'email': email,
                'name': info['name'],
                'total_emails': contact_counts[email],
                'avg_response_hours': response_times.get(email),
                'importance_score': importance_score,
                'first_contact': info['first_contact'],
                'last_contact': info['last_contact']
            })
        
        scored_contacts.sort(key=lambda c: c['importance_score'], reverse=True)
        
        return scored_contacts[:top_n]
    
    def __del__(self):
        """Close IMAP connection."""
        if self.connection:
            try:
                self.connection.close()
                self.connection.logout()
            except:
                pass


if __name__ == '__main__':
    print("\\n" + "="*60)
    print("IMAP Email API - Test")
    print("="*60 + "\\n")
    
    print("⚠️  IMAP requires manual configuration:")
    print("   - IMAP host (e.g., imap.gmail.com)")
    print("   - IMAP port (usually 993)")
    print("   - Password or app-specific password")
    print()
    print("For testing, use UniversalEmailAPI with provider auto-detection.")
