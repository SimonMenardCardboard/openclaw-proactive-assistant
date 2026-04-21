#!/usr/bin/env python3
"""
V8 Review Commands

CLI commands for reviewing and managing V8 optimization proposals.

Commands:
  v8-proposals          List all pending proposals
  v8-review <id>        Show proposal details
  v8-approve <id>       Approve and deploy
  v8-reject <id>        Reject proposal
  v8-status             Show V8 statistics
"""

import sys
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from approval_workflow import ApprovalWorkflow
from code_generator import CodeGenerator
from sandbox_tester import SandboxTester


class V8Commands:
    """Command-line interface for V8 proposal management"""
    
    def __init__(self):
        self.workflow = ApprovalWorkflow()
        self.generator = CodeGenerator()
        self.sandbox = SandboxTester()
    
    def list_proposals(self):
        """Show all pending proposals"""
        pending = self.workflow.get_pending()
        
        if not pending:
            print("✅ No pending proposals")
            return
        
        print(f"\n🔧 V8 OPTIMIZATION PROPOSALS ({len(pending)} pending)\n")
        print("=" * 70)
        
        for prop in pending:
            print(f"\nProposal #{prop['id']}: {prop['script_name']}")
            print(f"  Type: {prop['pattern_type']}")
            print(f"  Language: {prop['language']}")
            print(f"  Confidence: {prop['confidence']:.0%}")
            print(f"  Estimated Savings: {prop['estimated_savings']}")
            print(f"  Proposed: {prop['proposed_at']}")
            print(f"  Actions: v8-review {prop['id']} | v8-approve {prop['id']} | v8-reject {prop['id']}")
        
        print("\n" + "=" * 70)
    
    def review_proposal(self, proposal_id: int):
        """Show detailed proposal info"""
        proposal = self.workflow.get_proposal(proposal_id)
        
        if not proposal:
            print(f"❌ Proposal #{proposal_id} not found")
            return
        
        print(f"\n{'=' * 70}")
        print(f"PROPOSAL #{proposal_id}: {proposal['script_name']}")
        print(f"{'=' * 70}\n")
        
        print(f"Type: {proposal['pattern_type']}")
        print(f"Language: {proposal['language']}")
        print(f"Confidence: {proposal['confidence']:.0%}")
        print(f"Estimated Savings: {proposal['estimated_savings']}")
        print(f"Status: {proposal['status']}")
        
        print(f"\n{'-' * 70}")
        print("GENERATED CODE:")
        print(f"{'-' * 70}\n")
        print(proposal['generated_code'])
        
        print(f"\n{'-' * 70}")
        print("PATTERN DATA:")
        print(f"{'-' * 70}\n")
        import json
        print(json.dumps(proposal['pattern_data'], indent=2))
        
        print(f"\n{'-' * 70}")
        print("ACTIONS:")
        print(f"{'-' * 70}")
        print(f"Approve: v8-approve {proposal_id}")
        print(f"Reject:  v8-reject {proposal_id}")
        print()
    
    def approve_proposal(self, proposal_id: int, notes: str = None, skip_test: bool = False):
        """Approve and deploy a proposal"""
        proposal = self.workflow.get_proposal(proposal_id)
        
        if not proposal:
            print(f"❌ Proposal #{proposal_id} not found")
            return
        
        # Sandbox test first (unless skipped)
        if not skip_test:
            print(f"🧪 Testing proposal #{proposal_id} in sandbox...")
            test_results = self.sandbox.test_script(
                proposal['generated_code'],
                proposal['script_name'],
                proposal['language']
            )
            
            print(f"   Syntax: {'✅' if test_results['syntax_valid'] else '❌'}")
            print(f"   Safe: {'✅' if test_results['safe'] else '❌'}")
            print(f"   Executable: {'✅' if test_results['executable'] else '❌'}")
            
            if test_results['warnings']:
                print(f"   Warnings: {len(test_results['warnings'])}")
                for w in test_results['warnings']:
                    print(f"      - {w}")
            
            if not test_results['passed']:
                print(f"\n❌ Sandbox test FAILED")
                for err in test_results['errors']:
                    print(f"   Error: {err}")
                print(f"\n   Use --skip-test to deploy anyway (not recommended)")
                return
            
            print("   ✅ Sandbox test passed\n")
        
        print(f"✅ Approving proposal #{proposal_id}: {proposal['script_name']}")
        
        # Mark as approved
        self.workflow.approve(proposal_id, notes)
        
        # Deploy
        print("🚀 Deploying...")
        deployment_result = self._deploy_proposal(proposal)
        
        # Mark as deployed
        self.workflow.mark_deployed(proposal_id, deployment_result)
        
        if deployment_result['success']:
            print(f"✅ Deployed successfully!")
            print(f"   Script: {deployment_result['script_path']}")
            print(f"\n{deployment_result.get('instructions', '')}")
        else:
            print(f"❌ Deployment failed: {deployment_result.get('error')}")
    
    def reject_proposal(self, proposal_id: int, reason: str):
        """Reject a proposal"""
        proposal = self.workflow.get_proposal(proposal_id)
        
        if not proposal:
            print(f"❌ Proposal #{proposal_id} not found")
            return
        
        self.workflow.reject(proposal_id, reason)
        print(f"❌ Rejected proposal #{proposal_id}: {proposal['script_name']}")
        print(f"   Reason: {reason}")
    
    def _deploy_proposal(self, proposal: dict) -> dict:
        """Deploy an approved proposal"""
        try:
            script_name = proposal['script_name']
            code = proposal['generated_code']
            language = proposal['language']
            
            # Determine output path
            if language == 'bash':
                script_path = Path.home() / '.openclaw/workspace/scripts' / script_name
            else:
                script_path = Path.home() / '.openclaw/workspace/scripts' / f"{script_name}.py"
            
            # Write script
            script_path.write_text(code)
            
            # Make executable (for bash)
            if language == 'bash':
                import os
                os.chmod(script_path, 0o755)
            
            # Generate installation instructions
            instructions = self._get_install_instructions(proposal, script_path)
            
            return {
                'success': True,
                'script_path': str(script_path),
                'instructions': instructions
            }
        
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def _get_install_instructions(self, proposal: dict, script_path: Path) -> str:
        """Generate installation instructions"""
        pattern_type = proposal['pattern_type']
        script_name = proposal['script_name']
        
        if pattern_type == 'command_retry':
            command = proposal['pattern_data'].get('command', 'cmd')
            return f"""
INSTALLATION INSTRUCTIONS:
1. Script deployed to: {script_path}
2. Add alias to ~/.openclaw/workspace/scripts/smart_aliases.zsh:
   
   alias {command}='{script_path}'

3. Reload: source ~/.openclaw/workspace/scripts/smart_aliases.zsh
4. Test: {command} --help
"""
        
        elif pattern_type == 'dir_navigation':
            return f"""
INSTALLATION INSTRUCTIONS:
1. Script deployed to: {script_path}
2. Add alias to ~/.openclaw/workspace/scripts/smart_aliases.zsh:
   
   alias {script_name}='{script_path}'

3. Reload: source ~/.openclaw/workspace/scripts/smart_aliases.zsh
4. Test: {script_name} <dir> <args>
"""
        
        else:
            return f"""
INSTALLATION INSTRUCTIONS:
1. Script deployed to: {script_path}
2. Manual integration may be required
3. Review script and adjust as needed
"""
    
    def show_status(self):
        """Show V8 statistics"""
        import sqlite3
        
        db_path = Path.home() / '.openclaw/workspace/integrations/intelligence/v8_meta_learning/approvals.db'
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Get counts by status
        cursor.execute("SELECT status, COUNT(*) FROM proposals GROUP BY status")
        status_counts = dict(cursor.fetchall())
        
        # Get total proposals
        cursor.execute("SELECT COUNT(*) FROM proposals")
        total = cursor.fetchone()[0]
        
        conn.close()
        
        print("\n📊 V8 AUTO-OPTIMIZER STATUS")
        print("=" * 50)
        print(f"Total proposals: {total}")
        print(f"  Pending: {status_counts.get('pending', 0)}")
        print(f"  Approved: {status_counts.get('approved', 0)}")
        print(f"  Rejected: {status_counts.get('rejected', 0)}")
        print(f"  Deployed: {status_counts.get('deployed', 0)}")
        print("=" * 50)
        print()


