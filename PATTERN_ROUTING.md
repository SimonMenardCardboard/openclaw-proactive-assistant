# Pattern Routing - Shell Optimizations to Hobbes Control

## Overview

**Problem:** End users of Transmogrifier shouldn't approve shell scripts. That's a technical/security decision.

**Solution:** Route shell command optimizations to Hobbes Control for automated validation & deployment. User gets notified AFTER deployment, not before.

## Architecture

```
┌─────────────────┐
│ VM: User's      │
│ Transmogrifier  │
└────────┬────────┘
         │
         │ Detects patterns
         │
         ▼
┌─────────────────────────────────────┐
│ Pattern Router                      │
│ proactive_system/pattern_router.py  │
└───────┬─────────────────────────────┘
        │
        ├─► Shell patterns (command_retry, git_workflow, etc.)
        │   │
        │   ▼
        │   ┌──────────────────────┐
        │   │ Hobbes Control       │
        │   │ (Control Plane)      │
        │   ├──────────────────────┤
        │   │ 1. Security check    │
        │   │ 2. Sandbox test      │
        │   │ 3. Auto-approve      │
        │   │ 4. Deploy to VM      │
        │   │ 5. Notify user       │
        │   └──────────────────────┘
        │
        └─► Other patterns (email, calendar, productivity)
            │
            ▼
            ┌──────────────────────┐
            │ User Approval        │
            │ (Mobile/Desktop App) │
            └──────────────────────┘
```

## Pattern Types

### Shell Patterns (→ Hobbes Control)

Automatically routed to control plane for validation & deployment:

- `command_retry` - Auto-retry failed commands
- `dir_navigation` - Smart cd shortcuts
- `multi_command` - Workflow automation
- `cache_operation` - Cache management
- `git_workflow` - Git shortcuts
- `npm_workflow` - NPM shortcuts
- `docker_workflow` - Docker shortcuts
- `system_admin` - System admin tasks
- `development_workflow` - Dev workflows
- `file_management` - File operations
- `shell_automation` - General shell automation

### Non-Shell Patterns (→ User)

Require user approval via mobile/desktop app:

- `meeting_prep` - Meeting preparation
- `email_template` - Email templates
- `email_shortcut` - Email shortcuts
- `focus_block` - Calendar focus time
- `meeting_workflow` - Meeting workflows
- All other non-shell patterns

## Environment Detection

### Hobbes Prime (Dev/Test)

```bash
export HOBBES_PRIME=true
```

**Behavior:** ALL patterns → user (Simon via Telegram)

### Transmogrifier VM (Production)

```bash
export TRANSMOGRIFIER_VM=true
```

**Behavior:** Shell patterns → Hobbes Control, others → user

## Usage in Code

### Automatic Routing

```python
from pattern_router import route_pattern

# Detect pattern
pattern = {
    'type': 'command_retry',
    'command': 'git',
    'count': 15,
    'confidence': 0.85
}

# Generate code
generated_code = code_generator.generate(pattern)

# Route automatically
result = route_pattern(pattern, generated_code, user_id='user123')

if result['routed_to'] == 'user':
    print(f"User approval required: Queue ID {result['queue_id']}")
else:
    print(f"Sent to control plane: {result['control_id']}")
```

### Manual Routing

```python
from pattern_router import PatternRouter

router = PatternRouter(user_id='user123')

# Check routing destination
pattern_type = 'command_retry'
will_route_to_control = pattern_type in router.SHELL_PATTERN_TYPES
```

## Hobbes Control Workflow

### 1. Security Validation

**Checks:**
- ❌ No `sudo` or elevated permissions
- ❌ No network access (`curl`, `wget`, `ssh`, etc.)
- ❌ No file access outside workspace
- ❌ No PII access (email, calendar data)
- ❌ No destructive operations (`rm -rf`, etc.)

**Result:** Pass/Fail + violations list

### 2. Sandbox Testing

**Tests:**
- ✅ Executes without errors
- ✅ Doesn't hang or crash
- ✅ `--help` works (basic functionality)

**Environment:** Isolated temp directory, 10s timeout

**Result:** Pass/Fail + exit code/stderr

### 3. Auto-Approval

**Criteria:**
- ✅ Security check passed
- ✅ Sandbox test passed
- ✅ Confidence > 70%

**Result:** Approved for deployment

### 4. Deployment

**Steps:**
1. SSH to user VM
2. Copy script to `~/.openclaw/workspace/scripts/`
3. Set permissions (`chmod +x`)
4. Add alias (if applicable)
5. Verify deployment

**Result:** Success/Failure + script path

### 5. User Notification

**Timing:** AFTER deployment (not before)

**Message:**
```
✨ New Automation Deployed

Auto-retry Git Commands

Automatically retries failed git commands

What's new:
• Automation is live in your workspace
• No action needed - it's already working
• Runs automatically when triggered

Managing:
• Disable: hobbes disable git_retry
• View logs: hobbes logs git_retry
• Remove: hobbes remove git_retry
```

## Control Plane API

### Submit Optimization

```bash
POST /api/shell/submit
Content-Type: application/json
Authorization: Bearer <token>

{
  "pattern": {...},
  "generated_code": {...},
  "user_id": "user123"
}

Response:
{
  "control_id": "shell_abc123...",
  "status": "pending"
}
```

