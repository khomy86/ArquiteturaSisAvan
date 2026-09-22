import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response
from minio.error import S3Error
from redis import RedisError
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import events, storage
from .auth import require_admin
from .database import get_db
from .jobs import upload_queue
from .models import Video
from .schemas import VideoOut, VideoUpdate

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin)])


def _get_video(db: Session, video_id: int) -> Video:
    video = db.get(Video, video_id)
    if video is None:
        raise HTTPException(status_code=404, detail="Video not found")
    return video


@router.get("/videos", response_model=list[VideoOut])
def list_all_videos(db: Annotated[Session, Depends(get_db)]):
    """Every video regardless of status, including soft-deleted ones."""
    return db.scalars(select(Video).order_by(Video.id.desc())).all()


@router.patch("/videos/{video_id}", response_model=VideoOut)
def update_video(video_id: int, changes: VideoUpdate, db: Annotated[Session, Depends(get_db)]):
    video = _get_video(db, video_id)
    for name, value in changes.model_dump(exclude_unset=True, exclude_none=True).items():
        setattr(video, name, value.strip())
    db.commit()
    db.refresh(video)
    events.publish("updated", video.id)
    return video


@router.delete("/videos/{video_id}", status_code=204)
def delete_video(video_id: int, db: Annotated[Session, Depends(get_db)], permanent: bool = False):
    """Hide a video, or with `permanent=true` remove it and its files for good."""
    video = _get_video(db, video_id)
    if permanent:
        try:
            storage.remove_video_files(video.id)
        except S3Error:
            logger.exception("Could not remove files for video %s", video.id)
            raise HTTPException(status_code=502, detail="Could not remove the video files from storage")
        try:
            upload_queue.forget_video(video.id)
        except RedisError:
            logger.warning("Could not clear upload status for video %s; it will expire on its own", video.id)
        db.delete(video)
    else:
        video.is_deleted = True
    db.commit()
    events.publish("removed" if permanent else "deleted", video_id)
    return Response(status_code=204)


@router.post("/videos/{video_id}/restore", response_model=VideoOut)
def restore_video(video_id: int, db: Annotated[Session, Depends(get_db)]):
    video = _get_video(db, video_id)
    video.is_deleted = False
    db.commit()
    db.refresh(video)
    events.publish("restored", video.id)
    return video
