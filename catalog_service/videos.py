import logging
from collections.abc import AsyncIterable
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.sse import EventSourceResponse, ServerSentEvent
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import config, events, storage
from .database import get_db
from .jobs import upload_queue
from .models import Video
from .schemas import UploadAccepted, UploadStatus, VideoOut

logger = logging.getLogger(__name__)
router = APIRouter(tags=["videos"])

# Size of each multipart chunk when streaming an upload into MinIO.
UPLOAD_PART_SIZE = 10 * 1024 * 1024


@router.get("/videos", response_model=list[VideoOut])
def list_videos(db: Annotated[Session, Depends(get_db)]):
    """Videos that are ready to watch, newest first."""
    stmt = (
        select(Video)
        .where(Video.is_deleted.is_(False), Video.status == "completed")
        .order_by(Video.created_at.desc(), Video.id.desc())
    )
    return db.scalars(stmt).all()


@router.get("/videos/{video_id}", response_model=VideoOut)
def get_video(video_id: int, db: Annotated[Session, Depends(get_db)]):
    video = db.get(Video, video_id)
    if video is None or video.is_deleted:
        raise HTTPException(status_code=404, detail="Video not found")
    return video


@router.post("/videos/upload", response_model=UploadAccepted, status_code=status.HTTP_202_ACCEPTED)
def upload_video(
    db: Annotated[Session, Depends(get_db)],
    title: Annotated[str, Form(min_length=1, max_length=200)],
    file: Annotated[UploadFile, File()],
    description: Annotated[str, Form()] = "",
):
    if not (file.content_type or "").startswith("video/"):
        raise HTTPException(status_code=415, detail="Only video files can be uploaded")

    video = Video(title=title.strip(), description=description.strip())
    db.add(video)
    db.commit()

    try:
        storage.client.put_object(
            bucket_name=config.VIDEO_BUCKET,
            object_name=storage.video_key(video.id),
            data=file.file,
            length=-1,
            part_size=UPLOAD_PART_SIZE,
            content_type=file.content_type,
        )
        upload_id = upload_queue.enqueue(video.id)
    except Exception:
        logger.exception("Could not store upload for video %s", video.id)
        video.status = "failed"
        db.commit()
        raise HTTPException(status_code=502, detail="The upload could not be stored")

    return UploadAccepted(upload_id=upload_id, video=VideoOut.model_validate(video))


@router.get("/uploads/{upload_id}/status", response_model=UploadStatus)
def get_upload_status(upload_id: str):
    job = upload_queue.get(upload_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Upload not found")
    return job


@router.get("/events", response_class=EventSourceResponse)
async def catalog_events() -> AsyncIterable[ServerSentEvent]:
    """Server-sent events announcing catalog changes, so open pages can refresh.

    Each event's data is `{"action": ..., "video_id": ...}`.
    """
    async for event in events.subscribe():
        yield ServerSentEvent(data=event)
