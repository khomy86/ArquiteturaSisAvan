from fastapi import FastAPI, HTTPException, UploadFile, File, BackgroundTasks, Form, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import uvicorn
import os
from .queue import UploadQueue
import asyncio
from minio import Minio
import uuid
# Add SQLAlchemy imports
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from .models import Base, Video as VideoModel # Rename imported Video to avoid conflict

app = FastAPI(title="UALFlix Catalog Service")

# Database setup
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@db:5432/ualflix")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create tables if they don't exist (optional, consider using Alembic for migrations)
Base.metadata.create_all(bind=engine)

# Dependency to get DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Enable CORS - Commented out as Nginx handles this now
# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["*"],
#     allow_credentials=True,
#     allow_methods=["*"],
#     allow_headers=["*"],
# )

# Initialize services
queue = UploadQueue(os.getenv("REDIS_URL", "redis://redis:6379"))
minio_client = Minio(
    os.getenv("MINIO_ENDPOINT", "minio:9000"),
    access_key=os.getenv("MINIO_ACCESS_KEY", "minioadmin"),
    secret_key=os.getenv("MINIO_SECRET_KEY", "minioadmin"),
    secure=False
)

# Ensure bucket exists
try:
    minio_client.make_bucket("videos")
except Exception as e:
    print(f"Bucket already exists or error: {e}")

# Pydantic model for request/response (unchanged)
class Video(BaseModel):
    id: Optional[int] = None
    title: str
    description: str
    duration: int  # in seconds
    url: str
    status: Optional[str] = "pending"

    class Config:
        from_attributes = True # Enable ORM mode for mapping SQLAlchemy models (formerly orm_mode)

# New response model for upload endpoint
class UploadResponse(Video):
    upload_id: str

# Remove Temporary in-memory storage
# videos = []

@app.get("/")
async def root():
    return {"message": "Welcome to UALFlix Catalog Service"}

@app.get("/videos", response_model=List[Video])
async def get_videos(db: Session = Depends(get_db)):
    # Query database for videos
    db_videos = db.query(VideoModel).filter(VideoModel.is_deleted == False).all()
    return db_videos

@app.get("/videos/{video_id}", response_model=Video)
async def get_video(video_id: int, db: Session = Depends(get_db)):
    # Query database for specific video
    db_video = db.query(VideoModel).filter(VideoModel.id == video_id, VideoModel.is_deleted == False).first()
    if db_video is None:
        raise HTTPException(status_code=404, detail="Video not found")
    return db_video

@app.post("/videos/upload", response_model=UploadResponse) # Use the new response model
async def upload_video(
    background_tasks: BackgroundTasks,
    title: str = Form(...),
    description: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db) # Inject DB session
):
    # Create video entry in DB (without ID initially)
    new_video = VideoModel(
        title=title,
        description=description,
        duration=0,  # Will be updated after processing
        url="", # URL will be set after getting ID
        status="pending"
    )
    db.add(new_video)
    db.commit()
    db.refresh(new_video) # Refresh to get the auto-generated ID

    # Now use the generated ID
    video_id = new_video.id
    # video_url = f"http://streaming-service:8001/stream/{video_id}" # Use correct service name if different
    # Generate a relative URL path, assuming frontend uses the correct base URL
    video_url = f"/stream/{video_id}"

    # Update the URL in the database object
    new_video.url = video_url
    db.commit()

    # Add to upload queue
    upload_id = await queue.add_upload({
        "video_id": video_id,
        "title": title,
        "description": description,
        "file_name": file.filename
    })

    # Save file temporarily
    temp_path = f"/tmp/{file.filename}" # Ensure /tmp exists and is writable in container
    try:
        with open(temp_path, "wb") as f:
            content = await file.read()
            f.write(content)
    except Exception as e:
         # Clean up DB entry if temp file fails
        db.delete(new_video)
        db.commit()
        raise HTTPException(status_code=500, detail=f"Failed to save temporary file: {e}")


    # Process upload in background
    # Pass necessary info, including video_id
    background_tasks.add_task(process_upload, upload_id, temp_path, video_id)

    # Return combined data using the new response model
    response_data = Video.from_orm(new_video).dict()
    response_data["upload_id"] = upload_id
    return UploadResponse(**response_data)

@app.get("/uploads/{upload_id}/status")
async def get_upload_status(upload_id: str):
    status = await queue.get_upload_status(upload_id)
    if not status:
        raise HTTPException(status_code=404, detail="Upload not found")
    return status

async def process_upload(upload_id: str, file_path: str, video_id: int):
    # Need a database session for the background task
    db = SessionLocal()
    try:
        # Update status to processing
        await queue.update_status(upload_id, "processing")

        # Fetch the video record from DB
        video = db.query(VideoModel).filter(VideoModel.id == video_id).first()
        if not video:
            raise Exception(f"Video with ID {video_id} not found in database for processing.")

        # Upload to MinIO
        object_name = f"{video_id}.mp4" # Use the DB ID for the object name
        minio_client.fput_object("videos", object_name, file_path)

        # Update video status in DB
        video.status = "completed"
        # TODO: Extract actual video duration using ffprobe/ffmpeg if needed
        # video.duration = get_video_duration(file_path)
        db.commit()

        # Update queue status
        await queue.update_status(upload_id, "completed", {
            "video_id": video_id,
            "object_name": object_name
        })

        # Clean up temporary file
        if os.path.exists(file_path):
            os.remove(file_path)

    except Exception as e:
        print(f"Error processing upload {upload_id} for video {video_id}: {e}")
        # Update video status in DB
        video = db.query(VideoModel).filter(VideoModel.id == video_id).first()
        if video:
            video.status = "failed"
            db.commit()

        # Update queue status
        await queue.update_status(upload_id, "failed", {"error": str(e)})

        # Clean up temporary file
        if os.path.exists(file_path):
            os.remove(file_path)
    finally:
        db.close() # Ensure session is closed in background task

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000) 