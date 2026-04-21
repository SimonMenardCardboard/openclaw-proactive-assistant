#!/usr/bin/env python3
"""
V8 Deployment Manager - Phase 3

Orchestrates the complete deployment pipeline:
1. Sandbox test
2. Human approval (if needed)
3. Deploy with rollback protection
4. Monitor health
5. Auto-rollback if issues

This is the integration layer that ties together all Phase 3 components.

Usage:
    manager = DeploymentManager()
    
    # Full pipeline
    result = manager.deploy_optimization(
        pattern=pattern_dict,
        generated_code=code_dict
    )
"""

import sys
from pathlib import Path
from typing import Dict, Optional

# Import all Phase 3 components
sys.path.insert(0, str(Path(__file__).parent))
from sandbox_executor import SandboxExecutor
from approval_workflow import ApprovalWorkflow
from auto_rollback import AutoRollback
from health_monitor import HealthMonitor


class DeploymentManager:
    """
    Orchestrate complete V8 deployment pipeline.
    
    Pipeline:
    1. Generate code (from auto_optimizer)
    2. Sandbox test (syntax, safety, execution, output, side-effects)
    3. Submit for approval (auto-approved if sandbox passed + high confidence)
    4. Deploy with rollback protection
    5. Monitor health
    6. Auto-rollback if issues detected
    """
    
    def __init__(self,
                 scripts_dir: Path = None,
                 auto_approve_threshold: float = 0.90,
                 enable_auto_deploy: bool = False):
        """
        Initialize deployment manager.
        
        Args:
            scripts_dir: Where to deploy scripts
            auto_approve_threshold: Min confidence for auto-approval
            enable_auto_deploy: Whether to auto-deploy approved optimizations
        """
        if scripts_dir is None:
            scripts_dir = Path.home() / '.openclaw/workspace/scripts'
        
        self.scripts_dir = scripts_dir
        self.scripts_dir.mkdir(parents=True, exist_ok=True)
        
        self.auto_approve_threshold = auto_approve_threshold
        self.enable_auto_deploy = enable_auto_deploy
        
        # Initialize components
        self.sandbox = SandboxExecutor(validate_output=True)
        self.approval_workflow = ApprovalWorkflow(enable_sandbox=True)
        self.auto_rollback = AutoRollback()
        self.health_monitor = HealthMonitor()
    
    def deploy_optimization(self,
                           pattern: Dict,
                           generated_code: Dict,
                           auto_deploy: Optional[bool] = None) -> Dict:
        """
        Complete deployment pipeline for an optimization.
        
        Args:
            pattern: Pattern that triggered optimization
            generated_code: Generated script code
            auto_deploy: Override auto-deploy setting
        
        Returns:
            {
                'status': str ('pending'|'deployed'|'failed'|'rolled_back'),
                'proposal_id': int,
                'deployment_id': int (if deployed),
                'sandbox_result': Dict,
                'approval_status': str,
                'deployment_result': Dict (if deployed)
            }
        """
        use_auto_deploy = auto_deploy if auto_deploy is not None else self.enable_auto_deploy
        
        # Step 1: Sandbox test (happens automatically in approval workflow)
        print(f"📝 Submitting optimization: {generated_code.get('script_name')}")
        
        proposal_id = self.approval_workflow.submit_proposal(pattern, generated_code)
        
        # Get sandbox results
        proposal = self.approval_workflow.get_proposal(proposal_id)
        
        sandbox_passed = proposal.get('sandbox_passed', False)
        confidence = pattern.get('confidence', 0.0)
        
        # Step 2: Check if auto-approved
        auto_approved = (sandbox_passed and 
                        confidence >= self.auto_approve_threshold)
        
        if auto_approved:
            print(f"✅ Auto-approved (confidence: {confidence:.0%}, sandbox: passed)")
            self.approval_workflow.approve(proposal_id, "Auto-approved by deployment manager")
            approval_status = 'approved'
        else:
            print(f"⏸️  Pending review (confidence: {confidence:.0%}, sandbox: {'passed' if sandbox_passed else 'failed'})")
            approval_status = 'pending'
        
        # Step 3: Deploy if approved and auto-deploy enabled
        deployment_result = None
        deployment_id = None
        
        if approval_status == 'approved' and use_auto_deploy:
            deployment_result = self._deploy_approved(proposal_id, generated_code)
            deployment_id = deployment_result.get('deployment_id')
        
        return {
            'status': deployment_result.get('status', 'pending') if deployment_result else approval_status,
            'proposal_id': proposal_id,
            'deployment_id': deployment_id,
            'sandbox_result': {
                'passed': sandbox_passed,
                'tested': proposal.get('sandbox_tested', False)
            },
            'approval_status': approval_status,
            'deployment_result': deployment_result
        }
    
    def _deploy_approved(self, proposal_id: int, generated_code: Dict) -> Dict:
        """Deploy an approved optimization"""
        script_name = generated_code.get('script_name', 'unknown')
        script_code = generated_code.get('code', '')
        
        # Deployment path
        deployment_path = self.scripts_dir / script_name
        
        print(f"🚀 Deploying: {script_name}")
        
        # Deploy with rollback protection
        result = self.auto_rollback.deploy_with_protection(
            proposal_id=proposal_id,
            script_name=script_name,
            script_content=script_code,
            deployment_path=deployment_path
        )
        
        if result['success']:
            print(f"✅ Deployed successfully: {deployment_path}")
            print(f"   Monitoring: {result['monitoring']}")
            
            # Record deployment in approval workflow
            self.approval_workflow.mark_deployed(
                proposal_id=proposal_id,
                result={'success': True, 'path': str(deployment_path)}
            )
            
            return {
                'status': 'deployed',
                'deployment_id': result['deployment_id'],
                'script_path': str(deployment_path),
                'backup_path': result.get('backup_path'),
                'monitoring': result['monitoring']
            }
        else:
            print(f"❌ Deployment failed: {result.get('error')}")
            
            return {
                'status': 'failed',
                'deployment_id': result.get('deployment_id'),
                'error': result.get('error')
            }
    
    def get_deployment_health(self, deployment_id: int) -> Dict:
        """Get health status of a deployment"""
        return self.health_monitor.check_health(deployment_id)
    
    def manual_rollback(self, deployment_id: int, reason: str) -> bool:
        """Manually trigger rollback"""
        return self.health_monitor.trigger_rollback(deployment_id, reason)


