"""Unit tests for the storage/db.py layer using an isolated SQLite database."""
import time

import storage.db as db
from server.main import Event


class TestProjects:
    def test_empty_on_fresh_db(self):
        assert db.get_projects() == []

    def test_create_returns_project(self):
        p = db.create_project("Work")
        assert p["name"] == "Work"
        assert p["whitelist"] == []
        assert "id" in p

    def test_list_created_projects(self):
        db.create_project("Alpha")
        db.create_project("Beta")
        names = [p["name"] for p in db.get_projects()]
        assert "Alpha" in names
        assert "Beta" in names

    def test_delete_project(self):
        p = db.create_project("Temp")
        db.delete_project(p["id"])
        assert db.get_projects() == []

    def test_update_whitelist(self):
        p = db.create_project("Dev")
        db.update_project_whitelist(p["id"], ["github.com", "docs.python.org"])
        assert db.get_projects()[0]["whitelist"] == ["github.com", "docs.python.org"]

    def test_update_whitelist_to_empty(self):
        p = db.create_project("Dev")
        db.update_project_whitelist(p["id"], ["github.com"])
        db.update_project_whitelist(p["id"], [])
        assert db.get_projects()[0]["whitelist"] == []

    def test_delete_nonexistent_project_does_not_raise(self):
        db.delete_project(999)


class TestGlobalWhitelist:
    def test_defaults_to_empty(self):
        assert db.get_global_whitelist() == []

    def test_set_and_get(self):
        db.update_global_whitelist(["google.com", "stackoverflow.com"])
        assert db.get_global_whitelist() == ["google.com", "stackoverflow.com"]

    def test_update_replaces_previous(self):
        db.update_global_whitelist(["old.com"])
        db.update_global_whitelist(["new.com"])
        assert db.get_global_whitelist() == ["new.com"]

    def test_set_empty(self):
        db.update_global_whitelist(["a.com"])
        db.update_global_whitelist([])
        assert db.get_global_whitelist() == []


class TestSessions:
    def setup_method(self):
        self.project = db.create_project("TestProject")

    def test_no_active_session_initially(self):
        assert db.get_active_session() is None

    def test_start_session_makes_it_active(self):
        db.start_session(self.project["id"], "focus")
        session = db.get_active_session()
        assert session is not None
        assert session["mode"] == "focus"
        assert session["project_name"] == "TestProject"

    def test_end_session_deactivates(self):
        db.start_session(self.project["id"], "nudge")
        db.end_session()
        assert db.get_active_session() is None

    def test_starting_new_session_ends_previous(self):
        db.start_session(self.project["id"], "focus")
        db.start_session(self.project["id"], "nudge")
        assert db.get_active_session()["mode"] == "nudge"

    def test_session_carries_project_whitelist(self):
        db.update_project_whitelist(self.project["id"], ["example.com"])
        db.start_session(self.project["id"], "focus")
        session = db.get_active_session()
        assert "example.com" in session["project_whitelist"]

    def test_end_session_when_none_active_does_not_raise(self):
        db.end_session()

    def test_session_started_at_is_recent(self):
        before = time.time()
        db.start_session(self.project["id"], "focus")
        after = time.time()
        session = db.get_active_session()
        assert before <= session["started_at"] <= after

    def test_session_has_project_id(self):
        db.start_session(self.project["id"], "focus")
        session = db.get_active_session()
        assert session["project_id"] == self.project["id"]

    def test_nudge_mode_stored_correctly(self):
        db.start_session(self.project["id"], "nudge")
        assert db.get_active_session()["mode"] == "nudge"


class TestEvents:
    def test_save_event_without_session(self):
        event = Event(timestamp=time.time(), app="chrome.exe", title="Test", url="https://example.com")
        db.save_event(event)  # Should not raise

    def test_save_event_during_session(self):
        p = db.create_project("Testing")
        db.start_session(p["id"], "nudge")
        event = Event(timestamp=time.time(), app="code.exe", title="main.py", url=None)
        db.save_event(event)  # Should not raise

    def test_save_event_without_url(self):
        event = Event(timestamp=time.time(), app="notepad.exe", title="Untitled", url=None)
        db.save_event(event)  # Should not raise

    def test_save_event_without_app(self):
        event = Event(timestamp=time.time(), app=None, title=None, url="https://github.com")
        db.save_event(event)  # Should not raise
