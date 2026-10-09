"""
server.py - Step 4: runs the demo salon website and the chatbot API.

  GET  /            the demo website (static/index.html)
  GET  /widget.js   the chat widget, which any site can add with one <script> tag
  POST /api/chat    {"question": "..."}  ->  {"answered": bool, "answer": "...", "sources": [...]}

Uses Python's built-in web server, so there is nothing extra to install.
Start it with run_website.bat, then open http://localhost:8000
"""
import json
import time
import webbrowser
from collections import defaultdict, deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from answer import Assistant

PORT = 8000
STATIC = Path(__file__).with_name("static")
MAX_QUESTION_LENGTH = 500
RATE_LIMIT = 20  # questions per minute per visitor, so nobody can run up the AI bill

assistant = Assistant()
recent = defaultdict(deque)  # visitor IP -> times of their recent questions

FILES = {"/": ("index.html", "text/html"), "/widget.js": ("widget.js", "application/javascript")}


class Handler(BaseHTTPRequestHandler):
    def send_json(self, status: int, data: dict) -> None:
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path not in FILES:
            self.send_error(404)
            return
        name, kind = FILES[self.path]
        body = (STATIC / name).read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", f"{kind}; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        if self.path != "/api/chat":
            self.send_error(404)
            return

        # Rate limit per visitor
        now, times = time.time(), recent[self.client_address[0]]
        while times and now - times[0] > 60:
            times.popleft()
        if len(times) >= RATE_LIMIT:
            self.send_json(429, {"error": "Too many questions, please wait a minute."})
            return
        times.append(now)

        try:
            length = int(self.headers.get("Content-Length", 0))
            question = str(json.loads(self.rfile.read(min(length, 10_000)))["question"]).strip()
        except (ValueError, KeyError, TypeError):
            self.send_json(400, {"error": "Send JSON like {\"question\": \"...\"}"})
            return
        if not question or len(question) > MAX_QUESTION_LENGTH:
            self.send_json(400, {"error": f"Please ask a question under {MAX_QUESTION_LENGTH} characters."})
            return

        try:
            result = assistant.ask(question)
        except Exception as e:  # never show a crash to a customer
            print(f"Error answering {question!r}: {e}")
            self.send_json(503, {"error": "Sorry, I'm having trouble right now. Please try again in a moment."})
            return
        print(f"Q: {question}\n   -> {'answered' if result['answered'] else 'handed to a person'}")
        self.send_json(200, result)

    def log_message(self, *args):  # keep the window tidy
        pass


if __name__ == "__main__":
    server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    url = f"http://localhost:{PORT}"
    print(f"Demo website running at {url}  (press Ctrl + C to stop)")
    webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("Stopped.")