def main():
    """Test deployment manager"""
    manager = DeploymentManager(
        auto_approve_threshold=0.85,
        enable_auto_deploy=True
    )
    
    print("V8 Deployment Manager - Test Suite")
    print("=" * 70)
    
    # Test optimization
    pattern = {
        'type': 'command_retry',
        'confidence': 0.95,
        'count': 10,
        'description': 'Test command retry'
    }
    
    code = {
        'code': '''#!/usr/bin/env python3
# Test script
import sys
print("Attempting command...")
print("✅ Command succeeded")
sys.exit(0)
''',
        'script_name': 'test_deploy_script',
        'language': 'python',
        'estimated_savings': '5 min/week'
    }
    
    # Test 1: Full deployment pipeline
    print("\n1. Testing full deployment pipeline...")
    result = manager.deploy_optimization(pattern, code)
    
    print(f"\n--- Results ---")
    print(f"Status: {result['status']}")
    print(f"Proposal ID: {result['proposal_id']}")
    print(f"Deployment ID: {result['deployment_id']}")
    print(f"Approval: {result['approval_status']}")
    print(f"Sandbox passed: {result['sandbox_result']['passed']}")
    
    if result.get('deployment_result'):
        print(f"Deployed to: {result['deployment_result'].get('script_path')}")
        print(f"Monitoring: {result['deployment_result'].get('monitoring')}")
    
    # Test 2: Check deployment health
    if result['deployment_id']:
        print("\n2. Testing health check...")
        health = manager.get_deployment_health(result['deployment_id'])
        print(f"Healthy: {health['healthy']}")
        print(f"Status: {health['status']}")
    
    print("\n" + "=" * 70)
    print("✓ Deployment manager tests complete!")


if __name__ == '__main__':
    main()
