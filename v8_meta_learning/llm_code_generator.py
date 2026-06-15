#!/usr/bin/env python3
"""
LLM-Powered Dynamic Code Generation

Uses OpenClaw's configured model to generate automation templates on-demand
when no hardcoded template exists.

Flow:
1. Pattern detected without template
2. Build few-shot prompt with examples
3. Call OpenClaw LLM
4. Parse and validate generated code
5. Save successful templates for reuse
"""

import json
import subprocess
import re
from pathlib import Path
from typing import Dict, Optional
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('v8.llm_generator')


class LLMCodeGenerator:
    """Generate automation code using LLM when templates don't exist"""
    
    def __init__(self):
        self.base_dir = Path(__file__).parent
        self.examples_dir = self.base_dir / 'template_examples'
        self.learned_dir = self.base_dir / 'learned_templates'
        
        # Create directories
        self.examples_dir.mkdir(exist_ok=True)
        self.learned_dir.mkdir(exist_ok=True)
        
        # Rate limiting
        self.max_generations_per_day = 10
        self.generation_log = self.base_dir / 'llm_generation_log.json'
    
    def generate_from_pattern(self, pattern: Dict) -> Optional[Dict]:
        """
        Generate code template using LLM for unknown pattern types.
        
        Args:
            pattern: {
                'type': 'recurring_meeting',
                'title': 'Weekly standup',
                'count': 52,
                'confidence': 0.95,
                'description': 'Happens every Monday at 10am'
            }
        
        Returns:
            {
                'code': '#!/usr/bin/env python3...',
                'language': 'python',
                'script_name': 'weekly_standup_prep',
                'user_explanation': 'Auto-generates meeting notes...',
                'why_recommended': '...',
                'risk_level': 'medium',
                'generated_by': 'llm'
            }
        """
        pattern_type = pattern.get('type')
        
        # Check if we already learned this pattern type
        learned_template = self._load_learned_template(pattern_type)
        if learned_template:
            logger.info(f"Using learned template for {pattern_type}")
            return self._adapt_learned_template(learned_template, pattern)
        
        # Check rate limit
        if not self._check_rate_limit():
            logger.warning("LLM generation rate limit reached (3/day)")
            return None
        
        logger.info(f"🤖 Generating code for {pattern_type} using LLM...")
        
        # Build prompt
        prompt = self._build_generation_prompt(pattern)
        
        # Call LLM
        response = self._call_openclaw_llm(prompt)
        if not response:
            logger.error("LLM call failed")
            return None
        
        # Parse response
        code_result = self._parse_llm_response(response)
        if not code_result:
            logger.error("Failed to parse LLM response")
            return None
        
        # Add metadata
        code_result['pattern_type'] = pattern_type
        code_result['generated_by'] = 'llm'
        code_result['generated_at'] = datetime.now().isoformat()
        code_result['confidence'] = pattern.get('confidence', 0.0)
        code_result['pattern'] = pattern
        
        # Log generation
        self._log_generation(pattern_type)
        
        logger.info(f"✅ Generated {code_result.get('language', 'unknown')} script: {code_result.get('script_name')}")
        
        return code_result
    
    def _build_generation_prompt(self, pattern: Dict) -> str:
        """Build few-shot prompt with example templates"""
        
        pattern_type = pattern.get('type')
        description = pattern.get('description', 'No description')
        count = pattern.get('count', 0)
        confidence = pattern.get('confidence', 0.0)
        
        # Load similar examples
        examples = self._load_example_templates(pattern_type)
        
        # Pattern-specific context
        context = self._build_pattern_context(pattern)
        
        prompt = f"""You are a code generation assistant for a personal automation system (V8 meta-learning).

## Task
Generate a script to automate this detected user pattern:

**Pattern Type:** {pattern_type}
**Description:** {description}
**Frequency:** {count} occurrences
**Confidence:** {confidence:.0%}

{context}

## Example Templates
Here are similar automation scripts for reference:
{examples}

## Requirements
1. **Language:** Python 3 (prefer) or Bash for simple tasks
2. **Error handling:** Robust try/catch blocks
3. **Logging:** Log actions to ~/.openclaw/workspace/logs/automation.log
4. **Idempotent:** Safe to run multiple times
5. **User-friendly:** Clear output messages
6. **No external deps:** Use standard library when possible
7. **Permissions:** Never use sudo or destructive commands
8. **Files:** Write to ~/.openclaw/workspace/ subdirectories only

## Output Format
Return ONLY a valid JSON object (no markdown, no explanation):

{{
  "code": "#!/usr/bin/env python3\\n# Full script here...",
  "language": "python",
  "script_name": "descriptive_snake_case_name",
  "user_explanation": "What this automation does (1-2 sentences)",
  "why_recommended": "Why V8 recommends this based on the pattern",
  "what_changes": "What will be different after deployment",
  "risk_level": "low"
}}

**Important:** 
- Return ONLY the JSON object
- Script must be complete and executable
- Use absolute paths (home directory via Path.home())
- Include logging and error handling
"""
        
        return prompt
    
    def _build_pattern_context(self, pattern: Dict) -> str:
        """Build pattern-specific context for the prompt"""
        pattern_type = pattern.get('type')
        
        if pattern_type == 'recurring_meeting':
            return f"""
**Pattern Details:**
- Meeting: {pattern.get('title', 'Unknown')}
- Frequency: {pattern.get('count', 0)} times
- Accounts: {', '.join(pattern.get('accounts', ['primary']))}

**Suggested Automation:**
- Check calendar for this meeting
- Send prep reminder 30min before
- Create agenda doc if needed
- Log meeting outcomes after
"""
        
        elif pattern_type == 'time_block':
            return f"""
**Pattern Details:**
- Day: {pattern.get('weekday', 'Unknown')}
- Time: {pattern.get('hour', 0)}:00
- Frequency: {pattern.get('count', 0)} occurrences

**Suggested Automation:**
- Block calendar time
- Send focus-mode reminder
- Disable notifications during block
- Track time block usage
"""
        
        elif pattern_type == 'email_template':
            return f"""
**Pattern Details:**
- Subject pattern: {pattern.get('subject_pattern', 'Unknown')}
- Frequency: {pattern.get('count', 0)} emails
- Accounts: {', '.join(pattern.get('accounts', ['primary']))}

**Suggested Automation:**
- Create quick-reply template
- Pre-fill common content
- Save to ~/.openclaw/workspace/email_templates/
- Integrate with email client
"""
        
        elif pattern_type == 'email_shortcut':
            return f"""
**Pattern Details:**
- Recipient: {pattern.get('recipient', 'Unknown')}
- Frequency: {pattern.get('count', 0)} emails

**Suggested Automation:**
- Quick-compose shortcut
- Auto-suggest this recipient
- Pre-fill common greeting/signature
"""
        
        else:
            return f"""
**Pattern Details:**
{json.dumps(pattern, indent=2)}
"""
    
    def _load_example_templates(self, pattern_type: str) -> str:
        """Load similar template examples for few-shot learning"""
        
        # Map pattern types to similar existing templates
        example_map = {
            'recurring_meeting': ['command_retry', 'multi_command'],
            'time_block': ['command_retry', 'deduplication'],
            'meeting_category': ['multi_command', 'cache_operation'],
            'email_template': ['command_retry', 'deduplication'],
            'email_shortcut': ['dir_navigation', 'command_retry'],
            'email_schedule': ['cache_operation', 'deduplication'],
        }
        
        similar_types = example_map.get(pattern_type, ['command_retry', 'multi_command'])
        
        examples = []
        for similar_type in similar_types[:2]:
            example = self._get_builtin_example(similar_type)
            if example:
                examples.append(f"### Example: {similar_type}\n{example}")
        
        return "\n\n".join(examples) if examples else "No examples available"
    
    def _get_builtin_example(self, template_type: str) -> Optional[str]:
        """Get example from existing hardcoded templates"""
        
        # Simplified examples of existing templates
        examples = {
            'command_retry': '''```python
#!/usr/bin/env python3
import subprocess
import time

def retry_command(cmd, max_retries=3, delay=2):
    for attempt in range(max_retries):
        result = subprocess.run(cmd, shell=True, capture_output=True)
        if result.returncode == 0:
            return result
        if attempt < max_retries - 1:
            time.sleep(delay)
    return result

if __name__ == "__main__":
    result = retry_command("curl https://api.example.com")
    print(result.stdout.decode())
```''',
            
            'multi_command': '''```python
#!/usr/bin/env python3
import subprocess

def run_workflow():
    commands = [
        "git fetch origin",
        "git checkout main",
        "git pull origin main"
    ]
    for cmd in commands:
        result = subprocess.run(cmd, shell=True, capture_output=True)
        if result.returncode != 0:
            print(f"Failed: {cmd}")
            return False
    return True

if __name__ == "__main__":
    run_workflow()
```''',
            
            'deduplication': '''```python
#!/usr/bin/env python3
from pathlib import Path
import json
import hashlib

def track_operation(operation_id):
    tracker_file = Path.home() / '.openclaw/workspace/dedup_tracker.json'
    tracker_file.parent.mkdir(exist_ok=True)
    
    if tracker_file.exists():
        with open(tracker_file) as f:
            seen = json.load(f)
    else:
        seen = {}
    
    if operation_id in seen:
        return False  # Already done
    
    seen[operation_id] = {"timestamp": str(datetime.now())}
    with open(tracker_file, 'w') as f:
        json.dump(seen, f)
    return True
```''',
        }
        
        return examples.get(template_type)
    
    def _call_openclaw_llm(self, prompt: str) -> Optional[str]:
        """Call via OpenClaw's native gateway (inherits auth)"""
        try:
            import subprocess
            import tempfile
            import os
            
            # Write a simple Python script that OpenClaw will execute
            # Escape the prompt for Python triple-quoted string
            escaped_prompt = prompt.replace('\\', '\\\\').replace('"""', '\\"\\"\\"')
            
            script = f'''#!/usr/bin/env python3
import os, requests

# Route through OpenClaw gateway — never call Anthropic directly
gw_url   = os.environ.get("OPENCLAW_GATEWAY_URL", "http://localhost:28789")
gw_token = os.environ.get("OPENCLAW_GATEWAY_TOKEN", "")

prompt = """{escaped_prompt}"""

resp = requests.post(
    f"{{gw_url}}/v1/messages",
    headers={{"x-api-key": gw_token, "content-type": "application/json"}},
    json={{"model": "anthropic/claude-sonnet-4-6", "max_tokens": 4096,
          "messages": [{{"role": "user", "content": prompt}}]}},
    timeout=120,
)
resp.raise_for_status()

print(resp.json()["content"][0]["text"])
'''

            with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
                f.write(script)
                script_file = f.name
            
            try:
                logger.info("Calling Anthropic via OpenClaw environment...")
                
                # Run with python3 (will inherit ANTHROPIC_API_KEY from environment)
                result = subprocess.run(
                    ['python3', script_file],
                    capture_output=True,
                    text=True,
                    timeout=90,
                    env={**os.environ}  # Inherit current environment
                )
                
                if result.returncode == 0:
                    logger.info("LLM response received")
                    return result.stdout.strip()
                else:
                    logger.error(f"LLM call failed: {result.stderr}")
            
            finally:
                Path(script_file).unlink(missing_ok=True)
        
        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            import traceback
            traceback.print_exc()
        
        return None
    
    def _call_llm_with_manual_key(self, prompt: str) -> Optional[str]:
        """Fallback: Ask user to set ANTHROPIC_API_KEY in V8 daemon"""
        logger.error("""\nANTHROPIC_API_KEY not available in V8 daemon environment.\n\nTo fix:\n1. Get key: openclaw auth status\n2. Set key: launchctl setenv ANTHROPIC_API_KEY sk-ant-...\n3. Restart daemon: launchctl unload ~/Library/LaunchAgents/com.openclaw.v8-meta-learning.plist && launchctl load ~/Library/LaunchAgents/com.openclaw.v8-meta-learning.plist\n""")
        return None
    
    def _parse_llm_response(self, response: str) -> Optional[Dict]:
        """Parse LLM JSON response"""
        try:
            # Remove markdown code blocks if present
            if '```json' in response:
                response = response.split('```json')[1].split('```')[0].strip()
            elif '```' in response:
                response = response.split('```')[1].split('```')[0].strip()
            
            # Parse JSON
            data = json.loads(response)
            
            # Validate required fields
            required = ['code', 'language', 'script_name', 'user_explanation']
            for field in required:
                if field not in data:
                    logger.error(f"Missing required field: {field}")
                    return None
            
            # Set defaults for optional fields
            data.setdefault('why_recommended', 'Detected repeated pattern')
            data.setdefault('what_changes', 'Adds automation for this workflow')
            data.setdefault('risk_level', 'medium')  # LLM code defaults to medium risk
            
            return data
        
        except json.JSONDecodeError as e:
            logger.error(f"JSON parse error: {e}")
            logger.error(f"Response: {response[:500]}")
        except Exception as e:
            logger.error(f"Parse error: {e}")
        
        return None
    
    def _check_rate_limit(self) -> bool:
        """Check if we've hit daily generation limit"""
        if not self.generation_log.exists():
            return True
        
        try:
            with open(self.generation_log) as f:
                log = json.load(f)
            
            today = datetime.now().strftime('%Y-%m-%d')
            today_count = log.get(today, 0)
            
            return today_count < self.max_generations_per_day
        
        except Exception:
            return True
    
    def _log_generation(self, pattern_type: str):
        """Log LLM generation for rate limiting"""
        try:
            if self.generation_log.exists():
                with open(self.generation_log) as f:
                    log = json.load(f)
            else:
                log = {}
            
            today = datetime.now().strftime('%Y-%m-%d')
            log[today] = log.get(today, 0) + 1
            
            with open(self.generation_log, 'w') as f:
                json.dump(log, f)
        
        except Exception as e:
            logger.error(f"Failed to log generation: {e}")
    
    def _load_learned_template(self, pattern_type: str) -> Optional[Dict]:
        """Load previously learned template for this pattern type"""
        template_file = self.learned_dir / f"{pattern_type}.json"
        
        if not template_file.exists():
            return None
        
        try:
            with open(template_file) as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load learned template: {e}")
            return None
    
    def _adapt_learned_template(self, template: Dict, pattern: Dict) -> Dict:
        """Adapt a learned template to current pattern"""
        # Simple adaptation: replace placeholder values
        code = template.get('code', '')
        
        # Replace pattern-specific values
        for key, value in pattern.items():
            if isinstance(value, str):
                placeholder = f"{{{{pattern.{key}}}}}"
                code = code.replace(placeholder, value)
        
        result = template.copy()
        result['code'] = code
        result['pattern'] = pattern
        result['generated_by'] = 'learned_template'
        
        return result
    
    def save_learned_template(self, pattern_type: str, code_result: Dict, success: bool = True):
        """Save successful template for future reuse"""
        
        if not success:
            logger.info(f"Not saving failed template for {pattern_type}")
            return
        
        template_file = self.learned_dir / f"{pattern_type}.json"
        
        template_data = {
            'pattern_type': pattern_type,
            'code': code_result.get('code'),
            'language': code_result.get('language'),
            'script_name': code_result.get('script_name'),
            'user_explanation': code_result.get('user_explanation'),
            'why_recommended': code_result.get('why_recommended'),
            'risk_level': code_result.get('risk_level', 'medium'),
            'learned_at': datetime.now().isoformat(),
            'usage_count': 0
        }
        
        with open(template_file, 'w') as f:
            json.dump(template_data, f, indent=2)
        
        logger.info(f"✅ Learned new template: {pattern_type}")


if __name__ == "__main__":
    # Test LLM generation
    generator = LLMCodeGenerator()
    
    test_pattern = {
        'type': 'recurring_meeting',
        'title': 'Weekly Standup',
        'weekday': 'Monday',
        'hour': 10,
        'count': 52,
        'confidence': 0.95,
        'description': 'Recurring meeting "Weekly Standup" (52 times)'
    }
    
    result = generator.generate_from_pattern(test_pattern)
    
    if result:
        print("✅ Generated code:")
        print(f"   Script: {result['script_name']}")
        print(f"   Language: {result['language']}")
        print(f"   Risk: {result['risk_level']}")
        print("\nCode preview:")
        print(result['code'][:500] + "...")
    else:
        print("❌ Generation failed")
