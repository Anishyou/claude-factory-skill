#!/usr/bin/env python3
"""PreToolUse hook: hard boundaries for every agent in the factory.

Edit | Write
  - factory/jobs/** and factory/backlog.md are always writable (job state).
  - Inside a job worktree: deny protected paths (factory.config.json
    `protectedPaths`) unless the job's allow.md unlocks them.
  - In the main checkout while this session runs a job: deny. Code changes
    belong in the worktree; the main checkout is the user's.

Bash
  - Deny any command matching `forbiddenCommands`.

Exit 2 denies the call and sends the reason back to the agent. A deny here
holds in every permission mode, including --dangerously-skip-permissions.
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _factory import (  # noqa: E402
    deny, forbidden_hit, job_for_path, job_for_session, load_config,
    native_path, project_dir, protected_hit, read_input,
)

inp = read_input()
root = project_dir(inp)
cfg = load_config(root)
tool = inp.get("tool_name", "")
args = inp.get("tool_input", {}) or {}

if tool == "Bash":
    cmd = args.get("command", "") or ""
    hit = forbidden_hit(cmd, cfg)
    if hit:
        deny(f"factory: command denied by forbiddenCommands rule /{hit}/.\n"
             f"This factory never force-pushes, pushes to the base branch, merges locally, "
             f"stages with -A, or deploys. Do the task another way, or write STATUS: BLOCKED "
             f"and explain why this command is needed.")
    sys.exit(0)

if tool in ("Edit", "Write", "MultiEdit", "NotebookEdit"):
    fp = args.get("file_path") or args.get("notebook_path") or ""
    if not fp:
        sys.exit(0)
    path = Path(native_path(fp))
    if not path.is_absolute():
        path = root / path
    path = path.resolve()

    # Job state in the main checkout is always writable.
    try:
        rel_main = path.relative_to(root).as_posix()
    except ValueError:
        rel_main = None
    if rel_main and (rel_main.startswith("factory/jobs/")
                     or rel_main in ("factory/backlog.md", "factory/roadmap.md", "factory/coverage.md")):
        sys.exit(0)

    job = job_for_path(root, path)
    if job:
        rel = path.relative_to(Path(job["worktree"]).resolve()).as_posix()
        hit = protected_hit(rel, cfg, job)
        if hit:
            deny(f"factory: `{rel}` is a protected path (rule `{hit}`). Agents may not change it.\n"
                 f"If the spec cannot be met without it, revert any other attempt, write "
                 f"STATUS: BLOCKED in build.md under a ## Blocked heading naming the path and why, "
                 f"and stop. A human can unlock it with: /factory allow {job['id']} {rel}")
        sys.exit(0)

    # Not in any worktree. If this session is running a job, the main checkout is off limits.
    if rel_main is not None:
        mine = job_for_session(root, inp.get("session_id"))
        if mine:
            deny(f"factory: this session is running job {mine['id']}. Code changes go in its "
                 f"worktree ({mine['worktree']}), not the main checkout. Only files under "
                 f"factory/jobs/ may be written here.")
    sys.exit(0)

sys.exit(0)
