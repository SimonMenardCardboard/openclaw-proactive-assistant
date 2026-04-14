#!/usr/bin/env python3
"""
V8 Approval Workflow - Phase 2

Manages human approval of auto-generated optimizations.

Flow:
1. V8 detects pattern → generates code
2. Save proposal to review queue
3. Notify human (Telegram)
4. Human reviews → approves/rejects
5. If approved → deploy automatically
6. Track results → update V8 confidence
"""

import sqlite3
import json
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional

# Import sandbox for testing and time savings estimator
sys.path.insert(0, str(Path(__file__).parent))
from sandbox_executor import SandboxExecutor
from time_savings_estimator import TimeSavingsEstimator


class ApprovalWorkflow:
    """Manage optimization approval queue"""
    
    def __init__(self, db_path: Path = None, enable_sandbox: bool = True):
        if db_path is None:
            db_path = Path.home() / '.openclaw/workspace/integrations/intelligence/v8_meta_learning/approvals.db'
        
        self.db_path = db_path
        self.enable_sandbox = enable_sandbox
        self.sandbox = SandboxExecutor() if enable_sandbox else None
        self.time_estimator = TimeSavingsEstimator()
        self._init_db()
    
    def _init_db(self):
        """Initialize approval database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS proposals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pattern_type TEXT,
                pattern_data TEXT,
                generated_code TEXT,
                script_name TEXT,
                language TEXT,
                confidence REAL,
                estimated_savings_seconds REAL,
                estimated_savings_weekly_seconds REAL,
                status TEXT DEFAULT 'pending',
                sandbox_tested BOOLEAN DEFAULT FALSE,
                sandbox_passed BOOLEAN DEFAULT FALSE,
                sandbox_warnings TEXT,
                proposed_at TEXT DEFAULT CURRENT_TIMESTAMP,
                reviewed_at TEXT,
                reviewer_notes TEXT,
                deployed_at TEXT,
                deployment_result TEXT
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS deployment_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                proposal_id INTEGER,
                deployed_at TEXT,
                success BOOLEAN,
                error TEXT,
                actual_savings TEXT,
                measured_at TEXT,
                FOREIGN KEY (proposal_id) REFERENCES proposals(id)
            )
        """)
        
        conn.commit()
        conn.close()
    
    def submit_proposal(self, pattern: Dict, generated_code: Dict) -> int:
        """
        Submit a new optimization proposal for review.
        
        Auto-tests in sandbox if enabled.
        Calculates time savings estimate.
        
        Returns: proposal_id
        """
        # Calculate time savings estimate
        time_savings = self.time_estimator.estimate_savings(pattern)
        per_use_seconds = time_savings['per_use_seconds']
        weekly_seconds = time_savings['weekly_seconds']
        
        # Format human-readable savings
        if weekly_seconds >= 3600:  # >= 1 hour
            savings_str = f"{weekly_seconds / 3600:.1f} hr/week"
        elif weekly_seconds >= 60:  # >= 1 minute
            savings_str = f"{weekly_seconds / 60:.0f} min/week"
        else:
            savings_str = f"{weekly_seconds:.0f} sec/week"
        
        # Test in sandbox first (if enabled)
        sandbox_tested = False
        sandbox_passed = False
        sandbox_warnings = []
        
        if self.enable_sandbox and self.sandbox:
            try:
                test_result = self.sandbox.test_optimization({
                    'code': generated_code.get('code', ''),
                    'language': generated_code.get('language', 'python'),
                    'name': generated_code.get('script_name', 'unknown'),
                    'type': pattern.get('type', 'unknown'),
                    'confidence': pattern.get('confidence', 0.0)
                })
                
                sandbox_tested = True
                sandbox_passed = test_result['test_passed']
                sandbox_warnings = test_result.get('warnings', [])
            
            except Exception as e:
                sandbox_warnings = [f'Sandbox test failed: {str(e)}']
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO proposals 
            (pattern_type, pattern_data, generated_code, script_name, 
             language, confidence, estimated_savings_seconds, 
             estimated_savings_weekly_seconds, sandbox_tested, 
             sandbox_passed, sandbox_warnings)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            pattern.get('type'),
            json.dumps(pattern),
            generated_code.get('code'),
            generated_code.get('script_name'),
            generated_code.get('language'),
            pattern.get('confidence', 0.0),
            per_use_seconds,
            weekly_seconds,
            sandbox_tested,
            sandbox_passed,
            json.dumps(sandbox_warnings) if sandbox_warnings else None
        ))
        
        proposal_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        # Store in time savings database
        optimization_id = generated_code.get('script_name', f'proposal_{proposal_id}')
        self.time_estimator.record_deployment(optimization_id, pattern, time_savings)
        
        return proposal_id
    
    def get_pending(self) -> List[Dict]:
        """Get all pending proposals"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, pattern_type, script_name, language, 
                   confidence, estimated_savings, proposed_at,
                   sandbox_tested, sandbox_passed, sandbox_warnings
            FROM proposals
            WHERE status = 'pending'
            ORDER BY proposed_at DESC
        """)
        
        results = []
        for row in cursor.fetchall():
            warnings = json.loads(row[9]) if row[9] else []
            results.append({
                'id': row[0],
                'pattern_type': row[1],
                'script_name': row[2],
                'language': row[3],
                'confidence': row[4],
                'estimated_savings': row[5],
                'proposed_at': row[6],
                'sandbox_tested': bool(row[7]),
                'sandbox_passed': bool(row[8]),
                'sandbox_warnings': warnings
            })
        
        conn.close()
        return results
    
    def get_proposal(self, proposal_id: int) -> Optional[Dict]:
        """Get full proposal details"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT pattern_type, pattern_data, generated_code, script_name,
                   language, confidence, estimated_savings, status
            FROM proposals
            WHERE id = ?
        """, (proposal_id,))
        
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return None
        
        return {
            'id': proposal_id,
            'pattern_type': row[0],
            'pattern_data': json.loads(row[1]),
            'generated_code': row[2],
            'script_name': row[3],
            'language': row[4],
            'confidence': row[5],
            'estimated_savings': row[6],
            'status': row[7]
        }
    
    def approve(self, proposal_id: int, notes: str = None) -> bool:
        """Approve a proposal"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE proposals
            SET status = 'approved',
                reviewed_at = ?,
                reviewer_notes = ?
            WHERE id = ?
        """, (datetime.now().isoformat(), notes, proposal_id))
        
        success = cursor.rowcount > 0
        conn.commit()
        conn.close()
        
        return success
    
    def reject(self, proposal_id: int, reason: str) -> bool:
        """Reject a proposal"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE proposals
            SET status = 'rejected',
                reviewed_at = ?,
                reviewer_notes = ?
            WHERE id = ?
        """, (datetime.now().isoformat(), reason, proposal_id))
        
        success = cursor.rowcount > 0
        conn.commit()
        conn.close()
        
        return success
    
    def mark_deployed(self, proposal_id: int, result: Dict) -> bool:
        """Mark proposal as deployed"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE proposals
            SET status = 'deployed',
                deployed_at = ?,
                deployment_result = ?
            WHERE id = ?
        """, (datetime.now().isoformat(), json.dumps(result), proposal_id))
        
        success = cursor.rowcount > 0
        conn.commit()
        conn.close()
        
        return success
    
    def generate_report(self) -> str:
        """Generate approval queue report"""
        pending = self.get_pending()
        
        report = "🔧 V8 OPTIMIZATION PROPOSALS\n"
        report += "=" * 60 + "\n\n"
        
        if not pending:
            report += "✅ No pending proposals\n"
            return report
        
        report += f"{len(pending)} proposal(s) awaiting review:\n\n"
        
        for i, prop in enumerate(pending, 1):
            report += f"{i}. {prop['script_name']} ({prop['language']})\n"
            report += f"   Type: {prop['pattern_type']}\n"
            report += f"   Confidence: {prop['confidence']:.0%}\n"
            report += f"   Savings: {prop['estimated_savings']}\n"
            report += f"   Proposed: {prop['proposed_at']}\n"
            report += f"   Review: /v8-approve {prop['id']} OR /v8-reject {prop['id']}\n"
            report += "\n"
        
        return report


def main():
    """Test approval workflow"""
    workflow = ApprovalWorkflow()
    
    # Test proposal
    test_pattern = {
        'type': 'command_retry',
        'command': 'curl',
        'confidence': 0.87,
        'occurrences': 20
    }
    
    test_code = {
        'code': '#!/bin/bash\n# test',
        'script_name': 'curl_retry',
        'language': 'bash',
        'estimated_savings': '100 sec/week'
    }
    
    # Submit
    proposal_id = workflow.submit_proposal(test_pattern, test_code)
    print(f"✅ Submitted proposal #{proposal_id}")
    print()
    
    # Show report
    print(workflow.generate_report())


if __name__ == '__main__':
    main()
