from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class VideoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    description: str
    duration: float | None
    url: str
    status: str
    thumbnail_url: str | None
    is_deleted: bool
    created_at: datetime
    updated_at: datetime | None


class VideoUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None


class UploadAccepted(BaseModel):
    upload_id: str
    video: VideoOut


class UploadStatus(BaseModel):
    id: str
    video_id: int
    status: str
    attempts: int = 0
    error: str | None = None


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class AdminOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    username: str
