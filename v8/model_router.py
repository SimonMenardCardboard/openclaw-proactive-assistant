#!/usr/bin/env python3
"""
Dynamic LLM routing based on task classification
Routes tasks to optimal model based on complexity, context, and cost.

Usage:
    from model_router import ModelRouter
    
    router = ModelRouter()
    model = router.route("what's on my calendar today?")
    # Returns: "google/gemini-2.0-flash-exp"
"""

import re
import json
from typing import Dict, Optional, List, Tuple
from datetime import datetime


class ModelRouter:
    """Routes tasks to optimal LLM based on complexity and cost"""
    
    # Model pricing (per 1M tokens, input/output)
    MODELS = {
        "flash": {
            "name": "google/gemini-2.0-flash-exp",
            "cost": (0.075, 0.30),
            "context": 1_000_000,
            "speed": "fast",
            "quality": "good"
        },
        "pro": {
            "name": "google/gemini-1.5-pro",
            "cost": (1.25, 5.00),
            "context": 2_000_000,
            "speed": "medium",
            "quality": "excellent"
        },
        "sonnet": {
            "name": "anthropic/claude-sonnet-4-5",
            "cost": (3.00, 15.00),
            "context": 200_000,
            "speed": "medium",
            "quality": "excellent"
        }
    }
    
    # Task category detection patterns
    PATTERNS = {
        "calendar": [r"\bcalendar\b", r"\bevent\b", r"\bmeeting\b", r"\bschedule\b", r"what'?s on my"],
        "email": [r"\bemail\b", r"\binbox\b", r"\bmessage\b", r"\bscan\b", r"\bgmail\b"],
        "digest": [r"\bdigest\b", r"\bsummary\b", r"\bmorning\b", r"\bevening\b"],
        "monitoring": [r"\bstatus\b", r"\bcheck\b", r"\bmonitor\b", r"\bhealth\b"],
        "training": [r"\bwhoop\b", r"\brecovery\b", r"\btraining\b", r"\bworkout\b"],
        "supplement": [r"\bsupplement\b", r"\bnutrition\b", r"\bmacrofactor\b"],
        "memory": [r"\bmemory\b", r"\bremember\b", r"\brecall\b", r"\bsave to\b"],
        "task": [r"\btask\b", r"\btodo\b", r"\bextract\b"],
        "v6_action": [r"refresh.*token", r"restart.*tunnel", r"launchagent"],
        "v7_diagnosis": [r"\bdiagnose\b", r"root cause", r"\bfailure\b", r"\bcascade\b", r"why did.*fail"],
        "v8_pattern": [r"\bpattern\b", r"\blearn\b", r"\boptimize\b", r"\bworkflow\b"],
        "architecture": [r"\bdesign\b", r"\barchitecture\b", r"\bsystem\b", r"\broadmap\b"],
        "writing": [r"\bdraft\b", r"\bwrite\b", r"\bcompose\b", r"\bmemo\b", r"\bdocument\b"],
        "debugging": [r"\bdebug\b", r"\bfix\b", r"\berror\b", r"\bbroken\b", r"what'?s wrong"],
        "code_review": [r"review.*code", r"\bpr\b", r"pull request"],
    }
    
    # External/high-stakes keywords
    EXTERNAL_KEYWORDS = [
        "client", "customer", "partner", "public", "post", "tweet",
        "email to", "send to", "draft email", "compose email", "reply to"
    ]
    
    # Complex reasoning indicators
    COMPLEX_INDICATORS = [
        "why", "how", "explain", "compare", "analyze", "evaluate",
        "recommend", "strategy", "plan", "decide"
    ]
    
    def __init__(self, log_file: Optional[str] = None):
        """
        Initialize router
        
        Args:
            log_file: Optional path to log routing decisions
        """
        self.log_file = log_file
        self.routing_history: List[Dict] = []
    
    def route(self, prompt: str, context: Optional[Dict] = None) -> str:
        """
        Route task to optimal model
        
        Args:
            prompt: User's task/question
            context: Optional metadata (tokens, audience, etc.)
        
        Returns:
            Model identifier (e.g., "google/gemini-2.0-flash-exp")
        """
        prompt_lower = prompt.lower()
        category = self.classify(prompt)
        
        # Rule 1: Large context needs Pro
        if context and context.get("input_tokens", 0) > 128_000:
            model = self.MODELS["pro"]["name"]
            reason = "large_context"
        
        # Rule 2: External/high-stakes needs Sonnet
        elif self._is_external(prompt_lower, context):
            model = self.MODELS["sonnet"]["name"]
            reason = "external_high_stakes"
        
        # Rule 3: Complex reasoning needs Sonnet
        elif self._is_complex_reasoning(prompt_lower, category):
            model = self.MODELS["sonnet"]["name"]
            reason = "complex_reasoning"
        
        # Rule 4: Creative writing needs Sonnet
        elif self._is_creative_writing(prompt_lower, context):
            model = self.MODELS["sonnet"]["name"]
            reason = "creative_writing"
        
        # Rule 5: Default to Flash (90% of tasks)
        else:
            model = self.MODELS["flash"]["name"]
            reason = "default_flash"
        
        # Log decision
        self._log_decision(prompt, category, model, reason, context)
        
        return model
    
    def _is_external(self, prompt: str, context: Optional[Dict]) -> bool:
        """Check if task is external/high-stakes"""
        if context and context.get("audience") == "client":
            return True
        
        return any(kw in prompt for kw in self.EXTERNAL_KEYWORDS)
    
    def _is_complex_reasoning(self, prompt: str, category: str) -> bool:
        """Check if task requires complex reasoning"""
        # V7 diagnosis always needs Sonnet
        if category in ["v7_diagnosis", "debugging"]:
            return True
        
        # Architecture and code review need Sonnet
        if category in ["architecture", "code_review"]:
            return True
        
        # Check for complex reasoning indicators
        complex_count = sum(1 for ind in self.COMPLEX_INDICATORS if ind in prompt)
        if complex_count >= 2:  # Multiple complex indicators
            return True
        
        return False
    
    def _is_creative_writing(self, prompt: str, context: Optional[Dict]) -> bool:
        """Check if task is creative writing"""
        # Check for writing keywords
        is_writing = any(re.search(pattern, prompt) for pattern in self.PATTERNS["writing"])
        
        if not is_writing:
            return False
        
        # Long-form writing gets Sonnet
        if context and context.get("target_length", 0) > 500:
            return True
        
        # Documents/roadmaps get Sonnet
        doc_keywords = ["roadmap", "documentation", "skill", "guide", "report"]
        return any(kw in prompt for kw in doc_keywords)
    
    def classify(self, prompt: str) -> str:
        """
        Classify task category (for debugging/logging)
        
        Returns:
            Category name (e.g., "calendar", "v7_diagnosis")
        """
        prompt_lower = prompt.lower()
        
        # Check patterns in priority order
        priority_categories = [
            "v7_diagnosis", "architecture", "code_review",  # High priority
            "calendar", "email", "digest", "training",       # Common tasks
        ]
        
        for category in priority_categories:
            if any(re.search(pattern, prompt_lower) for pattern in self.PATTERNS[category]):
                return category
        
        # Check remaining patterns
        for category, patterns in self.PATTERNS.items():
            if category in priority_categories:
                continue
            if any(re.search(pattern, prompt_lower) for pattern in patterns):
                return category
        
        return "general"
    
    def estimate_cost(self, model: str, input_tokens: int, output_tokens: int) -> float:
        """
        Estimate task cost
        
        Args:
            model: Model name
            input_tokens: Input token count
            output_tokens: Output token count
        
        Returns:
            Cost in USD
        """
        # Find model pricing
        pricing = None
        for m in self.MODELS.values():
            if m["name"] == model:
                pricing = m["cost"]
                break
        
        if not pricing:
            return 0.0  # Unknown model
        
        input_cost = (input_tokens / 1_000_000) * pricing[0]
        output_cost = (output_tokens / 1_000_000) * pricing[1]
        
        return input_cost + output_cost
    
    def get_cost_savings(self, prompt: str, routed_model: str, 
                        input_tokens: int, output_tokens: int) -> Dict:
        """
        Calculate cost savings vs always using Sonnet
        
        Returns:
            Dict with cost comparison and savings
        """
        routed_cost = self.estimate_cost(routed_model, input_tokens, output_tokens)
        sonnet_cost = self.estimate_cost(
            self.MODELS["sonnet"]["name"], input_tokens, output_tokens
        )
        
        savings = sonnet_cost - routed_cost
        savings_pct = (savings / sonnet_cost * 100) if sonnet_cost > 0 else 0
        
        return {
            "routed_model": routed_model,
            "routed_cost": round(routed_cost, 4),
            "sonnet_cost": round(sonnet_cost, 4),
            "savings": round(savings, 4),
            "savings_pct": round(savings_pct, 1)
        }
    
    def _log_decision(self, prompt: str, category: str, model: str, 
                     reason: str, context: Optional[Dict]):
        """Log routing decision for analysis"""
        decision = {
            "timestamp": datetime.now().isoformat(),
            "prompt": prompt[:100],  # First 100 chars
            "category": category,
            "model": model,
            "reason": reason,
            "context": context or {}
        }
        
        self.routing_history.append(decision)
        
        if self.log_file:
            with open(self.log_file, 'a') as f:
                f.write(json.dumps(decision) + '\n')
    
    def get_routing_stats(self) -> Dict:
        """
        Analyze routing history
        
        Returns:
            Statistics on routing decisions
        """
        if not self.routing_history:
            return {"error": "No routing history"}
        
        total = len(self.routing_history)
        
        # Count by model
        by_model = {}
        for decision in self.routing_history:
            model = decision["model"]
            by_model[model] = by_model.get(model, 0) + 1
        
        # Count by category
        by_category = {}
        for decision in self.routing_history:
            cat = decision["category"]
            by_category[cat] = by_category.get(cat, 0) + 1
        
        # Calculate percentages
        model_pcts = {
            model: round(count / total * 100, 1)
            for model, count in by_model.items()
        }
        
        return {
            "total_decisions": total,
            "by_model": by_model,
            "by_model_pct": model_pcts,
            "by_category": by_category,
            "flash_usage_pct": model_pcts.get(self.MODELS["flash"]["name"], 0)
        }


