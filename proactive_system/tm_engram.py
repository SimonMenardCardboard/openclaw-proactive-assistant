#!/usr/bin/env python3
"""
Transmogrifier Engram — per-user, per-VM working memory.

Port of the Hobbes Prime / Cardboard Legal Engram pattern
(cardboard-legal/backend/hobbes_memory/engram.py) with TM's simpler policy
set (tm_policy.py): no privilege gating, no retention floors, no audit-log
compliance. What TM keeps:

- 7±2 per-user VM working set with pinning and salience-based eviction
- Soft activity decay: salience = base * 0.8^(days_inactive)
- vm_neglected signals for the dashboard (salience < 0.3)
- Token-seeded + spreading-activation associative recall over user facts
- Append-only VM lifecycle episodes

Storage: tm_memory.db (separate file from proactive_queue.db). Tables:
tm_engram_facts, tm_links, tm_wm, tm_episodes. Single-writer per process.
"""

from __future__ import annotations

import json
import re
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from tm_paths import MEMORY_DB
from tm_policy import (
    TMRecallFilter,
    TMRetentionPolicy,
    TMSaliencePolicy,
    VM_NEGLECT_THRESHOLD,
    WM_MAX_SLOTS,
)

TM_ENGRAM_SCHEMA_VERSION = 1

