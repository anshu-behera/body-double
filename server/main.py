import os
import sys
import threading
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
from server import embeddings

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

db.init_db()

TEMPLATES_DIR = Path(__file__).parent / "templates"

# Per-session in-memory state
_overrides: set = set()
_session_embedding = None          # numpy array for the active project, or None
_url_relevance_cache: dict = {}    # url -> bool; cleared on session start/end

DISTRACTION_SITES = ["youtube.com", "twitter.com", "reddit.com", "instagram.com", "tiktok.com"]


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------

class Event(BaseModel):
    app: Optional[str] = None
    title: Optional[str] = None
    url: Optional[str] = None
    timestamp: float
    meta_description: Optional[str] = None
    headings: Optional[List[str]] = None
    body_snippet: Optional[str] = None


class ProjectCreate(BaseModel):
    name: str
    description: str = ""


class ProjectDescriptionUpdate(BaseModel):
    description: str


class WhitelistUpdate(BaseModel):
    domains: List[str]


class SessionStart(BaseModel):
    project_id: int
    mode: str  # "focus" | "nudge"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _matches_entry(entry: str, url: str) -> bool:
    """Domain entries (no ://) match any URL containing that string.
    Page entries (with ://) match URLs that start with the stored prefix."""
    if "://" in entry:
        return url.startswith(entry)
    return entry in url


def _build_page_content(event: Event) -> str:
    parts = [
        event.title or "",
        event.meta_description or "",
        " ".join(event.headings or []),
        event.body_snippet or "",
    ]
    return " ".join(p for p in parts if p).strip()


def _precompute_embedding(description: str) -> None:
    global _session_embedding
    try:
        _session_embedding = embeddings.project_embedding(description)
    except Exception:
        _session_embedding = None


def _is_distracted(event: Event, session: dict) -> bool:
    if not event.url:
        return False

    combined = db.get_global_whitelist() + session.get("project_whitelist", [])
    if any(_matches_entry(e, event.url) for e in combined):
        return False  # explicitly whitelisted — no further checks

    page_content = _build_page_content(event)

    # Semantic check — requires a project description and extracted page content
    if _session_embedding is not None and page_content:
        url = event.url
        if url not in _url_relevance_cache:
            try:
                _url_relevance_cache[url] = embeddings.is_relevant(_session_embedding, page_content)
            except Exception:
                _url_relevance_cache[url] = True  # fail-open
        return not _url_relevance_cache[url]

    # Fallback: rule-based list when no semantic context is available
    return any(site in event.url for site in DISTRACTION_SITES)


# ---------------------------------------------------------------------------
# Routes — UI
# ---------------------------------------------------------------------------

@app.get("/")
def get_ui():
    return FileResponse(str(TEMPLATES_DIR / "index.html"))


# ---------------------------------------------------------------------------
# Routes — Projects
# ---------------------------------------------------------------------------

@app.get("/projects")
def list_projects():
    return db.get_projects()


@app.post("/projects")
def create_project(body: ProjectCreate):
    return db.create_project(body.name, body.description)


@app.delete("/projects/{project_id}")
def delete_project(project_id: int):
    db.delete_project(project_id)
    return {"status": "ok"}


@app.put("/projects/{project_id}/whitelist")
def update_project_whitelist(project_id: int, body: WhitelistUpdate):
    db.update_project_whitelist(project_id, body.domains)
    return {"status": "ok"}


@app.put("/projects/{project_id}/description")
def update_project_description(project_id: int, body: ProjectDescriptionUpdate):
    db.update_project_description(project_id, body.description)
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Routes — Global config
# ---------------------------------------------------------------------------

@app.get("/config/whitelist")
def get_global_whitelist():
    return {"domains": db.get_global_whitelist()}


@app.put("/config/whitelist")
def update_global_whitelist(body: WhitelistUpdate):
    db.update_global_whitelist(body.domains)
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Routes — Session
# ---------------------------------------------------------------------------

@app.post("/session/start")
def session_start(body: SessionStart):
    global _overrides, _session_embedding, _url_relevance_cache
    _overrides = set()
    _url_relevance_cache = {}
    _session_embedding = None
    db.start_session(body.project_id, body.mode)

    session = db.get_active_session()
    description = session.get("project_description", "") if session else ""
    if description and embeddings.available():
        threading.Thread(
            target=_precompute_embedding,
            args=(description,),
            daemon=True,
        ).start()

    return {"status": "ok"}


@app.post("/session/end")
def session_end():
    global _overrides, _session_embedding, _url_relevance_cache
    _overrides = set()
    _url_relevance_cache = {}
    _session_embedding = None
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


# ---------------------------------------------------------------------------
# Routes — Events
# ---------------------------------------------------------------------------

@app.post("/event")
def receive_event(event: Event):
    db.save_event(event)

    session = db.get_active_session()
    if not session:
        return {"status": "ok"}

    if _is_distracted(event, session):
        nudge(f"Drifting from: {session['project_name']}")

    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Routes — Block page
# ---------------------------------------------------------------------------

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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server.main:app", host="127.0.0.1", port=8000, reload=True)
