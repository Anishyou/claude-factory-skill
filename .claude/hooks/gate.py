#!/usr/bin/env python3
"""SubagentStop hook for `builder` and `test-writer`: the deterministic gate.

An agent may not finish until, in the job's worktree:
  1. its status file has a valid first line
     (build.md: STATUS: READY | BLOCKED, tests.md: STATUS: WRITTEN | SKIPPED)
  2. it is on the job branch and the tree is clean (everything committed)
  3. no protected path changed on the branch (unless allow.md unlocks it)
  4. the test-writer only touched `testPaths` (when configured)
  5. every validation command for this phase passes

On failure the hook exits 2: the agent is sent back with the reason and keeps
working. STATUS: BLOCKED skips 5, because a blocked build is reported, not
shipped. The result is written to <job>/gate.md so the dashboard and the
approver can see it.
"""
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _factory import (  # noqa: E402
    allowed_paths, first_hit, job_for_session, load_config, project_dir,
    protected_hit, read_input,
)

PHASES = {"builder": ("build", "build.md", ("STATUS: READY", "STATUS: BLOCKED")),
          "test-writer": ("tests", "tests.md", ("STATUS: WRITTEN", "STATUS: SKIPPED"))}

inp = read_input()
if inp.get("stop_hook_active"):
    sys.exit(0)  # never loop forever
agent = inp.get("agent_type", "")
if agent not in PHASES:
    sys.exit(0)
phase, status_file, valid = PHASES[agent]

root = project_dir(inp)
cfg = load_config(root)
job = job_for_session(root, inp.get("session_id"), fallback=True)
if not job:
    sys.stderr.write("factory gate: could not find this session's active job; gate skipped.\n")
    sys.exit(0)

jobdir = job["_dir"]
wt = Path(job["worktree"]).resolve()
base = cfg.get("baseBranch", "main")
lines = []
failures = []


def log(s):
    lines.append(s)


def sh(cmd, timeout=60):
    p = subprocess.run(cmd, shell=True, cwd=wt, capture_output=True, text=True, timeout=timeout)
    return p.returncode, (p.stdout + p.stderr)


def fail(msg):
    failures.append(msg)
    log(f"- FAIL: {msg.splitlines()[0]}")


# 1. status file
sf = jobdir / status_file
first = sf.read_text().splitlines()[0].strip() if sf.exists() and sf.read_text().strip() else ""
if first not in valid:
    fail(f"{status_file} must start with one of {' | '.join(valid)} (found: {first or 'nothing'}).")
blocked = first in ("STATUS: BLOCKED", "STATUS: SKIPPED")
log(f"- {status_file}: {first or 'missing'}")

# 2. branch + clean tree
if not wt.is_dir():
    fail(f"worktree {wt} does not exist.")
else:
    rc, out = sh("git branch --show-current")
    cur = out.strip()
    if cur != job.get("branch"):
        fail(f"worktree is on `{cur}`, expected `{job.get('branch')}`.")
    rc, out = sh("git status --porcelain")
    if out.strip():
        fail("uncommitted changes in the worktree. Commit your work (stage explicit paths) "
             "so the tree is clean:\n" + out.strip())
    log(f"- branch: {cur}, tree {'clean' if not out.strip() else 'DIRTY'}")

    # 3. protected paths on the branch
    rc, out = sh(f"git diff --name-only {base}...HEAD")
    changed = [l.strip() for l in out.splitlines() if l.strip()]
    hits = [(f, protected_hit(f, cfg, job)) for f in changed]
    hits = [(f, h) for f, h in hits if h]
    if hits:
        fail("protected paths changed on this branch: "
             + ", ".join(f"`{f}` ({h})" for f, h in hits)
             + ". Revert them, or write STATUS: BLOCKED naming the paths and why they are needed. "
               f"A human can unlock with /factory allow {job['id']} <path>.")
    log(f"- changed files: {len(changed)}" + (f", protected: {len(hits)}" if hits else ""))

    # 4. test-writer scope
    if agent == "test-writer" and cfg.get("testPaths"):
        allowed = cfg["testPaths"] + allowed_paths(job)
        out_of_scope = [f for f in changed if not first_hit(f, allowed)]
        if out_of_scope:
            fail("test-writer changed files outside testPaths: "
                 + ", ".join(f"`{f}`" for f in out_of_scope)
                 + ". Only tests may change in this phase; revert the rest.")

    # 5. validation
    if not blocked and not failures:
        timeout = int(cfg.get("validationTimeoutSeconds", 900))
        for v in cfg.get("validation", []):
            if phase not in v.get("phases", ["build"]):
                continue
            t0 = time.time()
            try:
                rc, out = sh(v["cmd"], timeout=timeout)
            except subprocess.TimeoutExpired:
                rc, out = 124, f"timed out after {timeout}s"
            secs = f"{time.time() - t0:.0f}s"
            if rc == 0:
                log(f"- {v['name']}: pass ({secs}) `{v['cmd']}`")
            else:
                tail = "\n".join(out.strip().splitlines()[-40:])
                log(f"- {v['name']}: FAIL ({secs}) `{v['cmd']}`")
                fail(f"`{v['cmd']}` failed (exit {rc}). Fix it and run it again before finishing.\n"
                     f"--- last lines ---\n{tail}")
    elif blocked:
        log("- validation: skipped (status is BLOCKED/SKIPPED)")

verdict = "GATE: PASS" if not failures else "GATE: FAIL"
stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
report = (
    f"{verdict}\n\n# Gate: {agent} · round {job.get('round', 0)} · {stamp}\n\n"
    + "\n".join(lines) + "\n"
    + ("\n## Why it failed\n" + "\n\n".join(f"{i+1}. {m}" for i, m in enumerate(failures)) + "\n" if failures else "")
)
(jobdir / "gate.md").write_text(report)

if failures:
    sys.stderr.write(
        "factory gate: you may not finish yet.\n\n"
        + "\n\n".join(f"{i+1}. {m}" for i, m in enumerate(failures))
        + f"\n\nFix these in the worktree, commit, update {status_file}, then finish again. "
          "Do not change the validation commands, hooks or config to make this pass.\n")
    sys.exit(2)
sys.exit(0)