SCHEMA = """
CREATE TABLE IF NOT EXISTS tm_schema_version (
  component   TEXT NOT NULL,
  version     INTEGER NOT NULL,
  migrated_at TEXT NOT NULL,
  PRIMARY KEY (component, version)
);

CREATE TABLE IF NOT EXISTS tm_engram_facts (
  id               INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id          TEXT NOT NULL,
  subject          TEXT NOT NULL,
  predicate        TEXT NOT NULL,
  value            TEXT NOT NULL,
  category         TEXT,
  confidence       REAL NOT NULL DEFAULT 0.8,
  salience         REAL NOT NULL DEFAULT 0.5,
  tags             TEXT,
  status           TEXT NOT NULL DEFAULT 'active',  -- active|superseded|retracted
  last_activated   TEXT,
  activation_count INTEGER NOT NULL DEFAULT 0,
  created_at       TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_tm_facts_user ON tm_engram_facts(user_id, status);
CREATE INDEX IF NOT EXISTS idx_tm_facts_sp   ON tm_engram_facts(user_id, subject, predicate, status);

CREATE TABLE IF NOT EXISTS tm_links (
  src    INTEGER NOT NULL,
  dst    INTEGER NOT NULL,
  kind   TEXT NOT NULL,
  weight REAL NOT NULL DEFAULT 0.1,
  UNIQUE(src, dst, kind)
);
CREATE INDEX IF NOT EXISTS idx_tm_links_src ON tm_links(src);

CREATE TABLE IF NOT EXISTS tm_wm (
  user_id     TEXT NOT NULL,
  vm_id       TEXT NOT NULL,
  vm_label    TEXT,
  pinned      INTEGER NOT NULL DEFAULT 0,
  salience    REAL NOT NULL DEFAULT 1.0,
  last_active TEXT NOT NULL,
  evicted_at  TEXT,
  UNIQUE(user_id, vm_id)
);
CREATE INDEX IF NOT EXISTS idx_tm_wm_user ON tm_wm(user_id, evicted_at);

CREATE TABLE IF NOT EXISTS tm_episodes (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id    TEXT NOT NULL,
  vm_id      TEXT,
  event_type TEXT NOT NULL,
  payload    TEXT,
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_tm_episodes_user ON tm_episodes(user_id, event_type);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _days_since(iso_ts: Optional[str]) -> float:
    if not iso_ts:
        return float("inf")
    try:
        ts = datetime.fromisoformat(iso_ts)
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        return max(0.0, (datetime.now(timezone.utc) - ts).total_seconds() / 86400.0)
    except Exception:
        return float("inf")


class TMMemoryService:
    """Per-user, per-VM Engram memory for Transmogrifier."""

    def __init__(
        self,
        db_path: Optional[str] = None,
        salience_policy: Optional[TMSaliencePolicy] = None,
        retention_policy: Optional[TMRetentionPolicy] = None,
        recall_filter: Optional[TMRecallFilter] = None,
    ) -> None:
        self.db_path = str(db_path or MEMORY_DB)
        self.salience_policy = salience_policy or TMSaliencePolicy()
        self.retention_policy = retention_policy or TMRetentionPolicy()
        self.recall_filter = recall_filter or TMRecallFilter()
        self._lock = threading.Lock()
        self._init_db()

    # ── DB plumbing ─────────────────────────────────────────────────────────

    @contextmanager
    def _conn(self):
        conn = sqlite3.connect(self.db_path, check_same_thread=False, timeout=30)
        conn.row_factory = sqlite3.Row
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    def _init_db(self) -> None:
        with self._conn() as conn:
            conn.executescript(SCHEMA)
            conn.execute(
                "INSERT OR REPLACE INTO tm_schema_version(component, version, migrated_at) VALUES (?,?,?)",
                ("tm_engram", TM_ENGRAM_SCHEMA_VERSION, _now()),
            )

    # ── Episodes (append-only VM lifecycle events) ──────────────────────────

    def episode(self, user_id: str, vm_id: Optional[str], event_type: str,
                payload: Any = None) -> int:
        data = payload if isinstance(payload, str) or payload is None else json.dumps(payload)
        with self._lock, self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO tm_episodes(user_id, vm_id, event_type, payload, created_at) VALUES (?,?,?,?,?)",
                (user_id, vm_id, event_type, data, _now()),
            )
            return cur.lastrowid

    def episodes(self, user_id: str, event_type: Optional[str] = None,
                 limit: int = 50) -> List[Dict[str, Any]]:
        q = "SELECT * FROM tm_episodes WHERE user_id=?"
        params: List[Any] = [user_id]
        if event_type:
            q += " AND event_type=?"
            params.append(event_type)
        q += " ORDER BY id DESC LIMIT ?"
        params.append(limit)
        with self._conn() as conn:
            return [dict(r) for r in conn.execute(q, params).fetchall()]

    # ── Facts ───────────────────────────────────────────────────────────────

    def remember(self, user_id: str, subject: str, predicate: str, value: Any,
                 category: str = "fact", confidence: float = 0.9,
                 tags: Optional[str] = None) -> int:
        """Write a user-scoped fact. Same (subject, predicate) with a different
        value supersedes the old fact (chain kept via tm_links)."""
        val = value if isinstance(value, str) else json.dumps(value)
        salience = self.salience_policy.salience(subject, predicate, val, category, tags)
        now = _now()
        with self._lock, self._conn() as conn:
            olds = conn.execute(
                "SELECT id, value FROM tm_engram_facts WHERE user_id=? AND subject=? AND predicate=? AND status='active'",
                (user_id, subject, predicate),
            ).fetchall()
            for r in olds:
                if r["value"] == val:
                    conn.execute(
                        "UPDATE tm_engram_facts SET confidence=max(confidence,?), last_activated=? WHERE id=?",
                        (confidence, now, r["id"]),
                    )
                    return r["id"]
            cur = conn.execute(
                """INSERT INTO tm_engram_facts
                   (user_id, subject, predicate, value, category, confidence, salience, tags, created_at, last_activated)
                   VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (user_id, subject, predicate, val, category, confidence, salience, tags, now, now),
            )
            new_id = cur.lastrowid
            for r in olds:
                conn.execute("UPDATE tm_engram_facts SET status='superseded' WHERE id=?", (r["id"],))
                conn.execute(
                    "INSERT OR IGNORE INTO tm_links(src,dst,kind,weight) VALUES (?,?,'supersedes',0.5)",
                    (new_id, r["id"]),
                )
            # associative same-subject links
            sibs = conn.execute(
                "SELECT id FROM tm_engram_facts WHERE user_id=? AND subject=? AND status='active' AND id!=? ORDER BY id DESC LIMIT 5",
                (user_id, subject, new_id),
            ).fetchall()
            for s in sibs:
                for a, b in ((new_id, s["id"]), (s["id"], new_id)):
                    conn.execute(
                        "INSERT OR IGNORE INTO tm_links(src,dst,kind,weight) VALUES (?,?,'same_subject',0.15)",
                        (a, b),
                    )
            return new_id

    # ── Recall (token-seed + spreading activation) ──────────────────────────

    def recall(self, user_id: str, query: str, k: int = 8, hops: int = 2) -> List[Dict[str, Any]]:
        ctx = {"user_id": user_id}
        tokens = [t.lower() for t in re.findall(r"[A-Za-z0-9_./:@-]{2,}", query or "")][:12]
        if not tokens:
            return []
        with self._conn() as conn:
            clauses, params = [], [user_id]
            for t in tokens:
                like = f"%{t}%"
                clauses.append(
                    "(LOWER(subject) LIKE ? OR LOWER(predicate) LIKE ? OR LOWER(value) LIKE ? OR LOWER(coalesce(tags,'')) LIKE ?)"
                )
                params.extend([like, like, like, like])
            rows = conn.execute(
                f"""SELECT id FROM tm_engram_facts
                    WHERE user_id=? AND status='active' AND ({' OR '.join(clauses)})
                    ORDER BY salience DESC LIMIT 40""",
                params,
            ).fetchall()
            seeds = {r["id"]: 1.0 / (1 + i * 0.25) for i, r in enumerate(rows)}

            activation = dict(seeds)
            frontier = dict(seeds)
            for _ in range(hops):
                if not frontier:
                    break
                ids = tuple(frontier.keys())
                nxt: Dict[int, float] = {}
                q = f"SELECT src,dst,weight FROM tm_links WHERE src IN ({','.join('?' * len(ids))})"
                for e in conn.execute(q, ids):
                    a = frontier[e["src"]] * e["weight"] * 0.5
                    if a > 0.005:
                        nxt[e["dst"]] = nxt.get(e["dst"], 0.0) + a
                for nid, a in nxt.items():
                    activation[nid] = activation.get(nid, 0.0) + a
                frontier = nxt

            results: List[Dict[str, Any]] = []
            if activation:
                ids = tuple(activation.keys())
                rows = conn.execute(
                    f"""SELECT * FROM tm_engram_facts
                        WHERE id IN ({','.join('?' * len(ids))}) AND status='active'""",
                    ids,
                ).fetchall()
                for row in rows:
                    d = dict(row)
                    if not self.recall_filter.allow(d, ctx):
                        continue
                    d["activation"] = round(
                        activation[d["id"]] * d["confidence"] * (0.5 + 0.5 * (d["salience"] or 0.5)), 4)
                    results.append(d)
            results.sort(key=lambda x: -x["activation"])
            results = results[:k]
            now = _now()
            for f in results:
                conn.execute(
                    "UPDATE tm_engram_facts SET activation_count=activation_count+1, last_activated=? WHERE id=?",
                    (now, f["id"]),
                )
            return results

    # ── VM working memory (7±2 per user) ────────────────────────────────────

    def vm_push(self, user_id: str, vm_id: str, vm_label: str = "") -> List[Dict[str, Any]]:
        """Push a VM into the user's working set (salience refreshed to 1.0).
        Evicts the lowest-salience non-pinned VM when over the 7±2 cap."""
        now = _now()
        with self._lock, self._conn() as conn:
            conn.execute(
                """INSERT INTO tm_wm(user_id, vm_id, vm_label, salience, last_active, evicted_at)
                   VALUES (?,?,?,1.0,?,NULL)
                   ON CONFLICT(user_id, vm_id) DO UPDATE SET
                     salience=1.0,
                     vm_label=CASE WHEN excluded.vm_label!='' THEN excluded.vm_label ELSE vm_label END,
                     last_active=excluded.last_active,
                     evicted_at=NULL""",
                (user_id, vm_id, vm_label, now),
            )
            rows = conn.execute(
                "SELECT * FROM tm_wm WHERE user_id=? AND evicted_at IS NULL "
                "ORDER BY pinned DESC, salience DESC, last_active DESC",
                (user_id,),
            ).fetchall()
            if len(rows) > WM_MAX_SLOTS:
                for victim in [r for r in rows[WM_MAX_SLOTS:] if not r["pinned"]]:
                    conn.execute(
                        "UPDATE tm_wm SET evicted_at=? WHERE user_id=? AND vm_id=?",
                        (now, user_id, victim["vm_id"]),
                    )
                    conn.execute(
                        "INSERT INTO tm_episodes(user_id, vm_id, event_type, payload, created_at) VALUES (?,?,?,?,?)",
                        (user_id, victim["vm_id"], "vm_evicted",
                         json.dumps({"salience": victim["salience"], "reason": "wm_cap"}), now),
                    )
        return self.get_working_set(user_id)

    def vm_pin(self, user_id: str, vm_id: str, pin: bool = True) -> None:
        with self._lock, self._conn() as conn:
            conn.execute(
                "UPDATE tm_wm SET pinned=? WHERE user_id=? AND vm_id=?",
                (int(pin), user_id, vm_id),
            )

    def get_working_set(self, user_id: str) -> List[Dict[str, Any]]:
        """Active VMs with effective (decayed-at-read) salience scores."""
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM tm_wm WHERE user_id=? AND evicted_at IS NULL "
                "ORDER BY pinned DESC, salience DESC",
                (user_id,),
            ).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d["pinned"] = bool(d["pinned"])
            d["effective_salience"] = self.salience_policy.vm_salience(
                d["salience"], _days_since(d["last_active"]))
            out.append(d)
        out.sort(key=lambda x: (-int(x["pinned"]), -x["effective_salience"]))
        return out

    def vm_tick(self, user_id: str) -> Dict[str, List[Dict[str, Any]]]:
        """Daily decay tick. Applies salience = base * 0.8^(days_inactive),
        emits vm_neglected episodes for VMs below the neglect threshold.
        Pinned VMs decay too but are never evicted; neglect signal still fires.

        Returns {"neglected": [...], "working_set": [...]}.
        """
        now = _now()
        neglected: List[Dict[str, Any]] = []
        with self._lock, self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM tm_wm WHERE user_id=? AND evicted_at IS NULL",
                (user_id,),
            ).fetchall()
            for r in rows:
                eff = self.salience_policy.vm_salience(
                    r["salience"], _days_since(r["last_active"]))
                conn.execute(
                    "UPDATE tm_wm SET salience=?, last_active=? WHERE user_id=? AND vm_id=?",
                    (eff, now, user_id, r["vm_id"]),
                )
                if self.salience_policy.is_neglected(eff):
                    neglected.append({"vm_id": r["vm_id"], "vm_label": r["vm_label"],
                                      "salience": eff, "pinned": bool(r["pinned"])})
                    conn.execute(
                        "INSERT INTO tm_episodes(user_id, vm_id, event_type, payload, created_at) VALUES (?,?,?,?,?)",
                        (user_id, r["vm_id"], "vm_neglected",
                         json.dumps({"salience": eff, "threshold": VM_NEGLECT_THRESHOLD}), now),
                    )
        return {"neglected": neglected, "working_set": self.get_working_set(user_id)}
