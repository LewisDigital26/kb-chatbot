"""
server.py - runs the demo salon website, the chatbot API and the admin page.

Public:
  GET  /            the demo website (static/index.html)
  GET  /widget.js   the chat widget, which any site can add with one <script> tag
  POST /api/chat    {"question": "..."}  ->  {"answered": bool, "answer": "...", "sources": [...]}

Admin (needs the ADMIN_PASSWORD from .env, sent in an X-Admin-Password header):
  GET    /admin                    the admin page
  GET    /api/admin/docs           list documents
  POST   /api/admin/docs           add or replace a document {"name": "...", "content": "..."}
  DELETE /api/admin/docs/<name>    remove a document
  GET    /api/admin/stats          question stats and the questions it couldn't answer

Uses Python's built-in web server, so there is nothing extra to install.
"""
import hmac
import json
import os
import re
import threading
import time
import webbrowser
from collections import defaultdict, deque
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote

from dotenv import load_dotenv

import ingest
from answer import Assistant
from search import KnowledgeBase

load_dotenv()
PORT = 8000
HERE = Path(__file__).parent
STATIC, DOCS, DATA = HERE / "static", HERE / "docs", HERE / "data"
LOG_FILE = DATA / "questions.jsonl"
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "").strip()

MAX_QUESTION_LENGTH = 500
MAX_DOC_SIZE = 100_000  # characters
RATE_LIMIT = 20  # questions per minute per visitor, so nobody can run up the AI bill
SAFE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 _.-]{0,60}\.(md|txt)$")

assistant = Assistant()
kb_lock = threading.Lock()  # stops a question being answered mid-rebuild
recent = defaultdict(deque)
admin_failures = defaultdict(deque)

FILES = {
    "/": ("index.html", "text/html"),
    "/widget.js": ("widget.js", "application/javascript"),
    "/admin": ("admin.html", "text/html"),
}


def log_question(question: str, answered: bool) -> None:
    DATA.mkdir(exist_ok=True)
    entry = {"time": datetime.now().isoformat(timespec="seconds"), "question": question, "answered": answered}
    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


def rebuild_knowledge_base() -> int:
    count = ingest.main()
    with kb_lock:
        assistant.kb = KnowledgeBase()
    return count


