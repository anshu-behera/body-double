"""Integration tests for FastAPI server endpoints and distraction detection logic."""
import time

import pytest
from fastapi.testclient import TestClient

import server.main as main
from server.main import Event, _is_distracted, DISTRACTION_SITES, app


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def project(client):
    resp = client.post("/projects", json={"name": "Test Project"})
    return resp.json()


# ---------------------------------------------------------------------------
# Projects
# ---------------------------------------------------------------------------

class TestProjects:
    def test_list_empty(self, client):
        resp = client.get("/projects")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_create(self, client):
        resp = client.post("/projects", json={"name": "My Project"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "My Project"
        assert data["whitelist"] == []
        assert "id" in data

    def test_list_after_create(self, client):
        client.post("/projects", json={"name": "Alpha"})
        client.post("/projects", json={"name": "Beta"})
        names = [p["name"] for p in client.get("/projects").json()]
        assert "Alpha" in names
        assert "Beta" in names

    def test_delete(self, client, project):
        resp = client.delete(f"/projects/{project['id']}")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}
        assert client.get("/projects").json() == []

    def test_update_whitelist(self, client, project):
        client.put(
            f"/projects/{project['id']}/whitelist",
            json={"domains": ["github.com", "docs.python.org"]},
        )
        projects = client.get("/projects").json()
        assert projects[0]["whitelist"] == ["github.com", "docs.python.org"]

    def test_clear_whitelist(self, client, project):
        client.put(f"/projects/{project['id']}/whitelist", json={"domains": ["github.com"]})
        client.put(f"/projects/{project['id']}/whitelist", json={"domains": []})
        assert client.get("/projects").json()[0]["whitelist"] == []


# ---------------------------------------------------------------------------
# Global whitelist
# ---------------------------------------------------------------------------

class TestGlobalWhitelist:
    def test_get_empty(self, client):
        resp = client.get("/config/whitelist")
        assert resp.status_code == 200
        assert resp.json() == {"domains": []}

    def test_update_and_get(self, client):
        client.put("/config/whitelist", json={"domains": ["google.com"]})
        assert client.get("/config/whitelist").json() == {"domains": ["google.com"]}

    def test_update_replaces(self, client):
        client.put("/config/whitelist", json={"domains": ["a.com"]})
        client.put("/config/whitelist", json={"domains": ["b.com"]})
        assert client.get("/config/whitelist").json() == {"domains": ["b.com"]}


# ---------------------------------------------------------------------------
# Session lifecycle
# ---------------------------------------------------------------------------

class TestSessionLifecycle:
    def test_inactive_by_default(self, client):
        resp = client.get("/session/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["active"] is False
        assert data["mode"] == "off"

    def test_start_focus_session(self, client, project):
        client.post("/session/start", json={"project_id": project["id"], "mode": "focus"})
        status = client.get("/session/status").json()
        assert status["active"] is True
        assert status["mode"] == "focus"

    def test_start_nudge_session(self, client, project):
        client.post("/session/start", json={"project_id": project["id"], "mode": "nudge"})
        assert client.get("/session/status").json()["mode"] == "nudge"

    def test_end_session(self, client, project):
        client.post("/session/start", json={"project_id": project["id"], "mode": "focus"})
        resp = client.post("/session/end")
        assert resp.status_code == 200
        assert client.get("/session/status").json()["active"] is False

    def test_start_clears_overrides(self, client, project):
        main._overrides.add("https://youtube.com")
        client.post("/session/start", json={"project_id": project["id"], "mode": "focus"})
        assert len(main._overrides) == 0

    def test_end_clears_overrides(self, client, project):
        client.post("/session/start", json={"project_id": project["id"], "mode": "focus"})
        main._overrides.add("https://youtube.com")
        client.post("/session/end")
        assert len(main._overrides) == 0

    def test_start_new_session_replaces_old(self, client, project):
        client.post("/session/start", json={"project_id": project["id"], "mode": "focus"})
        client.post("/session/start", json={"project_id": project["id"], "mode": "nudge"})
        assert client.get("/session/status").json()["mode"] == "nudge"


# ---------------------------------------------------------------------------
# Session check (focus mode URL gating)
# ---------------------------------------------------------------------------

class TestSessionCheck:
    def test_no_session_allows_all(self, client):
        assert client.get("/session/check?url=https://youtube.com").json()["allowed"] is True

    def test_nudge_mode_allows_all(self, client, project):
        client.post("/session/start", json={"project_id": project["id"], "mode": "nudge"})
        assert client.get("/session/check?url=https://youtube.com").json()["allowed"] is True

    def test_focus_mode_no_whitelist_blocks(self, client, project):
        client.post("/session/start", json={"project_id": project["id"], "mode": "focus"})
        assert client.get("/session/check?url=https://youtube.com").json()["allowed"] is False

    def test_focus_mode_url_matches_project_whitelist(self, client, project):
        client.put(f"/projects/{project['id']}/whitelist", json={"domains": ["github.com"]})
        client.post("/session/start", json={"project_id": project["id"], "mode": "focus"})
        assert client.get("/session/check?url=https://github.com/repo").json()["allowed"] is True

    def test_focus_mode_url_outside_project_whitelist(self, client, project):
        client.put(f"/projects/{project['id']}/whitelist", json={"domains": ["github.com"]})
        client.post("/session/start", json={"project_id": project["id"], "mode": "focus"})
        assert client.get("/session/check?url=https://youtube.com").json()["allowed"] is False

    def test_focus_mode_global_whitelist_allows(self, client, project):
        client.put("/config/whitelist", json={"domains": ["stackoverflow.com"]})
        client.post("/session/start", json={"project_id": project["id"], "mode": "focus"})
        assert client.get("/session/check?url=https://stackoverflow.com/q/123").json()["allowed"] is True

    def test_focus_mode_global_whitelist_takes_precedence(self, client, project):
        client.put("/config/whitelist", json={"domains": ["docs.python.org"]})
        client.put(f"/projects/{project['id']}/whitelist", json={"domains": ["github.com"]})
        client.post("/session/start", json={"project_id": project["id"], "mode": "focus"})
        # Both domains should be allowed
        assert client.get("/session/check?url=https://docs.python.org/3").json()["allowed"] is True
        assert client.get("/session/check?url=https://github.com/repo").json()["allowed"] is True

    def test_focus_mode_override_bypasses_block(self, client, project):
        client.post("/session/start", json={"project_id": project["id"], "mode": "focus"})
        url = "https://youtube.com/watch?v=abc"
        client.post(f"/session/override?url={url}")
        assert client.get(f"/session/check?url={url}").json()["allowed"] is True

    def test_check_response_includes_task_name_when_blocked(self, client, project):
        client.put(f"/projects/{project['id']}/whitelist", json={"domains": ["github.com"]})
        client.post("/session/start", json={"project_id": project["id"], "mode": "focus"})
        resp = client.get("/session/check?url=https://youtube.com").json()
        assert resp["allowed"] is False
        assert resp.get("task") == "Test Project"


# ---------------------------------------------------------------------------
# Session override
# ---------------------------------------------------------------------------

class TestSessionOverride:
    def test_override_returns_ok(self, client, project):
        client.post("/session/start", json={"project_id": project["id"], "mode": "focus"})
        resp = client.post("/session/override?url=https://youtube.com")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}

    def test_override_persists_in_set(self, client, project):
        client.post("/session/start", json={"project_id": project["id"], "mode": "focus"})
        url = "https://twitter.com"
        client.post(f"/session/override?url={url}")
        assert url in main._overrides

    def test_multiple_overrides_accumulate(self, client, project):
        client.post("/session/start", json={"project_id": project["id"], "mode": "focus"})
        client.post("/session/override?url=https://youtube.com")
        client.post("/session/override?url=https://twitter.com")
        assert len(main._overrides) == 2


# ---------------------------------------------------------------------------
# Event ingestion
# ---------------------------------------------------------------------------

class TestEventEndpoint:
    def _event_payload(self, url=None, app="chrome.exe", title="Tab"):
        return {"app": app, "title": title, "url": url, "timestamp": time.time()}

    def test_event_accepted_no_session(self, client):
        resp = client.post("/event", json=self._event_payload("https://youtube.com"))
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}

    def test_event_accepted_in_focus_mode(self, client, project):
        client.post("/session/start", json={"project_id": project["id"], "mode": "focus"})
        resp = client.post("/event", json=self._event_payload("https://youtube.com"))
        assert resp.status_code == 200

    def test_nudge_triggered_on_distraction(self, client, project, monkeypatch):
        calls = []
        monkeypatch.setattr(main, "nudge", lambda msg: calls.append(msg))
        client.post("/session/start", json={"project_id": project["id"], "mode": "nudge"})
        client.post("/event", json=self._event_payload("https://youtube.com"))
        assert len(calls) == 1
        assert "Test Project" in calls[0]

    def test_nudge_not_triggered_for_allowed_url(self, client, project, monkeypatch):
        calls = []
        monkeypatch.setattr(main, "nudge", lambda msg: calls.append(msg))
        client.put(f"/projects/{project['id']}/whitelist", json={"domains": ["github.com"]})
        client.post("/session/start", json={"project_id": project["id"], "mode": "nudge"})
        client.post("/event", json=self._event_payload("https://github.com/repo"))
        assert calls == []

    def test_nudge_not_triggered_without_url(self, client, project, monkeypatch):
        calls = []
        monkeypatch.setattr(main, "nudge", lambda msg: calls.append(msg))
        client.post("/session/start", json={"project_id": project["id"], "mode": "nudge"})
        client.post("/event", json=self._event_payload(url=None, app="code.exe", title="main.py"))
        assert calls == []

    def test_nudge_not_triggered_in_focus_mode(self, client, project, monkeypatch):
        calls = []
        monkeypatch.setattr(main, "nudge", lambda msg: calls.append(msg))
        client.post("/session/start", json={"project_id": project["id"], "mode": "focus"})
        client.post("/event", json=self._event_payload("https://youtube.com"))
        assert calls == []


