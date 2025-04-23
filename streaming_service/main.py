from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import os
from typing import Optional
import mimetypes
from minio import Minio
import io

app = FastAPI(title="UALFlix Streaming Service")

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize MinIO client
minio_client = Minio(
    os.getenv("MINIO_ENDPOINT", "minio:9000"),
    access_key=os.getenv("MINIO_ACCESS_KEY", "minioadmin"),
    secret_key=os.getenv("MINIO_SECRET_KEY", "minioadmin"),
    secure=False
)

BUCKET_NAME = "videos"

@app.get("/")
async def root():
    return {"message": "Welcome to UALFlix Streaming Service"}

@app.get("/stream/{video_id}")
async def stream_video(video_id: str, request: Request):
    object_name = f"{video_id}.mp4"
    
    try:
        # Get object info
        obj_info = minio_client.stat_object(BUCKET_NAME, object_name)
        file_size = obj_info.size
        
        # Get range header
        range_header = request.headers.get("Range")
        start, end = parse_range_header(range_header, file_size)
        
        # Get object data
        data = minio_client.get_object(
            BUCKET_NAME,
            object_name,
            start=start,
            length=end - start + 1
        )
        
        content_length = end - start + 1
        headers = {
            "Content-Range": f"bytes {start}-{end}/{file_size}",
            "Accept-Ranges": "bytes",
            "Content-Length": str(content_length),
            "Content-Type": "video/mp4",
        }
        
        return StreamingResponse(
            data.stream(32*1024),  # 32KB chunks
            headers=headers,
            status_code=206 if range_header else 200
        )
        
    except Exception as e:
        raise HTTPException(status_code=404, detail="Video not found")

def parse_range_header(range_header: str, file_size: int) -> tuple[int, int]:
    try:
        range_type, range_value = range_header.split("=")
        if range_type.strip() != "bytes":
            raise ValueError
        
        start, end = range_value.split("-")
        start = int(start) if start else 0
        end = int(end) if end else file_size - 1
        
        return start, min(end, file_size - 1)
    except:
        return 0, file_size - 1

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001) 