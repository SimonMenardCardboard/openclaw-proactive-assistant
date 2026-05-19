#!/usr/bin/env python3
"""
V8 Text Approval Handler
Monitors for /v8-approve and /v8-decline commands
"""

import re
import sqlite3
import sys
from pathlib import Path
from datetime import datetime
import logging

sys.path.insert(0, str(Path(__file__).parent))
from v8_callback_handler import V8CallbackHandler

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def process_text_command(text: str, chat_id: str) -> str:
    """
    Process /v8-approve or /v8-decline command
    
    Args:
        text: Command text (e.g., "/v8-approve 103")
        chat_id: Telegram chat ID
    
    Returns:
        Response message
    """
    # Parse command (accept both /v8_approve_123 and /v8approve123)
    approve_match = re.match(r'/v8_?approve_?(\d+)', text, re.IGNORECASE)
    decline_match = re.match(r'/v8_?decline_?(\d+)', text, re.IGNORECASE)
    
    if not approve_match and not decline_match:
        return None  # Not a V8 command
    
    queue_id = int(approve_match.group(1) if approve_match else decline_match.group(1))
    is_approval = bool(approve_match)
    
    logger.info(f"Processing {'approval' if is_approval else 'decline'} for queue ID {queue_id}")
    
    # Get pattern from queue
    proactive_queue_db = Path.home() / '.openclaw/workspace/integrations/intelligence/proactive_queue.db'
    
    try:
        conn = sqlite3.connect(proactive_queue_db)
        cursor = conn.cursor()
        
        cursor.execute("SELECT context, message FROM proactive_queue WHERE id = ?", (queue_id,))
        row = cursor.fetchone()
        
        if not row:
            conn.close()
            return f"❌ Pattern #{queue_id} not found"
        
        import json
        context_json, original_message = row
        context = json.loads(context_json) if context_json else {}
        pattern = context.get('pattern', {})
        
        if is_approval:
            # Mark as approved
            cursor.execute("""
                UPDATE proactive_queue 
                SET action_approved = 1 
                WHERE id = ?
            """, (queue_id,))
            conn.commit()
            conn.close()
            
            logger.info(f"✅ Approved optimization for queue ID {queue_id}")
            
            # Generate and deploy optimization
            handler = V8CallbackHandler()
            success, result_message = handler._generate_optimization(pattern)
            
            if success:
                return f"✅ **Optimization Approved & Deployed**\n\n{result_message}"
            else:
                return f"⚠️ **Optimization Approved (Deployment Failed)**\n\n{result_message}"
        
        else:
            # Mark as declined
            cursor.execute("""
                UPDATE proactive_queue 
                SET action_approved = 0 
                WHERE id = ?
            """, (queue_id,))
            conn.commit()
            conn.close()
            
            logger.info(f"❌ Declined optimization for queue ID {queue_id}")
            
            return f"❌ **Declined**\n\nPattern #{queue_id} - No optimization will be created."
    
    except Exception as e:
        logger.error(f"Error processing command: {e}", exc_info=True)
        return f"❌ Error: {str(e)}"


if __name__ == '__main__':
    # Test
    import sys
    if len(sys.argv) > 1:
        text = ' '.join(sys.argv[1:])
        result = process_text_command(text, '8451730454')
        print(result)
