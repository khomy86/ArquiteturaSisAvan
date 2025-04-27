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
import subprocess # Add subprocess import at the top

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

# Ensure buckets exist and set public read policy for thumbnails
try:
    if not minio_client.bucket_exists("videos"):
        minio_client.make_bucket("videos")
    if not minio_client.bucket_exists("thumbnails"):
        minio_client.make_bucket("thumbnails")

    # Set public read policy for thumbnails bucket
    policy = '{\"Version\":\"2012-10-17\",\"Statement\":[{\"Effect\":\"Allow\",\"Principal\":{\"AWS\":[\"*\"]},\"Action\":[\"s3:GetObject\"],\"Resource\":[\"arn:aws:s3:::thumbnails/*\"]}]}'
    minio_client.set_bucket_policy("thumbnails", policy)
    print("Applied public read policy to 'thumbnails' bucket.")

except Exception as e:
    print(f"Error during MinIO bucket setup/policy application: {e}")

# Pydantic model for request/response (unchanged)
class Video(BaseModel):
    id: Optional[int] = None
    title: str
    description: str
    duration: int  # in seconds
    url: str
    status: Optional[str] = "pending"
    thumbnail_url: Optional[str] = None

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
    video = None # Define video outside try block for access in finally/except
    try:
        # Update status to processing
        await queue.update_status(upload_id, "processing")

        # Fetch the video record from DB
        video = db.query(VideoModel).filter(VideoModel.id == video_id).first()
        if not video:
            raise Exception(f"Video with ID {video_id} not found in database for processing.")

        # Upload original video to MinIO
        object_name = f"{video_id}.mp4" # Use the DB ID for the object name
        minio_client.fput_object("videos", object_name, file_path)
        print(f"Successfully uploaded video {object_name} to MinIO.") # Added log

        # --- Thumbnail Generation ---
        thumbnail_filename = f"thumbnail_{video_id}.jpg"
        thumbnail_path = f"/tmp/{thumbnail_filename}"
        thumbnail_object_name = f"{video_id}.jpg"
        thumbnail_url = f"/thumbnails/{thumbnail_object_name}" # Relative URL for frontend/nginx

        # Bucket creation/policy is now handled at startup, removed from here
        # try:
        # Ensure thumbnails bucket exists (optional, depends on setup)
        # if not minio_client.bucket_exists("thumbnails"):
        #      minio_client.make_bucket("thumbnails")
        # Consider setting public read policy if needed, handled by Nginx here
        # policy = '{\"Version\":\"2012-10-17\",\"Statement\":[{\"Effect\":\"Allow\",\"Principal\":{\"AWS\":[\"*\"]},\"Action\":[\"s3:GetObject\"],\"Resource\":[\"arn:aws:s3:::thumbnails/*\"]}]}'
        # minio_client.set_bucket_policy("thumbnails", policy)

        # Generate thumbnail using ffmpeg (extract frame at 1 second)
        ffmpeg_command = [
            "ffmpeg",
            "-i", file_path,      # Input video file
            "-ss", "00:00:01.000", # Seek to 1 second
            "-vframes", "1",      # Extract one frame
            "-vf", "scale=320:-1", # Scale width to 320px, maintain aspect ratio
            thumbnail_path         # Output thumbnail file
        ]
        print(f"Running ffmpeg command: {' '.join(ffmpeg_command)}") # Added log
        subprocess.run(ffmpeg_command, check=True, capture_output=True)
        print(f"Successfully generated thumbnail {thumbnail_path}") # Added log

        # Upload thumbnail to MinIO
        minio_client.fput_object("thumbnails", thumbnail_object_name, thumbnail_path)
        print(f"Successfully uploaded thumbnail {thumbnail_object_name} to MinIO.") # Added log

        # Update video record with thumbnail URL
        video.thumbnail_url = thumbnail_url
        print(f"Updating video record {video_id} with thumbnail URL: {thumbnail_url}") # Added log

        # --- End Thumbnail Generation ---


        # Update video status in DB (commit includes thumbnail_url update)
        video.status = "completed"
        # TODO: Extract actual video duration using ffprobe/ffmpeg if needed
        # video.duration = get_video_duration(file_path)
        db.commit()
        print(f"Video record {video_id} updated successfully (status=completed).") # Added log

        # Update queue status
        await queue.update_status(upload_id, "completed", {
            "video_id": video_id,
            "object_name": object_name,
            "thumbnail_url": video.thumbnail_url # Include thumbnail url in status
        })

    except Exception as e:
        print(f"Error processing upload {upload_id} for video {video_id}: {e}")
        # Update video status in DB if video object exists
        if db.is_active and video: # Check if session is active and video was fetched
             video.status = "failed"
             # Don't nullify thumbnail_url here, keep potential result from thumb step
             db.commit()

        # Update queue status
        await queue.update_status(upload_id, "failed", {"error": str(e)})

    finally:
        # Clean up temporary files
        if os.path.exists(file_path):
            os.remove(file_path)
            print(f"Removed temporary video file: {file_path}") # Added log
        if 'thumbnail_path' in locals() and os.path.exists(thumbnail_path):
             os.remove(thumbnail_path)
             print(f"Removed temporary thumbnail file: {thumbnail_path}") # Added log
        if db.is_active: # Close session only if it's active
            db.close()

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000) 