# CLI for testing
if __name__ == "__main__":
    import sys
    
    router = ModelRouter()
    
    if len(sys.argv) < 2:
        print("Usage: python model_router.py 'task prompt' [input_tokens] [output_tokens]")
        print("\nExamples:")
        print("  python model_router.py \"what's on my calendar today?\"")
        print("  python model_router.py \"draft email to client\" 1000 500")
        print("  python model_router.py \"diagnose WHOOP API failure\" 2000 1000")
        sys.exit(1)
    
    prompt = " ".join(sys.argv[1:2])
    input_tokens = int(sys.argv[2]) if len(sys.argv) > 2 else 1000
    output_tokens = int(sys.argv[3]) if len(sys.argv) > 3 else 500
    
    # Route and classify
    model = router.route(prompt)
    category = router.classify(prompt)
    
    print(f"\n{'='*60}")
    print(f"Prompt: {prompt}")
    print(f"Category: {category}")
    print(f"Model: {model}")
    print(f"{'='*60}")
    
    # Estimate cost and savings
    cost = router.estimate_cost(model, input_tokens, output_tokens)
    savings = router.get_cost_savings(prompt, model, input_tokens, output_tokens)
    
    print(f"\nCost Analysis (estimated):")
    print(f"  Input tokens: {input_tokens:,}")
    print(f"  Output tokens: {output_tokens:,}")
    print(f"  Routed model cost: ${savings['routed_cost']:.4f}")
    print(f"  Sonnet cost: ${savings['sonnet_cost']:.4f}")
    print(f"  Savings: ${savings['savings']:.4f} ({savings['savings_pct']}%)")
    print()
