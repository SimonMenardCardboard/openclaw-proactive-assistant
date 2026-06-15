#!/usr/bin/env python3
"""
Unsnooze cron for proactive_queue.

Runs every few minutes (via cron or the coordinator loop) and resets
snoozed recommendations back to 'pending' when their snooze_until has passed.

Usage:
    python3 unsnooze_queue.py          # run once
    python3 unsnooze_queue.py --daemon  # loop every 60s
"""

import sys
import time
import sqlite3
import logging
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from tm_paths import QUEUE_DB

logging.basicConfig(level=logging.INFO, format='%(asctime)s [UNSNOOZE] %(message)s')
logger = logging.getLogger(__name__)


def unsnooze_due(db_path: Path = QUEUE_DB) -> int:
    """
    Reset snoozed items whose snoozed_until has passed back to 'pending'.
    Returns number of items unsnoozed.
    """
    if not db_path.exists():
        return 0

    conn = sqlite3.connect(db_path)
    cursor = conn.execute("""
        UPDATE proactive_queue
        SET status = 'pending', snoozed_until = NULL
        WHERE status = 'snoozed'
          AND snoozed_until IS NOT NULL
          AND snoozed_until <= datetime('now')
    """)
    count = cursor.rowcount
    conn.commit()
    conn.close()

    if count > 0:
        logger.info(f"Unsnoozed {count} recommendation(s)")

    return count


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--daemon', action='store_true', help='Run in loop every 60s')
    parser.add_argument('--interval', type=int, default=60)
    args = parser.parse_args()

    if args.daemon:
        logger.info(f"Running unsnooze daemon (every {args.interval}s)")
        while True:
            unsnooze_due()
            time.sleep(args.interval)
    else:
        n = unsnooze_due()
        print(f"Unsnoozed {n} item(s)")
