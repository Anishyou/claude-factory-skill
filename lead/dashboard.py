#!/usr/bin/env python3
"""The factory dashboard, for one repo or several: one local page to work from.

    python3 lead/dashboard.py                          this repo
    python3 lead/dashboard.py ../shop-api ../shop-web   several repos, one page
    python3 lead/dashboard.py --port 8010

Open http://127.0.0.1:8000/ . The page (dashboard.html) has two views. The
queue lists the items each repo's lead wrote to lead/state/queue/, most urgent
first. The line shows where every job in each repo's factory/jobs/ stands.
When you decide on an item, this server writes your decision into the item's
JSON file and nothing else: it never runs a command. The repo's lead reads the
decision on its next wake and runs the matching /factory command.

It reads the factory's files and never changes them. Each repo's factory/
folder is served under /r/<repo>/, which is where job files and design
mockups are read from.

Standard library only. Listens on 127.0.0.1 and nowhere else.
"""
import argparse
import json
import os
import posixpath
import re
import sys
import tempfile
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit

HERE = Path(__file__).resolve().parent
ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,150}$")
KINDS = {
    "escalation": ["approve", "rework", "allow"],
    "design": ["approve", "rework"],
    "pr": ["rework"],
    "decision": ["answer"],
    "policy": ["approve", "reject"],
    "idea": ["approve", "reject"],
    "stalled": ["dismiss"],
}
NEEDS_NOTE = {"rework", "allow", "answer"}
MAX_NOTE = 20_000
MAX_BODY = 64_000


def now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class Repo:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.factory = self.root / "factory"   # the factory's files: read, never written
        self.lead = self.root / "lead"         # this skill's folder in that repo
        self.name = self.root.name
        self.queue = self.lead / "state" / "queue"
        self.done = self.queue / "done"

    def status_line(self):
        try:
            with open(self.lead / "state" / "STATUS.md", encoding="utf-8") as f:
                return f.readline().strip()
        except OSError:
            return ""

    def _load(self, path):
        with open(path, encoding="utf-8") as f:
            item = json.load(f)
        if not isinstance(item, dict):
            raise ValueError("not a JSON object")
        if item.get("id") != path.stem:
            raise ValueError(f"id {item.get('id')!r} does not match the file name")
        if item.get("kind") not in KINDS:
            raise ValueError(f"unknown kind {item.get('kind')!r}")
        return item

    def items(self, folder=None):
        """(items, problems) for queue/ or queue/done/. A malformed file is a
        problem the page shows; it never takes the queue down."""
        folder = folder or self.queue
        items, problems = [], []
        if not folder.is_dir():
            return items, problems
        for path in sorted(folder.glob("*.json")):
            try:
                items.append(self._load(path))
            except (OSError, ValueError) as e:
                problems.append(f"{self.name}: {path.name}: {e}")
        return items, problems

    def item_path(self, item_id):
        if not ID_RE.match(item_id or ""):
            raise ValueError("bad item id")
        return self.queue / f"{item_id}.json"

    def write(self, item):
        """Replace the item file in one step, so the lead never reads half a file."""
        path = self.item_path(item["id"])
        fd, tmp = tempfile.mkstemp(dir=str(self.queue), prefix=".tmp-", suffix=".json")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(item, f, indent=2, ensure_ascii=False)
                f.write("\n")
            os.replace(tmp, path)
        except BaseException:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise


_first = {}  # path -> (mtime_ns, size, first line): job files are re-read only when they change


def first_line(path):
    try:
        st = path.stat()
        hit = _first.get(path)
        if hit and hit[0] == st.st_mtime_ns and hit[1] == st.st_size:
            return hit[2]
        with open(path, encoding="utf-8", errors="replace") as f:
            line = f.readline(400).strip()
        _first[path] = (st.st_mtime_ns, st.st_size, line)
        return line
    except OSError:
        return ""


# What the repo drawer offers. The two _lead/ names are the only files served
# from a repo's lead/ folder; everything else under /r/<repo>/ is factory/.
LEAD_DOCS = {"_lead/STATUS.md": ("state", "STATUS.md"), "_lead/judgment.md": ("judgment.md",)}
FACTORY_DOCS = ["backlog.md", "roadmap.md", "coverage.md"]


def repo_docs(repo):
    docs = [name for name, parts in LEAD_DOCS.items() if repo.lead.joinpath(*parts).is_file()]
    docs[1:1] = [d for d in FACTORY_DOCS if (repo.factory / d).is_file()]
    return docs


