import json
import uuid

import redis

from . import config

QUEUE_KEY = "uploads:queue"
PROCESSING_KEY = "uploads:processing:{}"  # jobs a given worker has claimed
WORKER_KEY = "uploads:worker:{}"  # heartbeat; expires if the worker dies
STATUS_KEY = "uploads:status:{}"
VIDEO_KEY = "uploads:video:{}"  # video id -> upload id, for cleanup on delete

# Finished jobs only need to stick around long enough for the client to see them.
FINISHED_TTL_SECONDS = 3600
HEARTBEAT_TTL_SECONDS = 30
# A job that has been picked up this many times without finishing is dropped,
# so a video that crashes the worker can't take it down over and over.
MAX_ATTEMPTS = 3


class UploadQueue:
    """Queue of uploaded videos waiting to be processed.

    Job IDs go into a Redis list that every catalog instance pulls from, and each
    job's status is kept under its own key so any instance can answer a status
    poll, whichever one received the upload or is processing it.

    Claiming a job moves it atomically into a list owned by that worker, where it
    stays until the worker acknowledges it. Workers keep a heartbeat key alive
    while running; if one dies, its heartbeat expires and the jobs left in its
    list are put back on the queue by whichever instance notices first.
    """

    def __init__(self, redis_url: str):
        self.redis = redis.Redis.from_url(redis_url, decode_responses=True)

    def enqueue(self, video_id: int) -> str:
        upload_id = str(uuid.uuid4())
        job = {"id": upload_id, "video_id": video_id, "status": "pending", "attempts": 0}
        with self.redis.pipeline() as pipe:
            pipe.set(STATUS_KEY.format(upload_id), json.dumps(job))
            pipe.set(VIDEO_KEY.format(video_id), upload_id)
            pipe.rpush(QUEUE_KEY, upload_id)
            pipe.execute()
        return upload_id

    def claim(self, worker_id: str, timeout: int = 2) -> dict | None:
        """Wait up to `timeout` seconds for a job and take ownership of it.

        Keep the timeout below the client's socket timeout (5s by default in
        redis-py), or an idle wait is reported as a connection error.
        """
        upload_id = self.redis.blmove(
            QUEUE_KEY, PROCESSING_KEY.format(worker_id), timeout, "LEFT", "RIGHT"
        )
        if upload_id is None:
            return None
        job = self.get(upload_id)
        if job is None:
            # The video was permanently deleted while its job was queued.
            self.ack(worker_id, upload_id)
            return None
        job["attempts"] = job.get("attempts", 0) + 1
        self._save(job)
        return job

    def ack(self, worker_id: str, upload_id: str) -> None:
        """Mark a claimed job as done with, successfully or not."""
        self.redis.lrem(PROCESSING_KEY.format(worker_id), 1, upload_id)

    def release(self, worker_id: str, upload_id: str) -> None:
        """Hand a claimed job back so it gets retried."""
        with self.redis.pipeline() as pipe:
            pipe.lrem(PROCESSING_KEY.format(worker_id), 1, upload_id)
            pipe.lpush(QUEUE_KEY, upload_id)
            pipe.execute()

    def heartbeat(self, worker_id: str) -> None:
        self.redis.set(WORKER_KEY.format(worker_id), 1, ex=HEARTBEAT_TTL_SECONDS)

    def retire(self, worker_id: str) -> None:
        """Called on shutdown, so anything left unfinished is picked up right away
        instead of after the heartbeat expires."""
        self.redis.delete(WORKER_KEY.format(worker_id))

    def requeue_abandoned(self) -> list[str]:
        """Put jobs held by workers with an expired heartbeat back on the queue."""
        requeued = []
        prefix = PROCESSING_KEY.format("")
        for key in self.redis.scan_iter(match=f"{prefix}*"):
            worker_id = key.removeprefix(prefix)
            if self.redis.exists(WORKER_KEY.format(worker_id)):
                continue
            # To the front of the queue, since these have already waited once.
            # LMOVE is atomic, so two instances doing this at once can't
            # requeue the same job twice.
            while (upload_id := self.redis.lmove(key, QUEUE_KEY, "RIGHT", "LEFT")) is not None:
                requeued.append(upload_id)
        return requeued

    def get(self, upload_id: str) -> dict | None:
        raw = self.redis.get(STATUS_KEY.format(upload_id))
        return json.loads(raw) if raw else None

    def set_status(self, upload_id: str, status: str, error: str | None = None) -> None:
        job = self.get(upload_id)
        if job is None:
            return
        job["status"] = status
        if error:
            job["error"] = error
        self._save(job)

    def forget_video(self, video_id: int) -> None:
        """Drop the upload status for a video that has been permanently deleted.

        If its job is still waiting in the queue, the worker will find no status
        for it and skip it.
        """
        upload_id = self.redis.get(VIDEO_KEY.format(video_id))
        keys = [VIDEO_KEY.format(video_id)]
        if upload_id:
            keys.append(STATUS_KEY.format(upload_id))
        self.redis.delete(*keys)

    def _save(self, job: dict) -> None:
        ttl = FINISHED_TTL_SECONDS if job["status"] in ("completed", "failed") else None
        with self.redis.pipeline() as pipe:
            pipe.set(STATUS_KEY.format(job["id"]), json.dumps(job), ex=ttl)
            pipe.set(VIDEO_KEY.format(job["video_id"]), job["id"], ex=ttl)
            pipe.execute()


upload_queue = UploadQueue(config.REDIS_URL)
