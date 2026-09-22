import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI

from . import admin, auth, config, storage, videos
from .database import run_migrations
from .jobs import upload_queue
from .processing import UploadWorker

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("catalog_service")


def _retry(action, name: str, attempts: int = 30, delay: float = 2.0):
    """Run a startup step, retrying while the dependency it needs comes up."""
    for attempt in range(1, attempts + 1):
        try:
            return action()
        except Exception as exc:
            if attempt == attempts:
                raise
            logger.warning("%s not ready (%s); retrying in %.0fs", name, exc, delay)
            time.sleep(delay)


@asynccontextmanager
async def lifespan(app: FastAPI):
    if not config.JWT_SECRET:
        raise RuntimeError("JWT_SECRET must be set")

    _retry(lambda: run_migrations(after=auth.ensure_admin_user), "PostgreSQL")
    _retry(storage.ensure_buckets, "MinIO")

    worker = UploadWorker(upload_queue)
    worker.start()
    yield
    worker.stop()


app = FastAPI(title="UALFlix Catalog Service", root_path=config.ROOT_PATH, lifespan=lifespan)
app.include_router(auth.router)
app.include_router(videos.router)
app.include_router(admin.router)


@app.get("/health", include_in_schema=False)
def health():
    return {"status": "ok"}