# ---------------------------------------------------------------------------
# Block page
# ---------------------------------------------------------------------------

class TestBlockedPage:
    def test_renders_html(self, client):
        resp = client.get("/blocked?url=https://youtube.com")
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]

    def test_shows_task_name_during_session(self, client, project):
        client.post("/session/start", json={"project_id": project["id"], "mode": "focus"})
        resp = client.get("/blocked?url=https://youtube.com")
        assert "Test Project" in resp.text

    def test_fallback_when_no_session(self, client):
        resp = client.get("/blocked?url=https://youtube.com")
        assert "your task" in resp.text

    def test_xss_prevention_in_url(self, client):
        malicious = "https://evil.com/<script>alert(1)</script>"
        resp = client.get("/blocked", params={"url": malicious})
        assert "<script>alert(1)</script>" not in resp.text
        assert "&lt;script&gt;" in resp.text

    def test_xss_prevention_ampersand(self, client, project):
        client.post("/session/start", json={"project_id": project["id"], "mode": "focus"})
        resp = client.get("/blocked", params={"url": "https://evil.com?a=1&b=2"})
        assert "&amp;" in resp.text


# ---------------------------------------------------------------------------
# _is_distracted() unit tests
# ---------------------------------------------------------------------------

class TestIsDistracted:
    def _event(self, url):
        return Event(timestamp=time.time(), url=url)

    def test_no_url_returns_false(self):
        event = Event(timestamp=time.time(), url=None)
        assert _is_distracted(event, {"project_whitelist": []}) is False

    @pytest.mark.parametrize("site", DISTRACTION_SITES)
    def test_distraction_sites_flagged_without_whitelist(self, site):
        event = self._event(f"https://{site}/page")
        assert _is_distracted(event, {"project_whitelist": []}) is True

    def test_unknown_site_not_flagged_without_whitelist(self):
        event = self._event("https://arxiv.org/abs/123")
        assert _is_distracted(event, {"project_whitelist": []}) is False

    def test_whitelisted_domain_not_distracted(self, monkeypatch):
        monkeypatch.setattr(main.db, "get_global_whitelist", lambda: [])
        event = self._event("https://github.com/repo")
        assert _is_distracted(event, {"project_whitelist": ["github.com"]}) is False

    def test_url_outside_whitelist_is_distracted(self, monkeypatch):
        monkeypatch.setattr(main.db, "get_global_whitelist", lambda: [])
        event = self._event("https://youtube.com/watch")
        assert _is_distracted(event, {"project_whitelist": ["github.com"]}) is True

    def test_global_whitelist_allows(self, monkeypatch):
        monkeypatch.setattr(main.db, "get_global_whitelist", lambda: ["docs.python.org"])
        event = self._event("https://docs.python.org/3/library")
        assert _is_distracted(event, {"project_whitelist": []}) is False

    def test_combined_whitelist_project_and_global(self, monkeypatch):
        monkeypatch.setattr(main.db, "get_global_whitelist", lambda: ["google.com"])
        event = self._event("https://github.com/repo")
        assert _is_distracted(event, {"project_whitelist": ["github.com"]}) is False

    def test_distraction_site_blocked_when_whitelist_set(self, monkeypatch):
        # When whitelist is non-empty, DISTRACTION_SITES list is NOT used —
        # only whitelist membership matters.
        monkeypatch.setattr(main.db, "get_global_whitelist", lambda: [])
        event = self._event("https://youtube.com/watch")
        assert _is_distracted(event, {"project_whitelist": ["github.com"]}) is True

    def test_partial_domain_match(self, monkeypatch):
        monkeypatch.setattr(main.db, "get_global_whitelist", lambda: [])
        event = self._event("https://subdomain.github.com/page")
        assert _is_distracted(event, {"project_whitelist": ["github.com"]}) is False
