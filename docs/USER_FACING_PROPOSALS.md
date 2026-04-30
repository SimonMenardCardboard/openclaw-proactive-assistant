# User-Facing Proposal Explanations

## Overview
When V8 generates automation proposals, users need clear, plain-English explanations of what each proposal does, why it's recommended, and what will change.

## Required Fields

### 1. `user_title` (string)
**Purpose:** Short, friendly name for the automation

**Examples:**
- ✅ "Auto-retry failed npm installs"
- ✅ "Quick navigation to build directory"
- ❌ "npm_retry_wrapper_v2.py"

### 2. `user_explanation` (string, 1-2 sentences)
**Purpose:** Clear description of what the automation does

**Examples:**
- ✅ "Automatically retry npm install up to 3 times with 2-second delays when it fails"
- ✅ "Create a 'gobuild' shortcut that navigates to your build directory and runs make"
- ❌ "Implements exponential backoff retry logic for package manager operations"

### 3. `why_recommended` (string, 1 sentence)
**Purpose:** Explain why V8 is suggesting this based on observed patterns

**Examples:**
- ✅ "You manually retry npm install 12× per week (saves ~3 min/week)"
- ✅ "You type 'cd ~/projects/app && make' 8× per day"
- ❌ "Pattern confidence: 82%, occurrence count: 12"

### 4. `what_changes` (string, 1 sentence)
**Purpose:** Explain what will be different after approval

**Examples:**
- ✅ "Adds retry logic to npm - no changes to your workflow"
- ✅ "Creates new 'gobuild' command you can use instead of manual navigation"
- ❌ "Installs wrapper script in ~/.openclaw/scripts/"

### 5. `risk_level` (enum: low|medium|high)
**Purpose:** Help users understand safety vs impact trade-off

**Guidelines:**
- **Low:** Read-only, no side effects, easy to undo (retries, navigation shortcuts)
- **Medium:** Writes files but isolated, recoverable (create scripts, config changes)
- **High:** Destructive or hard to undo (file deletion, system-wide changes)

## Notification Format

### Good Example:
```
💡 **2 New Automations Ready**

1. **Auto-retry failed npm installs**
   When npm install fails, automatically retry up to 3 times with 2-second delays
   
   💭 *Why:* You manually retry npm 12× per week (saves ~3 min/week)
   ⚙️ *Changes:* Adds retry logic to npm - no changes to your workflow
   🟢 *Risk:* Low
   ⏱️ *Saves:* ~3 min/week
   
   Review: `/v8-review 42`

2. **Quick navigation to build directory**
   Creates 'gobuild' shortcut that navigates to build dir and runs make
   
   💭 *Why:* You type 'cd ~/projects/app && make' 8× per day
   ⚙️ *Changes:* Creates new 'gobuild' command
   🟢 *Risk:* Low
   ⏱️ *Saves:* ~30 sec/use
   
   Review: `/v8-review 43`

View all: `/v8-proposals`
```

### Bad Example (Too Technical):
```
🔧 **V8 Generated 2 New Optimization Proposals**

1. **npm_retry_wrapper_v2** (python)
   • Confidence: 82%
   • Usage: 12 times
   • Source: v6
   • Review: `/v8-review 42`

2. **make_here** (bash)
   • Confidence: 78%
   • Usage: 8 times
   • Source: shell
   • Review: `/v8-review 43`
```

## Implementation Checklist

- [x] Add user-facing columns to proposals table
- [x] Update notification template
- [ ] Update CodeGenerator to generate explanations
- [ ] Add explanation templates for each pattern type
- [ ] Test with real user feedback
- [ ] Add examples to docs

## Pattern-Specific Templates

### Command Retry
- **Title:** "Auto-retry failed {command}"
- **Explanation:** "Automatically retry {command} up to {max_retries} times with {delay}-second delays when it fails"
- **Why:** "You manually retry {command} {count}× per week (saves ~{time}/week)"
- **Changes:** "Adds retry logic to {command} - no changes to your workflow"
- **Risk:** Low

### Directory Navigation
- **Title:** "Quick navigation to {location}"
- **Explanation:** "Creates '{shortcut}' command that navigates to {path} and runs {command}"
- **Why:** "You type 'cd {path} && {command}' {count}× per day"
- **Changes:** "Creates new '{shortcut}' command"
- **Risk:** Low

### Workflow Sequence
- **Title:** "Automate {workflow_name}"
- **Explanation:** "Combines {step1}, {step2}, and {step3} into a single '{command}' command"
- **Why:** "You run this sequence {count}× per week (saves ~{time}/week)"
- **Changes:** "Creates new '{command}' workflow shortcut"
- **Risk:** Medium (if includes writes)

## User Testing Notes
- Keep explanations under 2 sentences
- Use active voice ("Creates" not "Will create")
- Show time savings in familiar units (min/week, sec/use)
- Always explain what changes (even if "nothing")
- Risk level is critical - users skip proposals they don't understand
