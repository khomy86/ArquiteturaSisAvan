import os

os.environ.setdefault("JWT_SECRET", "test-secret-that-is-at-least-32-bytes")
os.environ.setdefault("ADMIN_USERNAME", "admin")
os.environ.setdefault("ADMIN_PASSWORD", "correct-horse")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from catalog_service import auth, events, processing, storage
from catalog_service.database import get_db
from catalog_service.jobs import upload_queue
from catalog_service.main import app
from catalog_service.models import Base, Video


@pytest.fixture
def session_factory(monkeypatch):
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, autoflush=False)
    with Session() as session:
        auth.ensure_admin_user(session)

    def override_get_db():
        with Session() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    monkeypatch.setattr(processing, "SessionLocal", Session)
    yield Session
    app.dependency_overrides.clear()


@pytest.fixture
def db_session(session_factory):
    with session_factory() as session:
        yield session


@pytest.fixture(autouse=True)
def published_events(monkeypatch):
    """Record catalog events instead of sending them to Redis."""
    published = []
    monkeypatch.setattr(events, "publish", lambda action, video_id: published.append((action, video_id)))
    return published


@pytest.fixture
def client(db_session):
    # Not used as a context manager, so the lifespan (Postgres, MinIO, worker) never runs.
    return TestClient(app)


@pytest.fixture
def token(client):
    response = client.post("/auth/login", data={"username": "admin", "password": "correct-horse"})
    return response.json()["access_token"]


@pytest.fixture
def auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def make_video(db_session):
    def make(**fields):
        video = Video(**{"title": "Clip", "status": "completed", **fields})
        db_session.add(video)
        db_session.commit()
        return video
    return make


@pytest.fixture
def fake_storage(monkeypatch):
    calls = {"put": [], "removed": []}
    monkeypatch.setattr(storage.client, "put_object", lambda **kw: calls["put"].append(kw))
    monkeypatch.setattr(storage, "remove_video_files", lambda video_id: calls["removed"].append(video_id))
    return calls


@pytest.fixture
def fake_queue(monkeypatch):
    jobs = {}

    def enqueue(video_id):
        upload_id = f"upload-{video_id}"
        jobs[upload_id] = {"id": upload_id, "video_id": video_id, "status": "pending", "attempts": 1}
        return upload_id

    def forget_video(video_id):
        for upload_id in [k for k, job in jobs.items() if job["video_id"] == video_id]:
            del jobs[upload_id]

    def set_status(upload_id, status, error=None):
        if upload_id in jobs:
            jobs[upload_id]["status"] = status

    monkeypatch.setattr(upload_queue, "enqueue", enqueue)
    monkeypatch.setattr(upload_queue, "get", jobs.get)
    monkeypatch.setattr(upload_queue, "forget_video", forget_video)
    monkeypatch.setattr(upload_queue, "set_status", set_status)
    return jobs
