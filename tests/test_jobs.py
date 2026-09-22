import fakeredis
import pytest

from catalog_service import jobs, processing
from catalog_service.jobs import MAX_ATTEMPTS, QUEUE_KEY, UploadQueue


@pytest.fixture
def queue():
    q = UploadQueue("redis://unused")
    q.redis = fakeredis.FakeRedis(decode_responses=True)
    return q


def processing_list(queue, worker_id):
    return queue.redis.lrange(jobs.PROCESSING_KEY.format(worker_id), 0, -1)


def test_claimed_job_stays_owned_until_acked(queue):
    upload_id = queue.enqueue(video_id=1)

    job = queue.claim("w1")
    assert job["id"] == upload_id
    assert job["attempts"] == 1
    assert queue.redis.llen(QUEUE_KEY) == 0
    assert processing_list(queue, "w1") == [upload_id]

    queue.ack("w1", upload_id)
    assert processing_list(queue, "w1") == []


def test_jobs_of_a_dead_worker_are_requeued(queue):
    upload_id = queue.enqueue(video_id=1)
    queue.heartbeat("w1")
    queue.claim("w1")

    # w1 dies: its heartbeat expires and nothing ever acks the job.
    queue.redis.delete(jobs.WORKER_KEY.format("w1"))
    assert queue.requeue_abandoned() == [upload_id]

    job = queue.claim("w2")
    assert job["id"] == upload_id
    assert job["attempts"] == 2
    assert processing_list(queue, "w1") == []


def test_jobs_of_a_live_worker_are_left_alone(queue):
    queue.enqueue(video_id=1)
    queue.heartbeat("w1")
    queue.claim("w1")

    assert queue.requeue_abandoned() == []
    assert queue.redis.llen(QUEUE_KEY) == 0


def test_job_for_deleted_video_is_skipped(queue):
    upload_id = queue.enqueue(video_id=1)
    queue.forget_video(1)

    assert queue.claim("w1") is None
    assert processing_list(queue, "w1") == []
    assert queue.get(upload_id) is None


def test_released_job_goes_back_to_the_front(queue):
    first = queue.enqueue(video_id=1)
    second = queue.enqueue(video_id=2)
    queue.claim("w1")

    queue.release("w1", first)
    assert queue.redis.lrange(QUEUE_KEY, 0, -1) == [first, second]
    assert processing_list(queue, "w1") == []


def test_worker_returns_job_when_infrastructure_fails(monkeypatch, queue):
    upload_id = queue.enqueue(video_id=1)
    worker = processing.UploadWorker(queue)
    job = queue.claim(worker.worker_id)

    def database_down(queue, job):
        raise ConnectionError("database unreachable")

    monkeypatch.setattr(processing, "handle_job", database_down)
    monkeypatch.setattr(worker._stopping, "wait", lambda timeout: None)
    worker._run(job)

    assert queue.redis.lrange(QUEUE_KEY, 0, -1) == [upload_id]
    assert processing_list(queue, worker.worker_id) == []


def test_worker_acks_finished_job(monkeypatch, queue):
    queue.enqueue(video_id=1)
    worker = processing.UploadWorker(queue)
    job = queue.claim(worker.worker_id)

    monkeypatch.setattr(processing, "handle_job", lambda queue, job: None)
    worker._run(job)

    assert queue.redis.llen(QUEUE_KEY) == 0
    assert processing_list(queue, worker.worker_id) == []


def test_job_is_abandoned_after_too_many_attempts(queue, make_video, db_session):
    video = make_video(status="processing")
    upload_id = queue.enqueue(video.id)
    for _ in range(MAX_ATTEMPTS + 1):
        job = queue.claim("w1")
        queue.release("w1", upload_id)

    processing.handle_job(queue, job)

    db_session.expire_all()
    assert db_session.get(type(video), video.id).status == "failed"
    assert queue.get(upload_id)["status"] == "failed"
