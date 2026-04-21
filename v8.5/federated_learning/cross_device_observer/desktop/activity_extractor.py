#!/usr/bin/env python3
"""
V8 Cross-Device Observer - Activity Extractor

Extracts user activities from screenshots using OCR and image analysis.

Features:
- OCR text extraction (window titles, app names, UI elements)
- Application detection
- Action inference (typing, clicking, scrolling based on UI changes)
- Privacy filtering (redact sensitive information)

Privacy controls:
- Filter out sensitive keywords (passwords, tokens, credit cards)
- Redact personal information
- Only extract high-level activity patterns
"""

import logging
from typing import Dict, Any, List, Optional
from pathlib import Path
import json
import re

logger = logging.getLogger('v8.cross_device.activity_extractor')


class ActivityExtractor:
    """Extract user activities from screenshots."""
    
    def __init__(self, privacy_filters: Optional[List[str]] = None):
        """
        Initialize activity extractor.
        
        Args:
            privacy_filters: List of keywords to filter/redact
        """
        if privacy_filters is None:
            privacy_filters = [
                'password', 'passwd', 'pwd',
                'token', 'api_key', 'apikey', 'secret',
                'credit_card', 'creditcard', 'card_number',
                'ssn', 'social_security',
                'private_key', 'privatekey',
                'bearer', 'authorization'
            ]
        
        self.privacy_filters = [f.lower() for f in privacy_filters]
        
        # Common app indicators
        self.app_indicators = {
            'chrome': ['Google Chrome', 'chrome', 'www.', 'http'],
            'safari': ['Safari', 'safari'],
            'mail': ['Mail', 'Inbox', 'Compose', 'Send', 'email'],
            'slack': ['Slack', 'Direct Messages', 'Channels'],
            'terminal': ['Terminal', 'bash', 'zsh', 'command'],
            'vscode': ['Visual Studio Code', 'VS Code', 'vscode'],
            'finder': ['Finder'],
        }
    
    def extract_from_screenshot(self, screenshot_path: Path) -> Dict[str, Any]:
        """
        Extract activity from a screenshot.
        
        Args:
            screenshot_path: Path to screenshot image
            
        Returns:
            Dictionary with extracted activity data
        """
        try:
            import pytesseract
            from PIL import Image
            
            logger.info(f"Extracting activity from: {screenshot_path}")
            
            # Open image
            image = Image.open(str(screenshot_path))
            
            # Extract text via OCR
            text = pytesseract.image_to_string(image)
            
            # Apply privacy filtering
            filtered_text = self._filter_sensitive_data(text)
            
            # Extract activity components
            activity = {
                'timestamp': screenshot_path.stem.split('_')[-2:] if '_' in screenshot_path.stem else None,
                'app_name': self._detect_app(filtered_text),
                'window_title': self._extract_window_title(filtered_text),
                'action_type': self._infer_action_type(filtered_text),
                'text_summary': self._summarize_text(filtered_text),
                'raw_text_length': len(text),  # Track how much was captured
                'filtered': True
            }
            
            logger.debug(f"Extracted activity: {activity['app_name']} - {activity['action_type']}")
            
            return activity
            
        except ImportError:
            logger.error("pytesseract not installed. Install with: pip install pytesseract")
            logger.error("Also ensure tesseract is installed: brew install tesseract")
            return {'error': 'pytesseract not installed'}
        except Exception as e:
            logger.error(f"Error extracting activity: {e}")
            return {'error': str(e)}
    
    def _filter_sensitive_data(self, text: str) -> str:
        """
        Filter out sensitive information from extracted text.
        
        Args:
            text: Raw OCR text
            
        Returns:
            Filtered text with sensitive data redacted
        """
        filtered = text
        
        # Redact lines containing sensitive keywords
        lines = filtered.split('\n')
        filtered_lines = []
        
        for line in lines:
            line_lower = line.lower()
            
            # Check for sensitive keywords
            is_sensitive = any(keyword in line_lower for keyword in self.privacy_filters)
            
            if is_sensitive:
                filtered_lines.append('[REDACTED]')
            else:
                # Also redact things that look like credentials
                # Credit card pattern
                line = re.sub(r'\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b', '[REDACTED-CARD]', line)
                
                # API key/token patterns (long alphanumeric strings)
                line = re.sub(r'\b[A-Za-z0-9]{32,}\b', '[REDACTED-TOKEN]', line)
                
                # Email addresses (optional - keep for now as they're less sensitive)
                # line = re.sub(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', '[REDACTED-EMAIL]', line)
                
                filtered_lines.append(line)
        
        return '\n'.join(filtered_lines)
    
    def _detect_app(self, text: str) -> Optional[str]:
        """
        Detect which application is active based on OCR text.
        
        Args:
            text: OCR text from screenshot
            
        Returns:
            Detected app name or 'Unknown'
        """
        text_lower = text.lower()
        
        for app, indicators in self.app_indicators.items():
            for indicator in indicators:
                if indicator.lower() in text_lower:
                    return app.capitalize()
        
        return 'Unknown'
    
    def _extract_window_title(self, text: str) -> Optional[str]:
        """
        Extract window title from OCR text.
        
        Window titles are usually at the top of the screen.
        
        Args:
            text: OCR text from screenshot
            
        Returns:
            Window title or None
        """
        lines = text.split('\n')
        
        # Usually the window title is one of the first few lines
        # Look for a line that's not too long and not too short
        for line in lines[:5]:
            line = line.strip()
            if 5 < len(line) < 100:
                # Avoid lines that look like menu items or toolbars
                if not any(x in line.lower() for x in ['file', 'edit', 'view', 'help', 'window']):
                    return line
        
        return None
    
    def _infer_action_type(self, text: str) -> str:
        """
        Infer the type of action being performed based on text content.
        
        Args:
            text: OCR text from screenshot
            
        Returns:
            Action type: 'typing', 'browsing', 'reading', 'editing', etc.
        """
        text_lower = text.lower()
        
        # Check for indicators of different actions
        if any(word in text_lower for word in ['compose', 'reply', 'write', 'draft']):
            return 'composing'
        
        if any(word in text_lower for word in ['code', 'function', 'class', 'def', 'import']):
            return 'coding'
        
        if any(word in text_lower for word in ['inbox', 'unread', 'email', 'message']):
            return 'reading_email'
        
        if any(word in text_lower for word in ['search', 'google', 'results']):
            return 'searching'
        
        if any(word in text_lower for word in ['file', 'folder', 'directory']):
            return 'file_management'
        
        if len(text) > 500:
            return 'reading'
        
        return 'active'
    
    def _summarize_text(self, text: str, max_length: int = 200) -> str:
        """
        Create a brief summary of the extracted text.
        
        Args:
            text: Full OCR text
            max_length: Maximum length of summary
            
        Returns:
            Text summary
        """
        # Remove extra whitespace
        text = ' '.join(text.split())
        
        if len(text) <= max_length:
            return text
        
        # Truncate and add ellipsis
        return text[:max_length] + '...'
    
    def extract_pattern_from_sequence(self, activities: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Identify patterns from a sequence of activities.
        
        Args:
            activities: List of activity dictionaries
            
        Returns:
            Detected pattern information
        """
        if not activities:
            return {'pattern': 'none'}
        
        # Analyze app switching patterns
        app_sequence = [a.get('app_name') for a in activities if a.get('app_name')]
        
        # Count app frequencies
        app_counts = {}
        for app in app_sequence:
            app_counts[app] = app_counts.get(app, 0) + 1
        
        # Detect repeated sequences
        if len(app_sequence) >= 3:
            for i in range(len(app_sequence) - 2):
                seq = tuple(app_sequence[i:i+3])
                count = sum(1 for j in range(len(app_sequence) - 2) 
                           if tuple(app_sequence[j:j+3]) == seq)
                
                if count >= 2:
                    return {
                        'pattern': 'repeated_app_switch',
                        'sequence': list(seq),
                        'frequency': count,
                        'description': f"User repeatedly switches: {' → '.join(seq)}"
                    }
        
        # Detect prolonged focus
        if len(activities) >= 5:
            most_used_app = max(app_counts.items(), key=lambda x: x[1])[0]
            if app_counts[most_used_app] > len(activities) * 0.7:
                return {
                    'pattern': 'focused_work',
                    'app': most_used_app,
                    'duration_samples': app_counts[most_used_app],
                    'description': f"Focused work in {most_used_app}"
                }
        
        return {
            'pattern': 'varied_activity',
            'app_counts': app_counts
        }


if __name__ == '__main__':
    # Test activity extractor
    print("\n=== Activity Extractor Test ===\n")
    
    extractor = ActivityExtractor()
    
    print("Privacy filters active:")
    for filter in extractor.privacy_filters[:5]:
        print(f"  - {filter}")
    print(f"  ... and {len(extractor.privacy_filters) - 5} more")
    
    print("\nApplication indicators:")
    for app in list(extractor.app_indicators.keys())[:5]:
        print(f"  - {app}")
    
    print("\nNote: To test OCR extraction:")
    print("  1. Install tesseract: brew install tesseract")
    print("  2. Install pytesseract: pip install pytesseract")
    print("  3. Provide a screenshot path to extract_from_screenshot()")
    
    # Test privacy filtering
    test_text = """
    User Dashboard
    Welcome, John!
    Password: mysecret123
    API Key: sk_live_YOUR_KEY_HERE
    Credit Card: 4532 1234 5678 9010
    Normal text here
    """
    
    print("\n--- Privacy Filtering Test ---")
    print("Original text length:", len(test_text))
    filtered = extractor._filter_sensitive_data(test_text)
    print("Filtered text length:", len(filtered))
    print("\nFiltered output:")
    print(filtered)