def jobs_of(repo, problems):
    """Every job of a repo with what the line view needs: job.json, the names
    of its markdown files, and each file's first line (the machine-read one)."""
    jobs = []
    root = repo.factory / "jobs"
    if not root.is_dir():
        return jobs
    for d in sorted(root.iterdir()):
        jf = d / "job.json"
        if not jf.is_file():
            continue
        try:
            with open(jf, encoding="utf-8") as f:
                job = json.load(f)
            if not isinstance(job, dict):
                raise ValueError("not a JSON object")
        except (OSError, ValueError) as e:
            problems.append(f"{repo.name}: jobs/{d.name}/job.json: {e}")
            continue
        job.setdefault("id", d.name)
        files = sorted(p.relative_to(d).as_posix() for p in d.rglob("*.md")
                       if "mockups" not in p.relative_to(d).parts)
        job["files"] = files
        job["firsts"] = {f: first_line(d / f) for f in files}
        job["mockups"] = (d / "mockups" / "index.html").is_file()
        jobs.append(job)
    return jobs


def unique_names(repos):
    seen = {}
    for r in repos:
        n = seen.get(r.name, 0) + 1
        seen[r.name] = n
        if n > 1:
            r.name = f"{r.name}-{n}"
    return {r.name: r for r in repos}


def allowed_actions(item):
    """The item's own action list, limited to what its kind permits."""
    kind_actions = KINDS[item["kind"]]
    listed = item.get("actions")
    if not isinstance(listed, list) or not listed:
        return kind_actions
    return [a for a in listed if a in kind_actions]


def snapshot(repos):
    items, problems, recent = [], [], []
    repo_jobs = {r.name: jobs_of(r, problems) for r in repos.values()}
    for r in repos.values():
        got, bad = r.items()
        problems += bad
        for it in got:
            it["repo"] = r.name
            it["actions"] = allowed_actions(it)
            items.append(it)
        done, bad = r.items(r.done)
        problems += bad
        for it in done:
            it["repo"] = r.name
            recent.append(it)

    def prio(it):
        p = it.get("priority")
        return p if isinstance(p, int) else 2

    open_items = sorted((i for i in items if not i.get("decision")),
                        key=lambda i: (prio(i), str(i.get("created", ""))))
    decided = sorted((i for i in items if i.get("decision")),
                     key=lambda i: str((i.get("decision") or {}).get("at", "")))
    recent.sort(key=lambda i: str(i.get("done") or ""), reverse=True)
    judged = [i for i in recent if isinstance(i.get("decision"), dict)
              and (i.get("recommendation") or {}).get("action")][:20]
    agreed = sum(1 for i in judged if i["decision"].get("agreed"))
    return {
        "now": now(),
        "repos": [{"name": r.name, "base": f"/r/{r.name}/", "status": r.status_line(),
                   "coverage": first_line(r.factory / "coverage.md"),
                   "docs": repo_docs(r),
                   "jobs": repo_jobs[r.name],
                   "open": sum(1 for i in open_items if i["repo"] == r.name)}
                  for r in repos.values()],
        "open": open_items,
        "decided": decided,
        "recent": recent[:15],
        "stats": {"judged": len(judged), "agreed": agreed, "corrected": len(judged) - agreed},
        "problems": problems,
    }


def decide(repos, body):
    repo = repos.get(body.get("repo"))
    if not repo:
        raise ValueError("unknown repo")
    path = repo.item_path(body.get("id"))
    try:
        item = repo._load(path)
    except FileNotFoundError:
        raise ValueError("this item is gone: the lead has already handled it")
    if item.get("done"):
        raise ValueError("the lead has already carried this item out")
    action = body.get("action")
    if action not in allowed_actions(item):
        raise ValueError(f"{action!r} is not an action of this item")
    note = body.get("note") or ""
    if not isinstance(note, str) or len(note) > MAX_NOTE:
        raise ValueError("note is missing or too long")
    note = note.strip()
    if action in NEEDS_NOTE and not note:
        raise ValueError(f"{action} needs a note")
    rec = item.get("recommendation") if isinstance(item.get("recommendation"), dict) else {}
    agreed = bool(rec.get("action")) and rec.get("action") == action \
        and note == str(rec.get("note") or "").strip()
    item["decision"] = {"action": action, "note": note, "agreed": agreed, "at": now()}
    repo.write(item)
    return item


def undo(repos, body):
    repo = repos.get(body.get("repo"))
    if not repo:
        raise ValueError("unknown repo")
    path = repo.item_path(body.get("id"))
    try:
        item = repo._load(path)
    except FileNotFoundError:
        raise ValueError("too late to undo: the lead has already handled this item")
    if item.get("done"):
        raise ValueError("too late to undo: the lead has already carried this out")
    item["decision"] = None
    repo.write(item)
    return item


