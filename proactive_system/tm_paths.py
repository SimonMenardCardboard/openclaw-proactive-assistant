#!/usr/bin/env python3
"""
Transmogrifier path resolver.
All intelligence modules should import paths from here — never hardcode
~/.openclaw/workspace/... which only exists on the dev machine.

On a user VM, TRANSMOGRIFIER_HOME is set by the provisioner to the VM's
working directory (e.g. /opt/transmogrifier or ~/transmogrifier).
On the dev machine it defaults to ~/.openclaw/workspace/integrations/intelligence.
"""

import os
from pathlib import Path

# Provisioner sets this env var on every user VM
TM_HOME = Path(os.environ.get(
    'TRANSMOGRIFIER_HOME',
    Path.home() / '.openclaw/workspace/integrations/intelligence'
))

# Standard sub-paths
LOGS_DIR = TM_HOME / 'logs'
DATA_DIR = TM_HOME / 'data'
CONFIG_DIR = TM_HOME / 'config'
QUEUE_DB = TM_HOME / 'proactive_queue.db'
CONTEXT_DB = TM_HOME / 'context.db'
MEMORY_DB = TM_HOME / 'tm_memory.db'   # Engram memory layer (separate from queue)

# Ensure dirs exist
for _dir in (LOGS_DIR, DATA_DIR, CONFIG_DIR):
    _dir.mkdir(parents=True, exist_ok=True)