### Check Status

```bash
GET /api/shell/status/<control_id>

Response:
{
  "control_id": "shell_abc123...",
  "status": "deployed",
  "security_check": {...},
  "sandbox_test": {...},
  "deployment_result": {...}
}
```

### List Optimizations

```bash
GET /api/shell/list?user_id=user123&status=deployed

Response:
{
  "optimizations": [
    {
      "control_id": "shell_abc123...",
      "user_id": "user123",
      "status": "deployed",
      "submitted_at": "2026-05-20T17:30:00Z"
    }
  ]
}
```

## Database Schema

### shell_optimizations

```sql
CREATE TABLE shell_optimizations (
    control_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    pattern TEXT NOT NULL,
    generated_code TEXT NOT NULL,
    submitted_at TEXT NOT NULL,
    status TEXT NOT NULL,
    security_check TEXT,
    sandbox_test TEXT,
    deployment_result TEXT,
    updated_at TEXT NOT NULL
);

CREATE INDEX idx_user_status
ON shell_optimizations(user_id, status);
```

**Statuses:**
- `pending` - Submitted, not yet processed
- `validating` - Running security checks
- `testing` - Running sandbox tests
- `approved` - Passed validation, ready to deploy
- `deploying` - Deploying to user VM
- `deployed` - Successfully deployed
- `rejected` - Failed validation
- `failed` - Deployment failed

## Testing

### Test on Hobbes Prime (All → User)

```bash
cd ~/.openclaw/workspace/transmogrifier/openclaw-proactive-assistant

# Set Prime mode
export HOBBES_PRIME=true

# Test routing
python3 -c "
from proactive_system.pattern_router import route_pattern

pattern = {'type': 'command_retry', 'command': 'git'}
result = route_pattern(pattern)
print(f\"Routed to: {result['routed_to']}\")
"
# Expected: Routed to: user
```

### Test on VM (Shell → Control)

```bash
# Set VM mode
export TRANSMOGRIFIER_VM=true

# Test routing
python3 -c "
from proactive_system.pattern_router import route_pattern

pattern = {'type': 'command_retry', 'command': 'git'}
result = route_pattern(pattern)
print(f\"Routed to: {result['routed_to']}\")
"
# Expected: Routed to: control_plane
```

## Deployment

### 1. Update VM Provisioning

Add to VM initialization:

```bash
export TRANSMOGRIFIER_VM=true
```

### 2. Deploy Control Plane Endpoints

```bash
cd transmogrifier/control-plane

# Add to app.py:
from shell_optimization_endpoints import shell_bp
app.register_blueprint(shell_bp)

# Restart control plane
systemctl restart transmogrifier-control
```

### 3. Update VM Code

```bash
# Pull latest openclaw-proactive-assistant
cd ~/.openclaw/workspace/transmogrifier/openclaw-proactive-assistant
git pull origin main

# Restart V8 daemon
systemctl restart v8-continuous-daemon
```

## Monitoring

### Control Plane Logs

```bash
tail -f /var/log/transmogrifier/shell_optimizations.log
```

### VM Logs

```bash
tail -f ~/.openclaw/workspace/logs/pattern_router.log
```

### Database Queries

```bash
# Count by status
sqlite3 control-plane/shell_optimizations.db "
  SELECT status, COUNT(*) 
  FROM shell_optimizations 
  GROUP BY status
"

# Recent deployments
sqlite3 control-plane/shell_optimizations.db "
  SELECT control_id, user_id, status, submitted_at
  FROM shell_optimizations
  ORDER BY submitted_at DESC
  LIMIT 10
"
```

## Security Considerations

### What Gets Blocked

- ❌ sudo/elevated permissions
- ❌ Network access
- ❌ File access outside workspace
- ❌ PII access (email, calendar)
- ❌ Destructive operations

### What's Allowed

- ✅ Workspace file operations
- ✅ Git commands
- ✅ NPM/package managers
- ✅ Development tools
- ✅ Command retries
- ✅ Workflow automation

### User Control

Users can ALWAYS:
- View deployed scripts
- Disable any automation
- Remove any automation
- View execution logs

## FAQ

**Q: What if Hobbes Control is down?**
A: Pattern router falls back to user approval flow.

**Q: Can users see the code before deployment?**
A: No. They're notified AFTER deployment with option to view logs/code.

**Q: What if deployment fails?**
A: Status set to 'failed', user NOT notified, retry available.

**Q: Can users override auto-approvals?**
A: Yes, via app settings: "Review all automations before deployment"

**Q: What about custom scripts?**
A: Only detected patterns are auto-approved. Custom scripts → user approval.

## Rollout Plan

1. **Week 1:** Deploy to Hobbes Prime (test with Simon)
2. **Week 2:** Deploy to beta VMs (10 users)
3. **Week 3:** Monitor security/approval rates
4. **Week 4:** Production rollout (all users)
5. **Week 5+:** Iterate based on feedback

## Metrics

Track:
- Approval rate (target: >80%)
- Security rejection rate (target: <5%)
- Sandbox failure rate (target: <10%)
- User disable rate (target: <15%)
- Time to deployment (target: <60s)

---

**Status:** Ready for testing (Hobbes Prime + beta VMs)
**Owner:** Hobbes Prime + Hobbes Control
**Last Updated:** 2026-05-20
