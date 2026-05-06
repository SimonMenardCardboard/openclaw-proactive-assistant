#!/usr/bin/env python3
"""
Shopping List Parser

Extracts shopping/to-buy items from:
1. Emails to self ("Shopping: eggs, milk, coffee")
2. Task lists in emails
3. Reminder emails

Categories:
- Food/Groceries
- Household items
- Personal care
- Office supplies
- Other

Stores in context database shopping_lists table.
"""

import re
from datetime import datetime
from typing import Dict, List, Optional
from pathlib import Path
import sqlite3

# Food/grocery keywords
FOOD_KEYWORDS = [
    'eggs', 'milk', 'bread', 'cheese', 'butter', 'yogurt', 'chicken', 'beef', 'pork',
    'fish', 'salmon', 'tuna', 'rice', 'pasta', 'cereal', 'oatmeal',
    'apple', 'banana', 'orange', 'lettuce', 'tomato', 'onion', 'garlic', 'potato',
    'coffee', 'tea', 'juice', 'water', 'soda', 'beer', 'wine',
    'chips', 'crackers', 'cookies', 'snacks',
    'salt', 'pepper', 'oil', 'vinegar', 'sauce', 'ketchup', 'mustard',
]

# Household keywords
HOUSEHOLD_KEYWORDS = [
    'detergent', 'soap', 'shampoo', 'conditioner', 'toothpaste', 'deodorant',
    'toilet paper', 'paper towel', 'tissue', 'napkin',
    'light bulb', 'battery', 'batteries',
    'trash bag', 'zip lock', 'foil', 'wrap',
]

# Shopping list patterns
SHOPPING_PATTERNS = [
    r'shopping\s*(?:list)?:?\s*(.+)',
    r'to\s*buy:?\s*(.+)',
    r'need\s*to\s*get:?\s*(.+)',
    r'pick\s*up:?\s*(.+)',
    r'grocery\s*list:?\s*(.+)',
    r'don\'t\s*forget:?\s*(.+)',
]


