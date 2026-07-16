#!/usr/bin/env python3
"""
Transmogrifier Engram policies — deliberately thin.

Deltas vs. Cardboard Legal (see legal_engram.py):
- NO retention floors, NO compliance gates, NO audit-log requirements.
- Items decay and can be purged normally.
- Recall is user-scoped only — no privilege gating.
- VM activity IS the salience signal: active VMs rank high, idle VMs decay.
"""

from __future__ import annotations

import math
from typing import Any, Dict, Optional

# Softer than CL's SOL decay: salience = base * 0.8^(days_inactive)
VM_SALIENCE_DECAY_BASE = 0.8
# Below this, a VM is considered neglected (dashboard signal)
VM_NEGLECT_THRESHOLD = 0.3
# 7±2 working-set cap
WM_MAX_SLOTS = 9


class TMRetentionPolicy:
    """No floors, no holds. Normal decay-driven lifecycle."""

    def may_archive(self, fact: Dict[str, Any]) -> bool:
        return fact.get("status") != "active"

    def may_purge(self, fact: Dict[str, Any]) -> bool:
        # Purgeable once retracted/superseded, or decayed to irrelevance.
        if fact.get("status") in ("retracted", "superseded"):
            return True
        return float(fact.get("salience", 1.0) or 0.0) < 0.05


class TMSaliencePolicy:
    """VM activity = salience. Idle VMs decay softly."""

    def salience(self, subject: str, predicate: str, value: str,
                 category: Optional[str] = None, tags: Optional[str] = None) -> float:
        s = 0.5
        if category in ("decision", "vm_event"):
            s = 0.7
        text = f"{predicate} {value} {tags or ''}".lower()
        if any(w in text for w in ("error", "failed", "billing", "urgent")):
            s = min(1.0, s + 0.2)
        return round(s, 3)

    @staticmethod
    def vm_salience(base_salience: float, days_inactive: float) -> float:
        """Effective VM salience given idle time. base * 0.8^days."""
        days = max(0.0, float(days_inactive))
        return round(base_salience * math.pow(VM_SALIENCE_DECAY_BASE, days), 4)

    @staticmethod
    def is_neglected(effective_salience: float) -> bool:
        return effective_salience < VM_NEGLECT_THRESHOLD


class TMRecallFilter:
    """User-scoped only. A fact is visible iff it belongs to the caller."""

    def allow(self, fact: Dict[str, Any], context: Dict[str, Any]) -> bool:
        return fact.get("user_id") == context.get("user_id")
