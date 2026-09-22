from catalog_service import processing
from catalog_service.jobs import upload_queue
from catalog_service.models import Video


def test_finished_job_marks_video_ready(
    monkeypatch, make_video, fake_queue, fake_storage, db_session, published_events
):
    video = make_video(status="pending")
    upload_id = upload_queue.enqueue(video.id)
    monkeypatch.setattr(processing, "process_video", lambda _video_id: 12.5)

    processing.handle_job(upload_queue, fake_queue[upload_id])

    db_session.expire_all()
    stored = db_session.get(Video, video.id)
    assert (stored.status, stored.duration) == ("completed", 12.5)
    assert stored.thumbnail_url == f"/thumbnails/{video.id}.jpg"
    assert fake_queue[upload_id]["status"] == "completed"
    assert published_events == [("processing", video.id), ("completed", video.id)]
    assert fake_storage["removed"] == []


def test_video_deleted_during_processing_is_cleaned_up(
    monkeypatch, make_video, fake_queue, fake_storage, db_session
):
    video = make_video(status="pending")
    upload_id = upload_queue.enqueue(video.id)

    def delete_while_processing(video_id):
        # Simulates an admin permanently deleting the video mid-job, after
        # which the worker uploads a thumbnail nobody will ever clean up.
        db_session.delete(db_session.get(Video, video_id))
        db_session.commit()
        return 3.0

    monkeypatch.setattr(processing, "process_video", delete_while_processing)

    processing.handle_job(upload_queue, fake_queue[upload_id])

    assert fake_storage["removed"] == [video.id]