class ShoppingListParser:
    """Parse and store shopping lists from emails."""
    
    def __init__(self, context_db_path: Optional[Path] = None):
        """
        Initialize shopping list parser.
        
        Args:
            context_db_path: Path to context database
        """
        if context_db_path is None:
            context_db_path = Path.home() / ".openclaw/workspace/transmogrifier/openclaw-proactive-assistant/proactive_system/context.db"
        
        self.context_db_path = Path(context_db_path)
        self._init_db()
    
    def _init_db(self):
        """Initialize shopping_lists table if not exists."""
        conn = sqlite3.connect(self.context_db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS shopping_lists (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                item TEXT NOT NULL,
                category TEXT,
                quantity TEXT,
                source TEXT,
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed BOOLEAN DEFAULT 0,
                completed_at TIMESTAMP
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def parse_from_email(self, email: Dict, user_email: str) -> List[Dict]:
        """
        Parse shopping list items from email.
        
        Args:
            email: Email dict with from, subject, body
            user_email: User's email address (to detect self-emails)
            
        Returns:
            List of shopping items
        """
        from_addr = self._extract_email(email.get('from', ''))
        subject = email.get('subject', '')
        body = email.get('body', '')
        
        # Only parse if email is from user to self
        if from_addr.lower() != user_email.lower():
            # Also check if it's a shared list or reminder
            if not any(keyword in subject.lower() for keyword in ['shopping', 'grocery', 'to buy', 'pick up']):
                return []
        
        text = f"{subject}\n{body}"
        items = []
        
        # Try to find shopping list patterns
        for pattern in SHOPPING_PATTERNS:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            
            for match in matches:
                items_text = match.group(1)
                
                # Parse items (comma/newline separated)
                parsed_items = self._parse_items_list(items_text)
                items.extend(parsed_items)
        
        # If no explicit shopping list found, scan for food keywords
        if not items:
            items = self._scan_for_items(text)
        
        # Add metadata
        source = f"email:{email.get('id', 'unknown')}:{email.get('date', 'unknown')}"
        
        for item in items:
            item['source'] = source
        
        return items
    
    def _parse_items_list(self, text: str) -> List[Dict]:
        """
        Parse comma/newline separated list of items.
        
        Returns list of dicts with item, quantity, category
        """
        items = []
        
        # Split by comma or newline
        parts = re.split(r'[,\n•\-]', text)
        
        for part in parts:
            part = part.strip()
            
            if not part or len(part) < 2:
                continue
            
            # Remove common prefixes
            part = re.sub(r'^(shopping|grocery|to buy|need to get|pick up):\s*', '', part, flags=re.IGNORECASE)
            part = part.strip()
            
            if not part or len(part) < 2:
                continue
            
            # Extract quantity if present (e.g., "2 eggs", "3x milk")
            quantity = None
            quantity_match = re.match(r'^(\d+x?|\d+\s*(?:lb|oz|kg|g|l|ml)?)\s+(.+)', part, re.IGNORECASE)
            
            if quantity_match:
                quantity = quantity_match.group(1).strip()
                part = quantity_match.group(2).strip()
            
            # Categorize item
            category = self._categorize_item(part)
            
            items.append({
                'item': part.lower(),
                'quantity': quantity,
                'category': category
            })
        
        return items
    
    def _scan_for_items(self, text: str) -> List[Dict]:
        """
        Scan text for known shopping items.
        
        Less aggressive - only picks up very obvious items.
        """
        items = []
        text_lower = text.lower()
        
        # Only scan if text is short (likely a quick note)
        if len(text) > 500:
            return []
        
        # Look for known food items
        for keyword in FOOD_KEYWORDS + HOUSEHOLD_KEYWORDS:
            if re.search(r'\b' + re.escape(keyword) + r'\b', text_lower):
                category = self._categorize_item(keyword)
                items.append({
                    'item': keyword,
                    'quantity': None,
                    'category': category
                })
        
        # Deduplicate
        seen = set()
        unique_items = []
        for item in items:
            if item['item'] not in seen:
                unique_items.append(item)
                seen.add(item['item'])
        
        return unique_items
    
    def _categorize_item(self, item: str) -> str:
        """Categorize shopping item."""
        item_lower = item.lower()
        
        if any(keyword in item_lower for keyword in FOOD_KEYWORDS):
            return 'food'
        elif any(keyword in item_lower for keyword in HOUSEHOLD_KEYWORDS):
            return 'household'
        elif any(keyword in item_lower for keyword in ['pen', 'paper', 'notebook', 'stapler', 'folder']):
            return 'office'
        else:
            return 'other'
    
    def save_items(self, items: List[Dict]):
        """
        Save shopping items to database.
        
        Args:
            items: List of item dicts
        """
        if not items:
            return
        
        conn = sqlite3.connect(self.context_db_path)
        cursor = conn.cursor()
        
        for item in items:
            # Check if item already exists and is not completed
            cursor.execute('''
                SELECT id FROM shopping_lists
                WHERE item = ? AND completed = 0
            ''', (item['item'],))
            
            existing = cursor.fetchone()
            
            if not existing:
                cursor.execute('''
                    INSERT INTO shopping_lists (item, category, quantity, source)
                    VALUES (?, ?, ?, ?)
                ''', (item['item'], item['category'], item.get('quantity'), item.get('source')))
        
        conn.commit()
        conn.close()
    
    def get_shopping_list(self, category: Optional[str] = None) -> List[Dict]:
        """
        Get current shopping list.
        
        Args:
            category: Filter by category (None = all)
            
        Returns:
            List of items
        """
        conn = sqlite3.connect(self.context_db_path)
        cursor = conn.cursor()
        
        if category:
            cursor.execute('''
                SELECT item, category, quantity, added_at
                FROM shopping_lists
                WHERE completed = 0 AND category = ?
                ORDER BY added_at DESC
            ''', (category,))
        else:
            cursor.execute('''
                SELECT item, category, quantity, added_at
                FROM shopping_lists
                WHERE completed = 0
                ORDER BY category, added_at DESC
            ''')
        
        items = []
        for row in cursor.fetchall():
            items.append({
                'item': row[0],
                'category': row[1],
                'quantity': row[2],
                'added_at': row[3]
            })
        
        conn.close()
        return items
    
    def mark_completed(self, item: str):
        """Mark item as completed."""
        conn = sqlite3.connect(self.context_db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE shopping_lists
            SET completed = 1, completed_at = CURRENT_TIMESTAMP
            WHERE item = ? AND completed = 0
        ''', (item,))
        
        conn.commit()
        conn.close()
    
    def _extract_email(self, email_str: str) -> str:
        """Extract email from 'Name <email>' format."""
        match = re.search(r'<(.+?)>', email_str)
        if match:
            return match.group(1).lower()
        return email_str.lower().strip()


def main():
    """Test shopping list parser."""
    parser = ShoppingListParser()
    
    # Test emails
    test_emails = [
        {
            'id': '1',
            'from': 'lacrosseguy76665@gmail.com',
            'subject': 'Shopping list',
            'body': 'Shopping: eggs, milk, bread, coffee, 2 lb chicken',
            'date': '2026-05-06'
        },
        {
            'id': '2',
            'from': 'lacrosseguy76665@gmail.com',
            'subject': 'Grocery reminder',
            'body': 'Don\'t forget:\n- Bananas\n- Yogurt\n- 3x cheese\n- Pasta',
            'date': '2026-05-06'
        },
        {
            'id': '3',
            'from': 'lacrosseguy76665@gmail.com',
            'subject': 'To buy',
            'body': 'Need to get: toilet paper, laundry detergent, batteries',
            'date': '2026-05-06'
        }
    ]
    
    print("Shopping List Parser Test")
    print("=" * 80)
    
    user_email = 'lacrosseguy76665@gmail.com'
    all_items = []
    
    for email in test_emails:
        print(f"\nEmail: {email['subject']}")
        print(f"Body: {email['body'][:60]}...")
        
        items = parser.parse_from_email(email, user_email)
        print(f"Items found: {len(items)}")
        
        for item in items:
            quantity = f"{item['quantity']} " if item.get('quantity') else ""
            print(f"  • {quantity}{item['item']} ({item['category']})")
            all_items.append(item)
    
    # Save to database
    parser.save_items(all_items)
    print(f"\n✅ Saved {len(all_items)} items to shopping list")
    
    # Retrieve shopping list
    print("\n\nCurrent Shopping List:")
    shopping_list = parser.get_shopping_list()
    
    by_category = {}
    for item in shopping_list:
        cat = item['category']
        if cat not in by_category:
            by_category[cat] = []
        by_category[cat].append(item)
    
    for category, items in by_category.items():
        print(f"\n{category.upper()}:")
        for item in items:
            quantity = f"{item['quantity']} " if item.get('quantity') else ""
            print(f"  • {quantity}{item['item']}")


if __name__ == '__main__':
    main()
