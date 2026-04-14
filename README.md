# OpenClaw Proactive Assistant

**Always-on AI operator that learns your workflows and maintains itself.**

## What's Included

### V6 - Proactive Daemon + Autonomous Executor
- **Health Monitoring:** Auth tokens, services, tunnels, LaunchAgents
- **Autonomous Actions:** Refresh tokens, restart services, recover from failures
- **Execution Log:** Full audit trail of all autonomous actions

### V7 - Self-Healing System
- **Auto-Diagnosis:** Detects failures and identifies root causes
- **Auto-Repair:** 5 repair templates (auth, service, tunnel, disk, database)
- **Health Monitoring:** Continuous system health checks
- **Rollback:** Automatic rollback on repair failure

### V8 - Meta-Learning
- **Pattern Detection:** Shell commands, file operations, workflows
- **Email Patterns:** (Optional) Gmail pattern detection via OAuth
- **Calendar Patterns:** (Optional) Google Calendar workflow patterns via OAuth
- **Cross-Device Observer:** (Optional) Desktop activity patterns
- **Auto-Optimization:** Detects repeated tasks, proposes automations
- **Code Generation:** Auto-generates optimization scripts
- **Approval Workflow:** Review and approve before deployment
- **Model Routing:** Smart model selection (Flash for speed, Sonnet for quality)

## Architecture

```
~/.openclaw/
├── proactive/
│   ├── v6/
│   │   ├── daemon.py           # Health monitoring
│   │   ├── executor.py         # Action execution
│   │   └── execution_log.db    # Audit trail
│   ├── v7/
│   │   ├── self_healing.py     # Auto-repair daemon
│   │   ├── diagnosis.py        # Failure diagnosis
│   │   └── repairs.db          # Repair history
│   ├── v8/
│   │   ├── meta_learning.py    # Pattern learning
│   │   ├── auto_optimizer.py   # Optimization engine
│   │   ├── code_generator.py   # Script generation
│   │   └── intelligence.db     # Pattern database
│   ├── logs/                   # All daemon logs
│   └── config.yaml             # Unified config
```

## Optional: Email & Calendar Integration

To enable email and calendar pattern detection:

### 1. Get Google OAuth Credentials

1. Go to https://console.cloud.google.com/apis/credentials
2. Create a new project (or use existing)
3. Enable Gmail API and Google Calendar API
4. Create OAuth 2.0 Client ID → Desktop application
5. Download JSON and save as:
   ```
   ~/.openclaw/proactive/credentials/google_client_secrets.json
   ```

### 2. Run OAuth Setup

```bash
python3 ~/.openclaw/proactive/scripts/setup_oauth.py
```

This will:
- Open browser for Google authorization
- Store credentials securely on YOUR VM
- Enable email and calendar pattern detection

### 3. Restart V8

```bash
systemctl restart openclaw-v8
```

V8 will now scan email and calendar for patterns alongside shell commands.

**Privacy:** All data stays on your VM. No external transmission.

---

## Installation

### Automated (Cloud-Init)
```yaml
# Add to your cloud-init runcmd
- curl -sSL https://raw.githubusercontent.com/transmogrifier/openclaw-proactive-assistant/main/install.sh | bash
```

### Manual
```bash
git clone https://github.com/transmogrifier/openclaw-proactive-assistant
cd openclaw-proactive-assistant
./install.sh
```

## What It Does

### Day 1
- Monitors system health every 60 seconds
- Learns command patterns
- Logs everything for transparency

### Week 1 (with OAuth setup)
- Auto-refreshes expired tokens
- Restarts failed services automatically
- Detects your workflow patterns
- Learns email response patterns
- Identifies calendar scheduling patterns

### Month 1
- Proposes workflow optimizations
- Auto-generates automation scripts
- Self-heals from failures without intervention
- Suggests email templates and calendar optimizations

## Pricing

**Pro Tier:** $20/month
- V6 + V7 + V8 included
- Full autonomous operation
- Self-learning and self-healing

## Requirements

- OpenClaw 2026.4.0+
- Python 3.12+
- Linux or macOS
- 512MB RAM minimum

## Support

- Docs: https://docs.transmogrifier.ai/proactive
- Issues: https://github.com/transmogrifier/openclaw-proactive-assistant/issues
- Email: support@transmogrifier.ai
