#!/usr/bin/env python3
"""SessionStart hook: expose this session's id to Bash as $FACTORY_SESSION_ID.

The orchestrator writes it into job.json, so the other hooks can tell which
job a given session (and its subagents) is working on when several factory
sessions run in parallel.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _factory import read_input  # noqa: E402

inp = read_input()
sid = inp.get("session_id", "")
env_file = os.environ.get("CLAUDE_ENV_FILE")
if sid and env_file:
    with open(env_file, "a") as f:
        f.write(f'export FACTORY_SESSION_ID="{sid}"\n')
sys.exit(0)
