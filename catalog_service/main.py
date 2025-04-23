from fastapi import FastAPI, HTTPException, UploadFile, File, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import uvicorn
import os
from queue import UploadQueue
import asyncio
from minio import Minio
import uuid

app = FastAPI(title="UALFlix Catalog Service")

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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

class Video(BaseModel):
    id: Optional[int] = None
    title: str
    description: str
    duration: int  # in seconds
    url: str
    status: Optional[str] = "pending"

# Temporary in-memory storage (will be replaced with database)
videos = []

@app.get("/")
async def root():
    return {"message": "Welcome to UALFlix Catalog Service"}

@app.get("/videos", response_model=List[Video])
async def get_videos():
    return videos

@app.get("/videos/{video_id}", response_model=Video)
async def get_video(video_id: int):
    for video in videos:
        if video.id == video_id:
            return video
    raise HTTPException(status_code=404, detail="Video not found")

@app.post("/videos/upload")
async def upload_video(
    background_tasks: BackgroundTasks,
    title: str,
    description: str,
    file: UploadFile = File(...)
):
    # Generate unique ID for the video
    video_id = len(videos) + 1
    video_url = f"http://streaming-service:8001/stream/{video_id}"
    
    # Create video entry
    video = Video(
        id=video_id,
        title=title,
        description=description,
        duration=0,  # Will be updated after processing
        url=video_url,
        status="pending"
    )
    videos.append(video)
    
    # Add to upload queue
    upload_id = await queue.add_upload({
        "video_id": video_id,
        "title": title,
        "description": description,
        "file_name": file.filename
    })
    
    # Save file temporarily
    temp_path = f"/tmp/{file.filename}"
    with open(temp_path, "wb") as f:
        content = await file.read()
        f.write(content)
    
    # Process upload in background
    background_tasks.add_task(process_upload, upload_id, temp_path, video_id)
    
    return {"message": "Upload started", "upload_id": upload_id}

@app.get("/uploads/{upload_id}/status")
async def get_upload_status(upload_id: str):
    status = await queue.get_upload_status(upload_id)
    if not status:
        raise HTTPException(status_code=404, detail="Upload not found")
    return status

async def process_upload(upload_id: str, file_path: str, video_id: int):
    try:
        # Update status to processing
        await queue.update_status(upload_id, "processing")
        
        # Upload to MinIO
        object_name = f"{video_id}.mp4"
        minio_client.fput_object("videos", object_name, file_path)
        
        # Update video status
        for video in videos:
            if video.id == video_id:
                video.status = "completed"
                break
        
        # Update queue status
        await queue.update_status(upload_id, "completed", {
            "video_id": video_id,
            "object_name": object_name
        })
        
        # Clean up temporary file
        os.remove(file_path)
        
    except Exception as e:
        # Update video status
        for video in videos:
            if video.id == video_id:
                video.status = "failed"
                break
        
        # Update queue status
        await queue.update_status(upload_id, "failed", {"error": str(e)})
        
        # Clean up temporary file
        if os.path.exists(file_path):
            os.remove(file_path)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000) 