def main():
    parser = argparse.ArgumentParser(description='V8 Optimization Proposal Management')
    subparsers = parser.add_subparsers(dest='command', help='Command')
    
    # List proposals
    subparsers.add_parser('proposals', help='List pending proposals')
    
    # Review proposal
    review_parser = subparsers.add_parser('review', help='Review proposal details')
    review_parser.add_argument('id', type=int, help='Proposal ID')
    
    # Approve proposal
    approve_parser = subparsers.add_parser('approve', help='Approve and deploy proposal')
    approve_parser.add_argument('id', type=int, help='Proposal ID')
    approve_parser.add_argument('--notes', help='Approval notes')
    approve_parser.add_argument('--skip-test', action='store_true', help='Skip sandbox testing')
    
    # Reject proposal
    reject_parser = subparsers.add_parser('reject', help='Reject proposal')
    reject_parser.add_argument('id', type=int, help='Proposal ID')
    reject_parser.add_argument('reason', help='Rejection reason')
    
    # Status
    subparsers.add_parser('status', help='Show V8 statistics')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    commands = V8Commands()
    
    if args.command == 'proposals':
        commands.list_proposals()
    elif args.command == 'review':
        commands.review_proposal(args.id)
    elif args.command == 'approve':
        commands.approve_proposal(args.id, args.notes, args.skip_test if hasattr(args, 'skip_test') else False)
    elif args.command == 'reject':
        commands.reject_proposal(args.id, args.reason)
    elif args.command == 'status':
        commands.show_status()


if __name__ == '__main__':
    main()
