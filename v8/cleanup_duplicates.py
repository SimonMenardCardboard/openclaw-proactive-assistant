#!/usr/bin/env python3
"""Clean up duplicate V8 proposals"""

import sqlite3
from pathlib import Path

db_path = Path.home() / '.openclaw/workspace/integrations/intelligence/v8_meta_learning/approvals.db'

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Get all pending proposals
cursor.execute("""
    SELECT id, script_name, proposed_at
    FROM proposals
    WHERE status = 'pending'
    ORDER BY script_name, proposed_at
""")

proposals = cursor.fetchall()

# Group by script_name
from collections import defaultdict
groups = defaultdict(list)

for prop_id, script_name, proposed_at in proposals:
    groups[script_name].append((prop_id, proposed_at))

# Keep oldest, reject duplicates
rejected_count = 0
kept_count = 0

for script_name, props in groups.items():
    # Sort by proposed_at (oldest first)
    props.sort(key=lambda x: x[1])
    
    # Keep first (oldest)
    kept_id = props[0][0]
    kept_count += 1
    print(f"✅ Keeping {script_name} (ID {kept_id})")
    
    # Reject rest
    for prop_id, _ in props[1:]:
        cursor.execute("""
            UPDATE proposals
            SET status = 'rejected',
                reviewed_at = datetime('now'),
                reviewer_notes = 'Duplicate proposal (auto-cleanup)'
            WHERE id = ?
        """, (prop_id,))
        rejected_count += 1

conn.commit()
conn.close()

print(f"\n📊 Cleanup Complete")
print(f"   Kept: {kept_count} unique proposals")
print(f"   Rejected: {rejected_count} duplicates")
