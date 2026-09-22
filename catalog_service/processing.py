import logging
import os
import socket
import subprocess
import tempfile
import threading
import uuid

import redis
from minio.error import S3Error

from . import config, events, storage
from .database import SessionLocal
from .jobs import MAX_ATTEMPTS, UploadQueue
from .models import Video

logger = logging.getLogger(__name__)

# Well inside HEARTBEAT_TTL_SECONDS, so one slow Redis round trip doesn't make a
# healthy worker look dead.
HEARTBEAT_INTERVAL_SECONDS = 10


def probe_duration(path: str) -> float | None:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", path],
        capture_output=True, text=True, check=True,
    )
    try:
        return float(result.stdout.strip())
    except ValueError:
        return None


def extract_thumbnail(video_path: str, output_path: str, at_seconds: float) -> None:
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-ss", f"{at_seconds:.2f}", "-i", video_path,
         "-frames:v", "1", "-vf", "scale=320:-2", output_path],
        capture_output=True, text=True, check=True,
    )


def process_video(video_id: int) -> float | None:
    """Generate the thumbnail for an uploaded video and return its duration."""
    with tempfile.TemporaryDirectory() as workdir:
        video_path = os.path.join(workdir, "source")
        thumbnail_path = os.path.join(workdir, "thumbnail.jpg")

        storage.client.fget_object(
            bucket_name=config.VIDEO_BUCKET,
            object_name=storage.video_key(video_id),
            file_path=video_path,
        )
        duration = probe_duration(video_path)
        # One second in usually skips a black first frame; very short clips use their midpoint.
        extract_thumbnail(video_path, thumbnail_path, min(1.0, duration / 2) if duration else 0)
        storage.client.fput_object(
            bucket_name=config.THUMBNAIL_BUCKET,
            object_name=storage.thumbnail_key(video_id),
            file_path=thumbnail_path,
            content_type="image/jpeg",
        )
    return duration


def _update_video(video_id: int, **fields) -> bool:
    """Apply `fields` to the video. Returns False if it no longer exists."""
    with SessionLocal() as db:
        video = db.get(Video, video_id)
        if video is None:
            return False
        for name, value in fields.items():
            setattr(video, name, value)
        db.commit()
    events.publish(fields.get("status", "updated"), video_id)
    return True


def handle_job(queue: UploadQueue, job: dict) -> None:
    upload_id, video_id = job["id"], job["video_id"]
    if job["attempts"] > MAX_ATTEMPTS:
        logger.error("Giving up on video %s after %d attempts", video_id, MAX_ATTEMPTS)
        _update_video(video_id, status="failed")
        queue.set_status(upload_id, "failed", error="Processing kept failing and was abandoned.")
        return

    logger.info("Processing video %s (upload %s, attempt %d)", video_id, upload_id, job["attempts"])
    queue.set_status(upload_id, "processing")
    _update_video(video_id, status="processing")

    # Only problems with the upload itself fail the job here. Anything else
    # (storage or database unreachable) propagates, and the worker retries it.
    try:
        duration = process_video(video_id)
    except subprocess.CalledProcessError as exc:
        logger.error("ffmpeg failed for video %s: %s", video_id, exc.stderr.strip())
        _update_video(video_id, status="failed")
        queue.set_status(upload_id, "failed", error="The file could not be read as a video.")
        return
    except S3Error as exc:
        if exc.code != "NoSuchKey":
            raise
        logger.warning("Source file for video %s is missing", video_id)
        _update_video(video_id, status="failed")
        queue.set_status(upload_id, "failed", error="The uploaded file is missing.")
        return

    finished = _update_video(
        video_id,
        status="completed",
        duration=duration,
        thumbnail_url=storage.thumbnail_url(video_id),
    )
    if not finished:
        # Permanently deleted while we were working on it. The delete may have run
        # before the thumbnail was uploaded, so remove what we just created.
        logger.info("Video %s was deleted during processing; removing its files", video_id)
        storage.remove_video_files(video_id)
        return
    queue.set_status(upload_id, "completed")
    logger.info("Video %s is ready", video_id)


class UploadWorker:
    """Pulls upload jobs off the queue and processes them one at a time.

    Runs two background threads: one does the work, the other keeps this
    worker's heartbeat alive and requeues jobs from workers that have died. The
    heartbeat has its own thread so it keeps going while ffmpeg is busy with a
    long video; otherwise another instance would decide this one had died and
    process the same video again.
    """

    def __init__(self, queue: UploadQueue):
        self.queue = queue
        self.worker_id = f"{socket.gethostname()}-{uuid.uuid4().hex[:8]}"
        self._stopping = threading.Event()
        self._threads = [
            threading.Thread(target=self._work, name="upload-worker", daemon=True),
            threading.Thread(target=self._watch, name="upload-heartbeat", daemon=True),
        ]

    def start(self) -> None:
        for thread in self._threads:
            thread.start()

    def stop(self, timeout: float = 10) -> None:
        self._stopping.set()
        for thread in self._threads:
            thread.join(timeout)
        try:
            self.queue.retire(self.worker_id)
        except redis.RedisError:
            pass  # the heartbeat will expire on its own

    def _work(self) -> None:
        while not self._stopping.is_set():
            try:
                # Also beat here, so the worker is registered before its first claim.
                self.queue.heartbeat(self.worker_id)
                job = self.queue.claim(self.worker_id)
            except redis.RedisError as exc:
                logger.warning("Upload queue unavailable: %s", exc)
                self._stopping.wait(5)
                continue
            if job is not None:
                self._run(job)

    def _run(self, job: dict) -> None:
        try:
            handle_job(self.queue, job)
        except Exception:
            # Something outside the video itself went wrong (database or storage
            # down, for example), so give the job back to be retried.
            logger.exception("Could not process upload %s; returning it to the queue", job["id"])
            try:
                self.queue.release(self.worker_id, job["id"])
            except redis.RedisError:
                pass  # still in our processing list, so it's requeued once we're gone
            self._stopping.wait(5)
            return
        try:
            self.queue.ack(self.worker_id, job["id"])
        except redis.RedisError:
            logger.warning("Could not acknowledge upload %s; it may be processed again", job["id"])

    def _watch(self) -> None:
        while not self._stopping.is_set():
            try:
                self.queue.heartbeat(self.worker_id)
                for upload_id in self.queue.requeue_abandoned():
                    logger.warning("Requeued upload %s left behind by a stopped worker", upload_id)
            except redis.RedisError as exc:
                logger.warning("Upload queue unavailable: %s", exc)
            self._stopping.wait(HEARTBEAT_INTERVAL_SECONDS)
