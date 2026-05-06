import os
import sys
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

import storage.db as db
from nudger.notifier import nudge

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

db.init_db()

TEMPLATES_DIR = Path(__file__).parent / "templates"

# Per-session overrides — cleared on session start/end
_overrides: set = set()

DISTRACTION_SITES = ["youtube.com", "twitter.com", "reddit.com", "instagram.com", "tiktok.com"]


def _matches_entry(entry: str, url: str) -> bool:
    """Domain entries (no ://) match any URL containing that string.
    Page entries (with ://) match URLs that start with the stored prefix."""
    if "://" in entry:
        return url.startswith(entry)
    return entry in url


class Event(BaseModel):
    app: Optional[str] = None
    title: Optional[str] = None
    url: Optional[str] = None
    timestamp: float


class ProjectCreate(BaseModel):
    name: str


class WhitelistUpdate(BaseModel):
    domains: List[str]


class SessionStart(BaseModel):
    project_id: int
    mode: str  # "focus" | "nudge"


@app.get("/")
def get_ui():
    return FileResponse(str(TEMPLATES_DIR / "index.html"))


@app.get("/projects")
def list_projects():
    return db.get_projects()


@app.post("/projects")
def create_project(body: ProjectCreate):
    return db.create_project(body.name)


@app.delete("/projects/{project_id}")
def delete_project(project_id: int):
    db.delete_project(project_id)
    return {"status": "ok"}


@app.put("/projects/{project_id}/whitelist")
def update_project_whitelist(project_id: int, body: WhitelistUpdate):
    db.update_project_whitelist(project_id, body.domains)
    return {"status": "ok"}


@app.get("/config/whitelist")
def get_global_whitelist():
    return {"domains": db.get_global_whitelist()}


@app.put("/config/whitelist")
def update_global_whitelist(body: WhitelistUpdate):
    db.update_global_whitelist(body.domains)
    return {"status": "ok"}


@app.post("/session/start")
def session_start(body: SessionStart):
    global _overrides
    _overrides = set()
    db.start_session(body.project_id, body.mode)
    return {"status": "ok"}


@app.post("/session/end")
def session_end():
    global _overrides
    _overrides = set()
    db.end_session()
    return {"status": "ok"}


@app.get("/session/status")
def session_status():
    session = db.get_active_session()
    if not session:
        return {"active": False, "mode": "off"}
    return {"active": True, **session}


@app.get("/session/check")
def session_check(url: str):
    session = db.get_active_session()
    if not session or session["mode"] != "focus":
        return {"allowed": True}
    if url in _overrides:
        return {"allowed": True}

    combined = db.get_global_whitelist() + session.get("project_whitelist", [])
    if not combined:
        return {"allowed": False}

    return {"allowed": any(_matches_entry(e, url) for e in combined), "task": session.get("project_name")}


@app.post("/session/override")
def session_override(url: str):
    _overrides.add(url)
    return {"status": "ok"}


@app.get("/blocked", response_class=HTMLResponse)
def blocked_page(url: str = ""):
    session = db.get_active_session()
    task = session["project_name"] if session else "your task"
    safe_task = task.replace("&", "&amp;").replace("<", "&lt;").replace('"', "&quot;")
    safe_url = url.replace("&", "&amp;").replace("<", "&lt;").replace('"', "&quot;")
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="target-url" content="{safe_url}">
  <title>Stay Focused</title>
  <style>
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #0a0a0a; color: #e5e5e5; display: flex; align-items: center; justify-content: center; height: 100vh; flex-direction: column; gap: 16px; }}
    h1 {{ font-size: 2.2rem; font-weight: 700; letter-spacing: -0.03em; }}
    p {{ color: #6b7280; font-size: 0.95rem; }}
    p strong {{ color: #9ca3af; }}
    .actions {{ display: flex; gap: 10px; margin-top: 8px; }}
    a {{ padding: 8px 16px; border-radius: 7px; font-size: 0.875rem; text-decoration: none; border: 1px solid #2a2a2a; color: #9ca3af; background: #141414; cursor: pointer; }}
    a:hover {{ border-color: #444; color: #e5e5e5; }}
    .through {{ color: #ef4444 !important; border-color: #3a1a1a !important; background: #1a0a0a !important; }}
    .through:hover {{ background: #2a0f0f !important; }}
  </style>
</head>
<body>
  <h1>Stay on task.</h1>
  <p>You're focused on: <strong>{safe_task}</strong></p>
  <div class="actions">
    <a href="http://localhost:8000">← Dashboard</a>
    <a class="through" onclick="allowThrough()">Let me through anyway</a>
  </div>
  <script>
    async function allowThrough() {{
      const url = document.querySelector('meta[name="target-url"]').content;
      await fetch('http://localhost:8000/session/override?url=' + encodeURIComponent(url), {{ method: 'POST' }});
      window.location.href = url;
    }}
  </script>
</body>
</html>"""


@app.post("/event")
def receive_event(event: Event):
    db.save_event(event)

    session = db.get_active_session()
    if not session or session["mode"] != "nudge":
        return {"status": "ok"}

    if _is_distracted(event, session):
        nudge(f"Drifting from: {session['project_name']}")

    return {"status": "ok"}


def _is_distracted(event: Event, session: dict) -> bool:
    if not event.url:
        return False
    combined = db.get_global_whitelist() + session.get("project_whitelist", [])
    if combined:
        return not any(_matches_entry(e, event.url) for e in combined)
    return any(site in event.url for site in DISTRACTION_SITES)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server.main:app", host="127.0.0.1", port=8000, reload=True)