class Handler(SimpleHTTPRequestHandler):
    repos = {}
    hosts = set()
    extensions_map = {**SimpleHTTPRequestHandler.extensions_map,
                      ".md": "text/markdown; charset=utf-8",
                      ".json": "application/json; charset=utf-8",
                      ".html": "text/html; charset=utf-8"}

    # ---- safety -----------------------------------------------------------

    def _local(self):
        """Only pages served by this server may talk to it. A wrong Host means
        DNS rebinding; a foreign Origin means another site in the browser."""
        if self.headers.get("Host", "").lower() not in self.hosts:
            return False
        origin = self.headers.get("Origin")
        return origin is None or origin.lower() in {f"http://{h}" for h in self.hosts}

    def _json(self, code, payload):
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def end_headers(self):  # job state changes by the second: never cache it
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        if getattr(self, "_agent_content", False):
            # Files under jobs/ are written by agents (mockups run inline JS).
            # Opened as pages they get an opaque origin, so a script in a
            # mockup can never post a decision to this server.
            self.send_header("Content-Security-Policy", "sandbox allow-scripts allow-popups allow-forms")
        super().end_headers()

    # ---- routing ----------------------------------------------------------

    def translate_path(self, path):
        """/r/<repo>/<path> → that repo's factory/<path>, plus the two lead
        documents in LEAD_DOCS. /fonts/ comes from next to this file. Anything
        else falls back to the first repo's factory/, so /jobs/<id>/mockups/
        keeps the URL the factory skill prints."""
        parts = [p for p in posixpath.normpath(unquote(urlsplit(path).path)).split("/")
                 if p and p not in (".", "..") and not re.search(r'[\\:]', p)]
        if len(parts) >= 2 and parts[0] == "r" and parts[1] in self.repos:
            repo, parts = self.repos[parts[1]], parts[2:]
            if "/".join(parts) in LEAD_DOCS:
                self._agent_content = False
                return str(repo.lead.joinpath(*LEAD_DOCS["/".join(parts)]))
            base = repo.factory
        elif parts and parts[0] == "fonts":
            base = HERE
        else:
            base = next(iter(self.repos.values())).factory
        self._agent_content = bool(parts) and parts[0] == "jobs"
        target = base.joinpath(*parts)
        try:  # a symlink must not lead out of factory/
            target.resolve().relative_to(base.resolve())
        except ValueError:
            return str(base / "__outside__")
        return str(target)

    def do_GET(self):
        if not self._local():
            return self.send_error(HTTPStatus.FORBIDDEN, "local requests only")
        route = urlsplit(self.path).path
        self._agent_content = False
        if route == "/":
            page = HERE / "dashboard.html"
            try:
                data = page.read_bytes()
            except OSError:
                return self.send_error(HTTPStatus.NOT_FOUND, "dashboard.html is missing next to dashboard.py")
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            return self.wfile.write(data)
        if route == "/api/state":
            return self._json(HTTPStatus.OK, snapshot(self.repos))
        return super().do_GET()

    def do_HEAD(self):
        if not self._local():
            return self.send_error(HTTPStatus.FORBIDDEN, "local requests only")
        return super().do_HEAD()

    def do_POST(self):
        route = urlsplit(self.path).path
        # The custom header forces a CORS preflight, which this server never
        # answers, so no other site can post a decision through your browser.
        if not self._local() or self.headers.get("X-Factory-Queue") != "1":
            return self._json(HTTPStatus.FORBIDDEN, {"error": "local requests only"})
        if route not in ("/api/decide", "/api/undo"):
            return self._json(HTTPStatus.NOT_FOUND, {"error": "no such endpoint"})
        try:
            length = int(self.headers.get("Content-Length") or 0)
            if not 0 < length <= MAX_BODY:
                raise ValueError("empty or oversized request")
            body = json.loads(self.rfile.read(length).decode("utf-8"))
            if not isinstance(body, dict):
                raise ValueError("expected a JSON object")
            item = (decide if route == "/api/decide" else undo)(self.repos, body)
        except (ValueError, UnicodeDecodeError) as e:
            return self._json(HTTPStatus.BAD_REQUEST, {"error": str(e)})
        except OSError as e:
            return self._json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": f"could not write the item: {e}"})
        d = item.get("decision")
        sys.stderr.write(f"{now()}  {body.get('repo')}  {item['id']}  "
                         f"{'undo' if not d else d['action']}\n")
        return self._json(HTTPStatus.OK, {"item": item})

    def log_message(self, fmt, *args):  # decisions are logged above; GET noise is not
        pass


def main():
    ap = argparse.ArgumentParser(description="Serve the factory dashboard and review queue on 127.0.0.1.")
    ap.add_argument("repos", nargs="*", help="repo roots (each has a factory/ folder). Default: the repo this file is in.")
    ap.add_argument("--port", type=int, default=8000)
    args = ap.parse_args()

    roots = args.repos or [HERE.parent]
    repos = []
    for root in roots:
        r = Repo(root)
        if not r.factory.is_dir():
            sys.exit(f"dashboard: {r.root} has no factory/ folder")
        repos.append(r)
    Handler.repos = unique_names(repos)
    Handler.hosts = {f"127.0.0.1:{args.port}", f"localhost:{args.port}"}

    try:
        server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    except OSError as e:
        sys.exit(f"dashboard: cannot listen on 127.0.0.1:{args.port} ({e}). Try --port.")
    print(f"Factory dashboard: http://127.0.0.1:{args.port}/")
    for r in Handler.repos.values():
        print(f"  {r.name}: {r.root}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print()


if __name__ == "__main__":
    main()
