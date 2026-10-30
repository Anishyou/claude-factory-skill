"""Shared helpers for the factory hooks. Not a hook itself."""
import fnmatch
import json
import os
import re
import sys
from pathlib import Path

ACTIVE_STAGES = {"spec", "tests", "build", "review", "approve", "verify", "design"}


def read_input():
    try:
        return json.load(sys.stdin)
    except Exception:
        return {}


def project_dir(inp):
    d = os.environ.get("CLAUDE_PROJECT_DIR") or inp.get("cwd") or os.getcwd()
    return Path(d).resolve()


def load_config(root):
    p = root / "factory" / "factory.config.json"
    try:
        return json.loads(p.read_text())
    except FileNotFoundError:
        return {}
    except Exception as e:  # malformed config: fail closed, loudly
        sys.stderr.write(f"factory: cannot parse {p}: {e}\n")
        sys.exit(2)


def native_path(p):
    """Git Bash on Windows reports /c/Users/... ; Python there needs C:/Users/..."""
    if os.name == "nt" and isinstance(p, str):
        m = re.match(r"^/([A-Za-z])/(.*)$", p)
        if m:
            return f"{m.group(1).upper()}:/{m.group(2)}"
    return p


def jobs(root):
    out = []
    for jf in sorted((root / "factory" / "jobs").glob("*/job.json")):
        try:
            j = json.loads(jf.read_text())
            j["_dir"] = jf.parent
            if j.get("worktree"):
                j["worktree"] = native_path(j["worktree"])
            out.append(j)
        except Exception:
            continue
    return out


def job_for_session(root, session_id, fallback=False):
    """The active job this session orchestrates, if any.

    With fallback=True, a lone active job is returned even when no job carries
    this session id (the gate uses this so a forgotten `session` field never
    disables validation). The guard never falls back: it must not block a
    session that isn't running a job."""
    active = [j for j in jobs(root) if j.get("stage") in ACTIVE_STAGES]
    mine = [j for j in active if session_id and j.get("session") == session_id]
    if len(mine) == 1:
        return mine[0]
    if fallback and not mine and len(active) == 1:
        return active[0]
    return None


def job_for_path(root, path):
    """The job whose worktree contains `path`, if any."""
    p = Path(path).resolve()
    for j in jobs(root):
        wt = j.get("worktree")
        if not wt:
            continue
        try:
            p.relative_to(Path(wt).resolve())
            return j
        except ValueError:
            continue
    return None


def allowed_paths(job):
    """Patterns a human unlocked for this job via /factory allow."""
    f = job["_dir"] / "allow.md"
    if not f.exists():
        return []
    pats = []
    for line in f.read_text().splitlines():
        line = line.strip().lstrip("-").strip().strip("`")
        if line and not line.startswith("#"):
            pats.append(line)
    return pats


def matches(rel, pattern):
    """Gitignore-ish matching: 'dir/' matches anything under dir at any depth,
    'name' matches a basename anywhere, 'a/b' matches that path, globs allowed."""
    rel = rel.replace("\\", "/")
    while rel.startswith("./"):
        rel = rel[2:]
    rel = rel.lstrip("/")
    parts = rel.split("/")
    pat = pattern.replace("\\", "/")
    if pat.endswith("/"):
        d = pat.rstrip("/")
        # any run of directory segments (never the final file segment) matching d
        return any(fnmatch.fnmatch("/".join(parts[i:j]), d)
                   for i in range(len(parts) - 1) for j in range(i + 1, len(parts)))
    if "/" in pat:
        return fnmatch.fnmatch(rel, pat) or fnmatch.fnmatch(rel, pat.lstrip("/"))
    return any(fnmatch.fnmatch(part, pat) for part in parts)


def first_hit(rel, patterns):
    for pat in patterns:
        if matches(rel, pat):
            return pat
    return None


def protected_hit(rel, cfg, job=None):
    if job and first_hit(rel, allowed_paths(job)):
        return None
    return first_hit(rel, cfg.get("protectedPaths", []))


def forbidden_hit(command, cfg):
    for pat in cfg.get("forbiddenCommands", []):
        try:
            if re.search(pat, command):
                return pat
        except re.error:
            continue
    return None


def deny(reason):
    sys.stderr.write(reason.rstrip() + "\n")
    sys.exit(2)
