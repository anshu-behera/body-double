import pytest


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    """Redirect all DB operations to an isolated temp file per test."""
    import storage.db as db
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()


@pytest.fixture(autouse=True)
def reset_overrides():
    """Clear the in-memory overrides set before and after each test."""
    import server.main as main
    main._overrides = set()
    yield
    main._overrides = set()


@pytest.fixture(autouse=True)
def mock_nudge(monkeypatch):
    """Prevent real Windows toast notifications during tests."""
    import server.main as main
    monkeypatch.setattr(main, "nudge", lambda msg: None)


@pytest.fixture
def client():
    from fastapi.testclient import TestClient
    from server.main import app
    return TestClient(app)


@pytest.fixture
def project(client):
    resp = client.post("/projects", json={"name": "Test Project"})
    return resp.json()
