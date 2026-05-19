# V8 LLM-Powered Dynamic Template Generation

## Overview
V8 can now generate automation templates on-the-fly using Claude Sonnet 4.5 when no hardcoded template exists.

## How It Works

```
Pattern Detection
    ↓
Check Hardcoded Template
    ├─ ✅ Template exists → Generate code → Auto-deploy (if high confidence)
    └─ ❌ No template → LLM Generation
           ↓
       Few-shot prompt with examples
           ↓
       Claude Sonnet 4.5 generates Python/Bash script
           ↓
       Safety validation (dangerous pattern detection)
           ↓
       🚨 Manual approval required (LLM code never auto-deploys)
           ↓
       Deploy + Save template for future reuse
           ↓
       Next similar pattern → Use learned template (no LLM cost)
```

## Current Status
✅ Implemented & tested
✅ API key configured (sk-ant-api03-...)
✅ Rate limit: 10 generations/day (~$0.30/day max)
✅ Safety validation active
✅ Daemon integration complete

## Files
- `llm_code_generator.py` - LLM template generation (468 lines)
- `code_generator.py` - Integrated LLM fallback
- `deployment_manager.py` - Manual approval workflow
- `learned_templates/` - Saved templates (reused automatically)
- `llm_generation_log.json` - Rate limiting tracker

## Testing
```bash
cd ~/.openclaw/workspace/integrations/intelligence/v8_meta_learning
ANTHROPIC_API_KEY="..." python3 llm_code_generator.py
```

## Examples Generated
Calendar patterns (recurring_meeting, time_block) → Python automation scripts
Email patterns (email_template, email_shortcut) → Quick-reply scripts
Custom workflows → Bash/Python automation

## Next Patterns to Handle
Next V8 cycle (30 min) will encounter:
- 10 recurring meeting patterns → LLM generates meeting prep scripts
- 5 time block patterns → LLM generates focus-mode automations
- 16 email patterns → LLM generates template/shortcut scripts

First 10 will generate code, rest will queue as notifications (rate limit).

## Manual Approval Process
1. User receives message: "🤖 LLM generated automation for [pattern]"
2. Code preview + explanation
3. User reviews + approves
4. Template saved to learned_templates/
5. Future similar patterns → instant deployment (no LLM call)

## Cost
- $0.03 per template generation
- 10/day rate limit = $0.30/day max
- Learned templates = $0 (reused forever)

## Safety
✅ Dangerous pattern detection (rm -rf, sudo, etc.)
✅ Manual approval required (no auto-deploy)
✅ Sandbox testing
✅ Audit log