class Handler(BaseHTTPRequestHandler):
    # ---------- helpers ----------
    def send_json(self, status: int, data: dict) -> None:
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def read_json(self) -> dict:
        length = int(self.headers.get("Content-Length", 0))
        if length > MAX_DOC_SIZE * 4:
            raise ValueError("too large")
        return json.loads(self.rfile.read(length))

    def is_admin(self) -> bool:
        """Check the admin password. Locks out an address after 5 wrong tries in 10 minutes."""
        ip, now = self.client_address[0], time.time()
        fails = admin_failures[ip]
        while fails and now - fails[0] > 600:
            fails.popleft()
        if not ADMIN_PASSWORD or len(fails) >= 5:
            self.send_json(403, {"error": "Admin is locked. Try again in 10 minutes."
                                 if ADMIN_PASSWORD else "Set ADMIN_PASSWORD in .env first."})
            return False
        given = self.headers.get("X-Admin-Password", "")
        if hmac.compare_digest(given.encode(), ADMIN_PASSWORD.encode()):  # timing-safe comparison
            return True
        fails.append(now)
        self.send_json(401, {"error": "Wrong password."})
        return False

    def log_message(self, *args):  # keep the window tidy
        pass

    # ---------- GET ----------
    def do_GET(self):
        if self.path in FILES:
            name, kind = FILES[self.path]
            body = (STATIC / name).read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", f"{kind}; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif self.path == "/api/admin/docs":
            if self.is_admin():
                docs = [{"name": p.name, "size": p.stat().st_size,
                         "updated": datetime.fromtimestamp(p.stat().st_mtime).strftime("%d %b %Y %H:%M")}
                        for p in sorted(DOCS.iterdir()) if p.suffix in (".md", ".txt")]
                self.send_json(200, {"docs": docs, "chunks": len(assistant.kb.chunks)})
        elif self.path.startswith("/api/admin/docs/"):
            if self.is_admin():
                path = self.doc_path(self.path)
                if path and path.exists():
                    self.send_json(200, {"name": path.name, "content": path.read_text(encoding="utf-8")})
                else:
                    self.send_json(404, {"error": "No such document."})
        elif self.path == "/api/admin/stats":
            if self.is_admin():
                entries = []
                if LOG_FILE.exists():
                    entries = [json.loads(line) for line in LOG_FILE.read_text(encoding="utf-8").splitlines() if line]
                unanswered = [e for e in entries if not e["answered"]]
                self.send_json(200, {"total": len(entries), "answered": len(entries) - len(unanswered),
                                     "unanswered": list(reversed(unanswered))[:50]})
        else:
            self.send_error(404)

    def doc_path(self, url_path: str):
        name = unquote(url_path.rsplit("/", 1)[-1])
        return DOCS / name if SAFE_NAME.match(name) else None  # blocks tricks like "../.env"

    # ---------- POST ----------
    def do_POST(self):
        if self.path == "/api/chat":
            self.handle_chat()
        elif self.path == "/api/admin/docs":
            if self.is_admin():
                self.handle_upload()
        elif self.path == "/api/admin/login":
            if self.is_admin():
                self.send_json(200, {"ok": True})
        else:
            self.send_error(404)

    def handle_chat(self):
        now, times = time.time(), recent[self.client_address[0]]
        while times and now - times[0] > 60:
            times.popleft()
        if len(times) >= RATE_LIMIT:
            self.send_json(429, {"error": "Too many questions, please wait a minute."})
            return
        times.append(now)

        try:
            question = str(self.read_json()["question"]).strip()
        except (ValueError, KeyError, TypeError):
            self.send_json(400, {"error": "Send JSON like {\"question\": \"...\"}"})
            return
        if not question or len(question) > MAX_QUESTION_LENGTH:
            self.send_json(400, {"error": f"Please ask a question under {MAX_QUESTION_LENGTH} characters."})
            return

        try:
            with kb_lock:
                result = assistant.ask(question)
        except Exception as e:  # never show a crash to a customer
            print(f"Error answering {question!r}: {e}")
            self.send_json(503, {"error": "Sorry, I'm having trouble right now. Please try again in a moment."})
            return
        log_question(question, result["answered"])
        print(f"Q: {question}\n   -> {'answered' if result['answered'] else 'handed to a person'}")
        self.send_json(200, result)

    def handle_upload(self):
        try:
            data = self.read_json()
            name, content = str(data["name"]).strip(), str(data["content"])
        except (ValueError, KeyError, TypeError):
            self.send_json(400, {"error": "Send a name and content."})
            return
        if not SAFE_NAME.match(name):
            self.send_json(400, {"error": "Use a simple file name ending in .md or .txt (letters, numbers, - and _)."})
            return
        if not content.strip() or len(content) > MAX_DOC_SIZE:
            self.send_json(400, {"error": f"The document must have text and be under {MAX_DOC_SIZE:,} characters."})
            return
        (DOCS / name).write_text(content.replace("\r\n", "\n"), encoding="utf-8")
        self.rebuild_and_reply(f"Saved {name}.")

    # ---------- DELETE ----------
    def do_DELETE(self):
        if not self.path.startswith("/api/admin/docs/"):
            self.send_error(404)
            return
        if not self.is_admin():
            return
        path = self.doc_path(self.path)
        if not path or not path.exists():
            self.send_json(404, {"error": "No such document."})
            return
        if len([p for p in DOCS.iterdir() if p.suffix in (".md", ".txt")]) <= 1:
            self.send_json(400, {"error": "Keep at least one document, or the chatbot has nothing to answer from."})
            return
        path.unlink()
        self.rebuild_and_reply(f"Removed {path.name}.")

    def rebuild_and_reply(self, message: str) -> None:
        try:
            count = rebuild_knowledge_base()
            print(f"Admin: {message} Knowledge base rebuilt ({count} chunks).")
            self.send_json(200, {"ok": True, "message": f"{message} The chatbot has relearned everything ({count} sections)."})
        except Exception as e:
            self.send_json(500, {"error": f"Saved, but rebuilding failed: {e}. Try again in a minute."})


if __name__ == "__main__":
    server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    url = f"http://localhost:{PORT}"
    print(f"Demo website: {url}    Admin page: {url}/admin    (press Ctrl + C to stop)")
    webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("Stopped.")
